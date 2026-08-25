"""
贝叶斯身份预测引擎
==================
根据对局中录入的行为，实时预测每个玩家的身份概率。

核心公式（贝叶斯定理）：
  P(身份|行为) ∝ P(身份) × P(行为|身份)

多条行为累积（假设条件独立）：
  P(身份|行为1,行为2,...,行为n) ∝ P(身份) × ∏ P(行为i|身份)

为避免数值下溢，使用对数概率计算：
  log P(身份|行为) ∝ log P(身份) + Σ log P(行为i|身份)

算法自我优化：
  对局确认后，根据玩家真实身份更新 algorithm_weights 表：
  每观察到一次"身份R的玩家做出行为A"，weight(R,A) += 1
  随着数据积累，预测会越来越准确
"""
import json
import math
from db import get_db, DB_TYPE, execute_write, query_all, query_one
from prophet_inference import get_prophet_claims, apply_prophet_inference, apply_role_uniqueness

# ============================================================
# 算法超参数（可根据效果调整）
# ============================================================
LEARNING_RATE = 0.1  # 改进#3：权重更新学习率，新数据的影响力占比

# ============================================================
# 改进#第四阶段：个性化似然度（每个玩家的行为倾向）
# ============================================================
MIN_PERSONALIZED_SAMPLES = 5   # 玩家最少需要多少局已确认对局才使用个性化修正
PERSONALIZED_FACTOR_MIN = 0.5  # 个性化修正系数下限（避免极端值）
PERSONALIZED_FACTOR_MAX = 2.0  # 个性化修正系数上限（避免极端值）


def ph():
    """参数占位符"""
    return '%s' if DB_TYPE == 'postgresql' else '?'


# ============================================================
# 权重管理
# ============================================================
def get_all_weights():
    """获取所有算法权重
    返回 {(action_id, role_id): {"weight": float, "sample_count": int}}
    """
    rows = query_all("SELECT * FROM algorithm_weights")
    result = {}
    for w in rows:
        result[(w["action_id"], w["role_id"])] = {
            "weight": w["weight"],
            "sample_count": w["sample_count"]
        }
    return result


def get_or_create_weight(action_id, role_id, default_weight):
    """获取权重记录，不存在则创建"""
    existing = query_one(
        f"SELECT * FROM algorithm_weights WHERE action_id={ph()} AND role_id={ph()}",
        (action_id, role_id)
    )
    if existing:
        return existing
    execute_write(
        f"INSERT INTO algorithm_weights (action_id, role_id, weight, sample_count) VALUES ({ph()}, {ph()}, {ph()}, 0)",
        (action_id, role_id, default_weight)
    )
    return {"weight": default_weight, "sample_count": 0, "action_id": action_id, "role_id": role_id}


# ============================================================
# 先验概率 P(身份)
# ============================================================
def calculate_prior(game_id):
    """计算先验概率 P(身份)
    基于版型配置：某身份的先验 = 该身份数量 / 总玩家数
    没有版型时用均匀分布。
    返回 {role_id: probability}
    """
    all_roles = query_all("SELECT id, name FROM roles WHERE is_active = TRUE")
    role_ids = [r["id"] for r in all_roles]

    if not role_ids:
        return {}

    game = query_one("SELECT * FROM games WHERE id = " + ph(), (game_id,))
    if not game:
        return {rid: 1.0 / len(role_ids) for rid in role_ids}

    # 尝试从版型获取身份配置
    if game.get("setup_id"):
        setup = query_one("SELECT * FROM setups WHERE id = " + ph(), (game["setup_id"],))
        if setup and setup.get("role_config"):
            try:
                config = json.loads(setup["role_config"])
                name_to_id = {r["name"]: r["id"] for r in all_roles}
                role_counts = {}
                total = 0
                for role_name, count in config.items():
                    if role_name in name_to_id:
                        rid = name_to_id[role_name]
                        role_counts[rid] = count
                        total += count
                if total > 0 and role_counts:
                    # 只返回版型中包含的身份的先验，版型外的身份不返回
                    prior = {}
                    for rid, cnt in role_counts.items():
                        prior[rid] = cnt / total
                    return prior
            except (json.JSONDecodeError, TypeError):
                pass

    # 均匀分布（没有版型时）
    return {rid: 1.0 / len(role_ids) for rid in role_ids}


# ============================================================
# 改进#1：利用行为目标信息修正预测
# ============================================================
# 目标信息修正强度系数（越大修正越明显）
TARGET_CORRECTION_STRENGTH = 0.5

# 需要利用目标信息的行为ID及修正逻辑
# 规则：根据目标的身份概率分布，给发起者的对应身份乘修正系数
TARGET_AWARE_ACTIONS = {
    2: "check",    # 查杀
    3: "golden",   # 发金水
    10: "side",    # 站边
}


# ============================================================
# 策略2：按版型自动调整查验可信度
# ============================================================
# 版型名称关键词 → 查验可信度（多种特殊角色取最低值）
SETUP_RELIABILITY_RULES = [
    (["混血儿"], 0.90),
    (["机械狼"], 0.85),
    (["魔术师"], 0.80),
    (["梦魇", "狼美人", "白狼王", "狼王"], 0.95),  # 特殊狼不影响查验结果
]
DEFAULT_RELIABILITY = 1.0  # 标准版型默认100%可信


# ============================================================
# 改进#6：行为组合模式识别（2-gram）
# ============================================================
# 预定义有意义的连续两条行为组合
# 格式: ((前行为ID, 后行为ID), {修正键: 系数})
# 修正键: "role:ID" 指特定身份, "camp:阵营名" 指整个阵营
BEHAVIOR_COMBINATIONS = [
    # === 预言家相关组合 ===
    # 注意：悍跳狼发查杀/金水取决于战术，不是固定倾向，所以狼人不额外加权
    ((1, 3), {"role:1": 1.20}),                      # 跳预言家→发金水：真预言家常规操作
    ((1, 2), {"role:1": 1.15}),                      # 跳预言家→查杀：真预言家常规操作
    ((1, 10), {"role:1": 1.05}),                      # 跳预言家→站边
    ((2, 10), {"camp:狼人": 1.10}),                    # 查杀→站边：可能查杀后站边狼队友（弱参考）
    ((3, 10), {"role:1": 1.05}),                      # 发金水→站边

    # === 神牌相关组合 ===
    # 注意：狼人可以穿神牌衣服，所以修正系数不宜过高
    ((4, 15), {"role:2": 1.20}),  # 跳女巫→使用解药：女巫可能，但狼人也可穿衣服
    ((4, 16), {"role:2": 1.20}),  # 跳女巫→使用毒药
    ((5, 14), {"role:3": 1.30, "role:8": 1.30}),  # 跳猎人→开枪：猎人/狼王技能，相对可靠
    ((6, 17), {"role:5": 1.30}),  # 跳守卫→守护：守卫技能，相对可靠

    # === 平民相关组合 ===
    ((7, 19), {"role:6": 1.10}),  # 认平民→划水

    # === 狼人相关组合 ===
    ((12, 10), {"camp:狼人": 1.20}),  # 冲锋→站边：狼人给狼队友号票（弱参考）
    ((11, 10), {"camp:狼人": 1.10}),  # 倒钩→站边：倒钩狼站边真预言家（弱参考，因倒钩狼存在）
    ((1, 13), {"camp:狼人": 1.50}),    # 跳预言家→自爆：悍跳狼自爆（相对可靠）
]


def apply_combination_correction(player_id, log_probs, actor_behaviors, role_camps, role_ids):
    """改进#6：应用行为组合模式修正（2-gram）

    检查玩家行为序列中连续两条行为的组合，如果匹配预定义模式，
    给对应身份/阵营的对数概率加 log(修正系数)。

    参数:
        player_id: 玩家ID
        log_probs: 当前玩家的对数概率 {role_id: log_prob}
        actor_behaviors: 该玩家作为发起者的行为列表（按时间顺序）
        role_camps: 身份ID→阵营映射
        role_ids: 所有身份ID列表
    """
    if len(actor_behaviors) < 2:
        return

    for i in range(1, len(actor_behaviors)):
        prev_action = actor_behaviors[i - 1]["action_id"]
        curr_action = actor_behaviors[i]["action_id"]

        # 查找匹配的组合模式
        for pattern, corrections in BEHAVIOR_COMBINATIONS:
            if pattern[0] == prev_action and pattern[1] == curr_action:
                for key, coeff in corrections.items():
                    if key.startswith("role:"):
                        # 特定身份修正
                        rid = int(key.split(":")[1])
                        if rid in role_ids:
                            log_probs[rid] += math.log(max(coeff, 0.01))
                    elif key.startswith("camp:"):
                        # 整个阵营修正
                        camp = key.split(":")[1]
                        for rid in role_ids:
                            if role_camps.get(rid) == camp:
                                log_probs[rid] += math.log(max(coeff, 0.01))
                break  # 每个组合只匹配第一个模式


# ============================================================
# 改进#7：玩家关系图建模（简化版标签传播）
# ============================================================
RELATIONSHIP_INFLUENCE = 0.1  # 关系图对阵营概率的影响强度（弱参考）
# 注意：关系传播不可靠，因为倒钩狼会站边真预言家、狼保好人、好人互踩都很常见。
# 这里仅作为极弱参考，未来应改为"个性化行为倾向"（每个玩家拿不同身份时的行为偏好）。

# 行为类型 → 关系分数（正=同阵营倾向，负=对立阵营倾向）
RELATIONSHIP_ACTIONS = {
    10: 1.0,   # 站边：强同阵营
    3: 0.8,    # 发金水：同阵营（但弱于站边）
    2: -1.0,   # 查杀：强对立阵营
    18: -0.5,  # 质疑：弱对立阵营
}


def build_relationship_matrix(behaviors, player_ids):
    """改进#7：构建玩家关系矩阵（有向图）

    根据行为记录计算每对玩家之间的关系分数：
    - A站边B → A→B: +1.0（A认为B是同阵营）
    - A发金水B → A→B: +0.8
    - A查杀B → A→B: -1.0（A认为B是对立阵营）
    - A质疑B → A→B: -0.5

    返回: {actor_id: {target_id: 关系分数}}
    """
    player_set = set(player_ids)
    rel = {pid: {} for pid in player_ids}

    for b in behaviors:
        actor = b["actor_id"]
        target = b.get("target_id")
        action_id = b["action_id"]

        if not target or actor not in player_set or target not in player_set:
            continue

        score = RELATIONSHIP_ACTIONS.get(action_id, 0)
        if score != 0:
            rel[actor][target] = rel[actor].get(target, 0) + score

    return rel


def apply_relationship_correction(results, rel, role_camps, role_ids, role_names):
    """改进#7：应用玩家关系图修正（简化版标签传播，单轮迭代）

    每个玩家的阵营概率受其"邻居"的影响：
    - 邻居好人概率高 + 正关系（站边/发金水）→ 该玩家好人概率提升
    - 邻居好人概率高 + 负关系（查杀/质疑）→ 该玩家狼人概率提升

    修正公式：
    邻居影响 = Σ(关系分数 × 邻居好人概率) / Σ(|关系分数|)
    新好人概率 = 原好人概率 × (1 + 影响强度 × 邻居影响)

    然后按比例调整好人/狼人阵营内各身份的概率。
    注意：简化假设好人+狼人=1，第三方阵营暂不参与关系传播。

    参数:
        results: 所有玩家的预测结果 {player_id: {"probabilities": {...}, ...}}
        rel: 玩家关系矩阵 {actor_id: {target_id: 分数}}
        role_camps: 身份ID→阵营映射
        role_ids: 所有身份ID列表
        role_names: 身份ID→名称映射
    """
    # 先计算每个玩家的好人概率
    good_probs = {}
    for pid, data in results.items():
        probs = data["probabilities"]
        good_prob = sum(p for rid, p in probs.items() if role_camps.get(rid) == "好人")
        good_probs[pid] = good_prob

    # 对每个玩家应用关系图修正
    for pid in results:
        neighbors = rel.get(pid, {})
        if not neighbors:
            continue

        # 计算加权邻居影响
        total_weight = 0.0
        weighted_good = 0.0
        for nid, score in neighbors.items():
            if nid in good_probs:
                total_weight += abs(score)
                weighted_good += score * good_probs[nid]

        if total_weight == 0:
            continue

        # 邻居影响范围 [-1, 1]：正=邻居倾向好人，负=邻居倾向狼人
        neighbor_influence = weighted_good / total_weight

        # 修正好人概率
        old_good = good_probs[pid]
        new_good = old_good * (1 + RELATIONSHIP_INFLUENCE * neighbor_influence)
        new_good = max(0.01, min(0.99, new_good))
        new_wolf = 1.0 - new_good  # 简化：好人+狼人=1

        # 按比例调整各身份的概率
        probs = results[pid]["probabilities"]
        old_good_total = sum(p for rid, p in probs.items() if role_camps.get(rid) == "好人")
        old_wolf_total = sum(p for rid, p in probs.items() if role_camps.get(rid) == "狼人")

        if old_good_total > 0.001:
            scale_good = new_good / old_good_total
            for rid in role_ids:
                if role_camps.get(rid) == "好人":
                    probs[rid] *= scale_good

        if old_wolf_total > 0.001:
            scale_wolf = new_wolf / old_wolf_total
            for rid in role_ids:
                if role_camps.get(rid) == "狼人":
                    probs[rid] *= scale_wolf

        # 重新归一化
        total = sum(probs.values())
        if total > 0:
            for rid in role_ids:
                probs[rid] = round(probs[rid] / total, 6)

        # 更新最高概率身份
        top_role_id = max(probs, key=probs.get) if probs else None
        results[pid]["top_role_id"] = top_role_id
        results[pid]["top_role_name"] = role_names.get(top_role_id, "") if top_role_id else ""
        results[pid]["top_probability"] = round(probs[top_role_id], 6) if top_role_id else 0.0


def get_check_reliability(setup_name):
    """根据版型名称获取预言家查验可信度（策略2）

    标准版型无特殊角色 = 1.0
    含混血儿 = 0.9（混血儿可能被链好人，查验好人但底牌狼）
    含机械狼 = 0.85（机械狼可能学习好人技能）
    含魔术师 = 0.8（换号导致查验对象不符）
    多种特殊角色叠加取最低值
    """
    if not setup_name:
        return DEFAULT_RELIABILITY
    reliability = DEFAULT_RELIABILITY
    for keywords, rel in SETUP_RELIABILITY_RULES:
        for kw in keywords:
            if kw in setup_name:
                reliability = min(reliability, rel)
                break
    return reliability


def _get_camp_prob(probabilities, role_camps, camp):
    """计算某阵营的总概率"""
    return sum(p for rid, p in probabilities.items() if role_camps.get(rid) == camp)


def apply_target_info_correction(player_id, log_probs, behaviors, base_results, role_camps, role_ids):
    """改进#1：利用行为目标信息修正发起者的对数概率

    对每条有 target_id 的行为，根据目标的基础预测分布，修正发起者的概率：
    - 查杀(action=2)：目标狼人概率高 → 发起者预言家概率提升；目标好人概率高 → 发起者狼人概率提升
    - 发金水(action=3)：目标好人概率高 → 发起者预言家概率提升；目标狼人概率高 → 发起者狼人概率提升
    - 站边(action=10)：目标预言家概率高 → 发起者好人阵营概率提升；目标狼人概率高 → 发起者狼人阵营概率提升

    参数:
        player_id: 当前玩家ID
        log_probs: 当前玩家的对数概率 {role_id: log_prob}
        behaviors: 当前玩家作为发起者的行为列表
        base_results: 所有玩家的基础预测结果 {player_id: {"probabilities": {...}}}
        role_camps: 身份ID→阵营映射 {role_id: camp}
        role_ids: 所有身份ID列表
    """
    s = TARGET_CORRECTION_STRENGTH

    for b in behaviors:
        target_id = b.get("target_id")
        action_id = b.get("action_id")

        # 只处理有目标且在目标感知行为列表中的行为
        if not target_id or action_id not in TARGET_AWARE_ACTIONS:
            continue

        # 获取目标的基础预测分布
        target_data = base_results.get(target_id)
        if not target_data:
            continue
        target_probs = target_data.get("probabilities", {})
        if not target_probs:
            continue

        action_type = TARGET_AWARE_ACTIONS[action_id]

        # 计算目标各阵营/身份的概率
        target_wolf_prob = _get_camp_prob(target_probs, role_camps, "狼人")
        target_good_prob = _get_camp_prob(target_probs, role_camps, "好人")
        target_seer_prob = 0.0
        for rid, p in target_probs.items():
            if role_camps.get(rid) == "好人" and rid in role_ids:
                # 找预言家身份（名称匹配）
                pass
        # 直接从概率分布中找预言家（id=1，因为初始数据中预言家是第一个）
        # 更稳健的方式：遍历所有身份，找名称为"预言家"的
        # 这里用一个简单的近似：好人阵营中概率最高的身份作为"预言家候选"
        # 实际上应该传 role_names 进来，但为了简化，我们用阵营概率来近似

        if action_type == "check":
            # 查杀：目标越像狼人，发起者越像预言家；目标越像好人，发起者越像狼人
            for rid in role_ids:
                camp = role_camps.get(rid)
                if camp == "好人":
                    # 好人阵营：目标狼人概率越高，预言家类身份越可能
                    # 简化：所有好人身份都乘 (1 + s*(target_wolf_prob - 0.3))
                    coeff = 1.0 + s * (target_wolf_prob - 0.3)
                    log_probs[rid] += math.log(max(coeff, 0.1))
                elif camp == "狼人":
                    # 狼人阵营：目标好人概率越高，悍跳狼越可能
                    coeff = 1.0 + s * (target_good_prob - 0.7)
                    log_probs[rid] += math.log(max(coeff, 0.1))

        elif action_type == "golden":
            # 发金水：目标越像好人，发起者越像预言家；目标越像狼人，发起者越像狼人
            for rid in role_ids:
                camp = role_camps.get(rid)
                if camp == "好人":
                    coeff = 1.0 + s * (target_good_prob - 0.7)
                    log_probs[rid] += math.log(max(coeff, 0.1))
                elif camp == "狼人":
                    coeff = 1.0 + s * (target_wolf_prob - 0.3)
                    log_probs[rid] += math.log(max(coeff, 0.1))

        elif action_type == "side":
            # 站边：目标越像预言家（好人），站边者越像好人；目标越像狼人，站边者越像狼人
            for rid in role_ids:
                camp = role_camps.get(rid)
                if camp == "好人":
                    coeff = 1.0 + s * 0.6 * (target_good_prob - 0.7)
                    log_probs[rid] += math.log(max(coeff, 0.1))
                elif camp == "狼人":
                    coeff = 1.0 + s * 0.6 * (target_wolf_prob - 0.3)
                    log_probs[rid] += math.log(max(coeff, 0.1))


def apply_target_as_target_correction(player_id, log_probs, behaviors_as_target, base_results, role_camps, role_ids, role_names, check_reliability):
    """改进#1（方案B）：当玩家作为行为目标时，用条件概率分解修正身份概率

    核心逻辑（全概率公式）：
    - 发金水(A→B)：P(B好人) = P(A预言家)×可信度 + P(A非预言家)×基础好人概率
    - 查杀(A→B)：P(B狼人) = P(A预言家)×可信度 + P(A非预言家)×基础狼人概率
    - 站边(A→B)：保留相关性修正（站边逻辑蕴涵较弱）

    这样能保证：如果A有80%概率是预言家，B的好人概率至少为80%×可信度

    参数:
        player_id: 当前玩家ID（作为目标）
        log_probs: 当前玩家的对数概率 {role_id: log_prob}
        behaviors_as_target: 以该玩家为目标的行为列表
        base_results: 所有玩家的基础预测结果
        role_camps: 身份ID→阵营映射
        role_ids: 所有身份ID列表
        role_names: 身份ID→名称映射（用于查找预言家）
        check_reliability: 当前版型的查验可信度（策略2）
    """
    # 找到预言家的 role_id
    seer_role_id = None
    for rid, name in role_names.items():
        if name == "预言家":
            seer_role_id = rid
            break

    for b in behaviors_as_target:
        actor_id = b.get("actor_id")
        action_id = b.get("action_id")

        if not actor_id or action_id not in TARGET_AWARE_ACTIONS:
            continue

        # 获取发起者的基础预测分布
        actor_data = base_results.get(actor_id)
        if not actor_data:
            continue
        actor_probs = actor_data.get("probabilities", {})
        if not actor_probs:
            continue

        action_type = TARGET_AWARE_ACTIONS[action_id]

        # 发起者是预言家的概率
        actor_seer_prob = actor_probs.get(seer_role_id, 0.0) if seer_role_id else 0.0

        # 计算目标当前的好人/狼人概率（从对数概率转换）
        max_log = max(log_probs.values())
        current_probs = {}
        total = 0.0
        for rid in role_ids:
            p = math.exp(log_probs[rid] - max_log)
            current_probs[rid] = p
            total += p
        if total > 0:
            for rid in role_ids:
                current_probs[rid] /= total

        target_good_prob = sum(p for rid, p in current_probs.items() if role_camps.get(rid) == "好人")
        target_wolf_prob = sum(p for rid, p in current_probs.items() if role_camps.get(rid) == "狼人")

        if action_type == "golden":
            # 发金水：P(B好人) = P(A预言家)×可信度 + P(A非预言家)×基础好人概率
            new_good_prob = actor_seer_prob * check_reliability + (1 - actor_seer_prob) * target_good_prob
            new_good_prob = max(0.01, min(0.99, new_good_prob))
            new_wolf_prob = 1.0 - new_good_prob  # 简化：好人+狼人=1，第三方暂不单独处理

            # 按比例调整好人阵营各身份的对数概率
            if target_good_prob > 0.001:
                scale = new_good_prob / target_good_prob
                for rid in role_ids:
                    if role_camps.get(rid) == "好人":
                        log_probs[rid] += math.log(max(scale, 0.01))
            if target_wolf_prob > 0.001:
                scale = new_wolf_prob / target_wolf_prob
                for rid in role_ids:
                    if role_camps.get(rid) == "狼人":
                        log_probs[rid] += math.log(max(scale, 0.01))

        elif action_type == "check":
            # 查杀：P(B狼人) = P(A预言家)×可信度 + P(A非预言家)×基础狼人概率
            new_wolf_prob = actor_seer_prob * check_reliability + (1 - actor_seer_prob) * target_wolf_prob
            new_wolf_prob = max(0.01, min(0.99, new_wolf_prob))
            new_good_prob = 1.0 - new_wolf_prob

            if target_wolf_prob > 0.001:
                scale = new_wolf_prob / target_wolf_prob
                for rid in role_ids:
                    if role_camps.get(rid) == "狼人":
                        log_probs[rid] += math.log(max(scale, 0.01))
            if target_good_prob > 0.001:
                scale = new_good_prob / target_good_prob
                for rid in role_ids:
                    if role_camps.get(rid) == "好人":
                        log_probs[rid] += math.log(max(scale, 0.01))

        elif action_type == "side":
            # 站边：保留相关性修正（站边的逻辑蕴涵较弱，用发起者好人概率做相关性）
            actor_good_prob = sum(p for rid, p in actor_probs.items() if role_camps.get(rid) == "好人")
            s = 0.3  # 站边修正强度
            for rid in role_ids:
                camp = role_camps.get(rid)
                if camp == "好人":
                    coeff = 1.0 + s * (actor_good_prob - 0.5)
                    log_probs[rid] += math.log(max(coeff, 0.1))
                elif camp == "狼人":
                    coeff = 1.0 + s * (0.5 - actor_good_prob)
                    log_probs[rid] += math.log(max(coeff, 0.1))


# ============================================================
# 似然度 P(行为|身份)
# ============================================================
def calculate_likelihood_table(weights, actions, role_ids):
    """计算所有 (行为,身份) 组合的似然度 P(行为|身份)

    P(行为A|身份R) = weight(R,A) / sum(weight(R, 所有行为))

    参数:
        weights: {(action_id, role_id): weight}
        actions: [{"id":..., "default_weight":...}, ...]
        role_ids: [role_id, ...]

    返回:
        {(action_id, role_id): probability}
    """
    likelihood = {}

    for rid in role_ids:
        # 计算该身份下所有行为的权重总和
        total_weight = 0.0
        action_weights = {}
        for act in actions:
            aid = act["id"]
            default_w = act.get("default_weight", 1.0)
            w = weights.get((aid, rid), default_w)
            action_weights[aid] = w
            total_weight += w

        # 计算条件概率
        for act in actions:
            aid = act["id"]
            if total_weight > 0:
                likelihood[(aid, rid)] = action_weights[aid] / total_weight
            else:
                likelihood[(aid, rid)] = 1.0 / len(actions)

    return likelihood


# ============================================================
# 改进#第四阶段：个性化似然度（每个玩家的行为倾向）
# ============================================================
def build_personalized_stats():
    """构建个性化行为统计（从持久化表 player_behavior_stats 读取）

    读取：
    1. 每个玩家拿每个身份时，各行为的出现次数和总局数
    2. 计算频率和全局平均

    返回:
        personalized_stats: {player_id: {role_id: {action_id: frequency}}}
        global_stats: {role_id: {action_id: frequency}}
        player_game_counts: {player_id: {role_id: game_count}}
    """
    # 从持久化表读取所有统计数据
    stats_rows = query_all("""
        SELECT player_id, role_id, action_id, count, game_count
        FROM player_behavior_stats
    """)

    # 1. 构建玩家对局数（去重，因为同一 player_id+role_id 的 game_count 相同）
    player_game_counts = {}
    for row in stats_rows:
        pid = row["player_id"]
        rid = row["role_id"]
        if pid not in player_game_counts:
            player_game_counts[pid] = {}
        player_game_counts[pid][rid] = row["game_count"]

    # 2. 构建个性化频率
    personalized_stats = {}
    for row in stats_rows:
        pid = row["player_id"]
        rid = row["role_id"]
        aid = row["action_id"]
        cnt = row["count"]
        gc = row["game_count"]

        if gc > 0:
            if pid not in personalized_stats:
                personalized_stats[pid] = {}
            if rid not in personalized_stats[pid]:
                personalized_stats[pid][rid] = {}
            personalized_stats[pid][rid][aid] = cnt / gc

    # 3. 计算全局平均频率（所有玩家拿每个身份时各行为的平均频率）
    global_action_counts = {}  # {role_id: {action_id: total_count}}
    global_game_counts = {}    # {role_id: total_game_count}
    for row in stats_rows:
        rid = row["role_id"]
        aid = row["action_id"]
        cnt = row["count"]
        gc = row["game_count"]

        if rid not in global_action_counts:
            global_action_counts[rid] = {}
        global_action_counts[rid][aid] = global_action_counts[rid].get(aid, 0) + cnt

        # 全局对局数需要去重（同一 player_id+role_id 只算一次）
        if rid not in global_game_counts:
            global_game_counts[rid] = set()
        global_game_counts[rid].add(row["player_id"])

    global_stats = {}
    for rid, action_counts in global_action_counts.items():
        total_games = len(global_game_counts.get(rid, set()))
        if total_games > 0:
            global_stats[rid] = {
                aid: cnt / total_games for aid, cnt in action_counts.items()
            }

    return personalized_stats, global_stats, player_game_counts


def update_personalized_stats(game_id):
    """对局确认后，更新个性化行为统计表（增量学习）

    对该对局的每个玩家：
    - 获取其真实身份
    - 统计其在这局中做了哪些行为
    - 更新 player_behavior_stats 表：count += 行为次数，game_count += 1

    参数:
        game_id: 对局ID

    返回:
        更新的玩家数量
    """
    # 1. 获取该对局玩家的真实身份
    game_players = query_all(
        "SELECT player_id, actual_role_id FROM game_players WHERE game_id = " + ph(),
        (game_id,)
    )
    player_actual_role = {
        gp["player_id"]: gp["actual_role_id"]
        for gp in game_players
        if gp.get("actual_role_id")
    }

    if not player_actual_role:
        return 0

    # 2. 获取该对局的行为记录，按发起者分组
    behaviors = query_all(
        "SELECT actor_id, action_id FROM behavior_records WHERE game_id = " + ph(),
        (game_id,)
    )
    behaviors_by_actor = {}
    for b in behaviors:
        actor = b["actor_id"]
        if actor not in behaviors_by_actor:
            behaviors_by_actor[actor] = {}
        aid = b["action_id"]
        behaviors_by_actor[actor][aid] = behaviors_by_actor[actor].get(aid, 0) + 1

    # 3. 更新每个玩家的统计
    updated_count = 0
    for player_id, role_id in player_actual_role.items():
        action_counts = behaviors_by_actor.get(player_id, {})

        # 对每个行为，更新或插入统计记录
        for action_id, count in action_counts.items():
            # 检查是否已存在记录
            existing = query_one(
                "SELECT id, count, game_count FROM player_behavior_stats "
                "WHERE player_id = " + ph() + " AND role_id = " + ph() + " AND action_id = " + ph(),
                (player_id, role_id, action_id)
            )

            if existing:
                # 更新现有记录
                execute_write(
                    "UPDATE player_behavior_stats SET count = count + " + ph() +
                    ", game_count = " + ph() + ", updated_at = CURRENT_TIMESTAMP WHERE id = " + ph(),
                    (count, 1, existing["id"])
                )
            else:
                # 插入新记录
                execute_write(
                    "INSERT INTO player_behavior_stats (player_id, role_id, action_id, count, game_count) "
                    "VALUES (" + ph() + ", " + ph() + ", " + ph() + ", " + ph() + ", " + ph() + ")",
                    (player_id, role_id, action_id, count, 1)
                )

        # 如果玩家没有任何行为，不插入记录（game_count 为0，数据不足时不使用个性化修正）
        updated_count += 1

    return updated_count


def get_personalized_factor(player_id, role_id, action_id,
                             personalized_stats, global_stats, player_game_counts):
    """获取个性化修正系数

    系数 = 玩家P拿身份R时做行为A的频率 / 全局平均频率
    - 系数 > 1：该玩家拿这个身份时更倾向于做这个行为
    - 系数 < 1：该玩家拿这个身份时更少做这个行为
    - 系数 = 1：无个性化修正（数据不足或全局频率为0）

    参数:
        player_id: 玩家ID
        role_id: 身份ID
        action_id: 行为ID
        personalized_stats: 个性化频率统计
        global_stats: 全局平均频率统计
        player_game_counts: 玩家对局数统计

    返回:
        个性化修正系数（限制在 [MIN, MAX] 范围内）
    """
    # 检查数据是否足够（该玩家拿该身份的对局数 >= 阈值）
    game_count = player_game_counts.get(player_id, {}).get(role_id, 0)
    if game_count < MIN_PERSONALIZED_SAMPLES:
        return 1.0  # 数据不足，不使用个性化修正

    # 获取玩家频率和全局平均频率
    player_freq = personalized_stats.get(player_id, {}).get(role_id, {}).get(action_id, 0)
    global_freq = global_stats.get(role_id, {}).get(action_id, 0)

    if global_freq == 0:
        return 1.0  # 全局频率为0，无法计算相对系数

    # 计算相对系数
    factor = player_freq / global_freq

    # 限制范围，避免极端值
    factor = max(PERSONALIZED_FACTOR_MIN, min(PERSONALIZED_FACTOR_MAX, factor))

    return factor


# ============================================================
# 改进#第五阶段：机器学习模型（逻辑回归）
# ============================================================
# ML模型超参数
ML_MIN_SAMPLES = 50          # 最少训练样本数，低于此数不使用ML模型
ML_LEARNING_RATE = 0.01      # 逻辑回归梯度下降学习率
ML_ITERATIONS = 100           # 每次训练的迭代次数
ML_REGULARIZATION = 0.01      # L2正则化系数，防止过拟合

# 行为ID列表（用于特征提取，按ID排序）
ALL_ACTION_IDS = list(range(1, 20))  # 1-19，共19种行为


def extract_features(actor_behaviors):
    """从玩家的行为记录中提取特征向量

    特征：
    1. 每种行为的出现次数（19维）
    2. 行为总数（1维）
    3. 是否跳预言家（1维）
    4. 是否有狼人行为（冲锋/倒钩/自爆，1维）

    返回:
        features: 特征列表 [f1, f2, ..., f22]
    """
    # 每种行为的出现次数（19维）
    action_counts = [0] * len(ALL_ACTION_IDS)
    for b in actor_behaviors:
        aid = b["action_id"]
        if 1 <= aid <= 19:
            action_counts[aid - 1] += 1

    # 行为总数
    total_actions = sum(action_counts)

    # 是否跳预言家
    has_jump_prophet = 1 if action_counts[0] > 0 else 0  # action_id=1

    # 是否有狼人行为（冲锋=12, 倒钩=11, 自爆=13）
    has_wolf_action = 1 if (action_counts[10] > 0 or action_counts[11] > 0 or action_counts[12] > 0) else 0

    # 组合特征向量
    features = action_counts + [total_actions, has_jump_prophet, has_wolf_action]
    return features


def sigmoid(z):
    """Sigmoid函数，把分数转换成0~1的概率"""
    if z >= 0:
        return 1 / (1 + math.exp(-z))
    else:
        exp_z = math.exp(z)
        return exp_z / (1 + exp_z)


class LogisticRegression:
    """逻辑回归二分类器（纯Python实现，无外部依赖）

    用于判断玩家是"好人"还是"狼人"。
    预测时输出是狼人的概率，然后调整朴素贝叶斯的阵营概率。
    """

    def __init__(self, n_features):
        """初始化模型

        参数:
            n_features: 特征维度
        """
        self.n_features = n_features
        self.weights = [0.0] * n_features  # 权重向量
        self.bias = 0.0                     # 偏置
        self.sample_count = 0               # 训练样本数
        self.accuracy = 0.0                 # 训练集准确率

    def predict_proba(self, features):
        """预测是正类（狼人）的概率

        参数:
            features: 特征向量

        返回:
            是狼人的概率（0~1）
        """
        z = self.bias + sum(w * x for w, x in zip(self.weights, features))
        return sigmoid(z)

    def train_step(self, features, label):
        """单步训练（增量学习）

        参数:
            features: 特征向量
            label: 真实标签（1=狼人，0=好人）
        """
        # 预测概率
        pred = self.predict_proba(features)
        error = label - pred

        # 梯度下降更新权重和偏置（带L2正则化）
        for i in range(self.n_features):
            # 梯度 = error * x_i - regularization * w_i
            gradient = error * features[i] - ML_REGULARIZATION * self.weights[i]
            self.weights[i] += ML_LEARNING_RATE * gradient

        # 更新偏置
        self.bias += ML_LEARNING_RATE * error

        self.sample_count += 1

    def to_dict(self):
        """把模型转换成字典（用于持久化存储）"""
        return {
            "n_features": self.n_features,
            "weights": self.weights,
            "bias": self.bias,
            "sample_count": self.sample_count,
            "accuracy": self.accuracy,
        }

    @classmethod
    def from_dict(cls, data):
        """从字典加载模型"""
        model = cls(data["n_features"])
        model.weights = data["weights"]
        model.bias = data["bias"]
        model.sample_count = data.get("sample_count", 0)
        model.accuracy = data.get("accuracy", 0.0)
        return model


def save_ml_model(model, model_type, target_class):
    """保存ML模型到数据库

    参数:
        model: 模型对象（LogisticRegression）
        model_type: 模型类型字符串
        target_class: 目标类别字符串
    """
    import json
    model_data = json.dumps(model.to_dict())

    # 检查是否已存在同类型模型
    existing = query_one(
        "SELECT id FROM ml_models WHERE model_type = " + ph() + " AND target_class = " + ph(),
        (model_type, target_class)
    )

    if existing:
        # 更新现有模型
        execute_write(
            "UPDATE ml_models SET model_data = " + ph() + ", sample_count = " + ph() +
            ", accuracy = " + ph() + ", trained_at = CURRENT_TIMESTAMP WHERE id = " + ph(),
            (model_data, model.sample_count, model.accuracy, existing["id"])
        )
    else:
        # 插入新模型
        execute_write(
            "INSERT INTO ml_models (model_type, target_class, model_data, sample_count, accuracy) "
            "VALUES (" + ph() + ", " + ph() + ", " + ph() + ", " + ph() + ", " + ph() + ")",
            (model_type, target_class, model_data, model.sample_count, model.accuracy)
        )


def load_ml_model(model_type, target_class):
    """从数据库加载ML模型

    参数:
        model_type: 模型类型字符串
        target_class: 目标类别字符串

    返回:
        模型对象，如果不存在则返回None
    """
    import json
    record = query_one(
        "SELECT model_data FROM ml_models WHERE model_type = " + ph() + " AND target_class = " + ph(),
        (model_type, target_class)
    )

    if not record:
        return None

    data = json.loads(record["model_data"])
    return LogisticRegression.from_dict(data)


def train_ml_model_from_game(game_id):
    """从一局已确认对局中训练ML模型（增量学习）

    参数:
        game_id: 对局ID

    返回:
        是否成功训练
    """
    # 1. 获取对局玩家的真实身份
    game_players = query_all(
        "SELECT player_id, actual_role_id FROM game_players WHERE game_id = " + ph(),
        (game_id,)
    )
    player_roles = {
        gp["player_id"]: gp["actual_role_id"]
        for gp in game_players
        if gp.get("actual_role_id")
    }

    if not player_roles:
        return False

    # 2. 获取该对局的行为记录，按发起者分组
    behaviors = query_all(
        "SELECT actor_id, action_id FROM behavior_records WHERE game_id = " + ph(),
        (game_id,)
    )
    behaviors_by_actor = {}
    for b in behaviors:
        actor = b["actor_id"]
        if actor not in behaviors_by_actor:
            behaviors_by_actor[actor] = []
        behaviors_by_actor[actor].append(b)

    # 3. 加载或创建逻辑回归模型（好人vs狼人）
    model = load_ml_model("logistic_regression", "好人_vs_狼人")
    if model is None:
        # 特征维度 = 19种行为 + 行为总数 + 是否跳预言家 + 是否有狼人行为 = 22
        model = LogisticRegression(n_features=22)

    # 4. 对每个玩家进行增量训练
    for player_id, role_id in player_roles.items():
        actor_behaviors = behaviors_by_actor.get(player_id, [])
        features = extract_features(actor_behaviors)

        # 标签：1=狼人，0=好人（第三方暂不参与训练）
        if role_id in (7, 8, 9):  # 狼人、狼王、白狼王
            label = 1
        elif role_id in (1, 2, 3, 4, 5, 6):  # 预言家、女巫、猎人、白痴、守卫、平民
            label = 0
        else:
            continue  # 第三方身份跳过

        model.train_step(features, label)

    # 5. 保存模型
    save_ml_model(model, "logistic_regression", "好人_vs_狼人")

    return True


def apply_ml_correction(player_id, actor_behaviors, results, role_ids, role_camps, role_names):
    """应用ML模型修正预测结果

    如果ML模型已训练且样本数足够，用逻辑回归预测的狼人概率调整阵营概率。

    参数:
        player_id: 玩家ID
        actor_behaviors: 该玩家的行为记录
        results: 预测结果字典
        role_ids: 所有身份ID
        role_camps: 身份ID→阵营映射
        role_names: 身份ID→名称映射
    """
    # 加载ML模型
    model = load_ml_model("logistic_regression", "好人_vs_狼人")
    if model is None or model.sample_count < ML_MIN_SAMPLES:
        return  # 模型未训练或样本不足，不修正

    # 提取特征并预测狼人概率
    features = extract_features(actor_behaviors)
    wolf_prob_ml = model.predict_proba(features)  # ML模型预测的狼人概率
    good_prob_ml = 1.0 - wolf_prob_ml

    # 获取当前朴素贝叶斯预测的阵营概率
    probs = results[player_id]["probabilities"]
    wolf_prob_nb = sum(p for rid, p in probs.items() if role_camps.get(rid) == "狼人")
    good_prob_nb = sum(p for rid, p in probs.items() if role_camps.get(rid) == "好人")

    if wolf_prob_nb == 0 or good_prob_nb == 0:
        return  # 避免除零

    # 混合策略：取朴素贝叶斯和ML模型的几何平均
    # 新狼人概率 ∝ sqrt(朴素贝叶斯狼人概率 × ML狼人概率)
    # 新好人概率 ∝ sqrt(朴素贝叶斯好人概率 × ML好人概率)
    new_wolf_prob = math.sqrt(wolf_prob_nb * wolf_prob_ml)
    new_good_prob = math.sqrt(good_prob_nb * good_prob_ml)

    # 归一化
    total = new_wolf_prob + new_good_prob
    if total == 0:
        return
    new_wolf_prob /= total
    new_good_prob /= total

    # 按比例调整各身份的概率
    for rid in role_ids:
        camp = role_camps.get(rid)
        if camp == "狼人" and wolf_prob_nb > 0:
            probs[rid] = probs[rid] * (new_wolf_prob / wolf_prob_nb)
        elif camp == "好人" and good_prob_nb > 0:
            probs[rid] = probs[rid] * (new_good_prob / good_prob_nb)
        # 第三方身份保持不变

    # 重新归一化
    total = sum(probs.values())
    if total > 0:
        for rid in role_ids:
            probs[rid] = round(probs[rid] / total, 6)

    # 更新最高概率身份
    top_role_id = max(probs, key=probs.get) if probs else None
    results[player_id]["top_role_id"] = top_role_id
    results[player_id]["top_role_name"] = role_names.get(top_role_id, "") if top_role_id else ""
    results[player_id]["top_probability"] = round(probs[top_role_id], 6) if top_role_id else 0.0


# ============================================================
# 主预测函数
# ============================================================
def predict_game(game_id, scenario_id=None):
    """主预测函数：根据对局中所有行为，预测每个玩家的身份概率

    算法步骤：
    1. 获取对局玩家列表
    2. 获取所有行为记录，按发起者分组
    3. 计算先验概率 P(身份)
    4. 获取算法权重 weight(身份,行为)，直接作为相对似然度 P(行为|身份) ∝ weight
    5. 对每个玩家：log后验 = log先验 + Σ log(weight(身份,该玩家的行为))
    6. 归一化得到概率
    7. 保存到 predictions 表（仅当无scenario_id时）

    参数:
        game_id: 对局ID
        scenario_id: 假设情景ID（可选）。如果提供，会应用情景中的假设身份，
                     且不保存到predictions表（情景预测不覆盖真实预测）

    返回:
        {
            player_id: {
                "player_id": int,
                "probabilities": {role_id: probability, ...},
                "top_role_id": int,
                "top_role_name": str,
                "top_probability": float
            },
            ...
        }
    """
    # 加载情景假设身份（如果有）
    scenario_assignments = {}
    if scenario_id:
        assignments = query_all(
            f"SELECT * FROM scenario_assignments WHERE scenario_id = {ph()}",
            (scenario_id,)
        )
        for a in assignments:
            scenario_assignments[a['player_id']] = {
                'role_id': a.get('role_id'),
                'camp': a.get('camp'),
                'confidence': a.get('confidence', 0.9)
            }

    # 1. 获取对局玩家
    # 获取对局版型信息（用于策略2：按版型自动调整查验可信度）
    game_info = query_one("SELECT setup_id FROM games WHERE id = " + ph(), (game_id,))
    setup_name = ""
    if game_info and game_info.get("setup_id"):
        setup = query_one("SELECT name FROM setups WHERE id = " + ph(), (game_info["setup_id"],))
        if setup:
            setup_name = setup["name"]
    check_reliability = get_check_reliability(setup_name)

    # 1. 获取对局玩家
    game_players = query_all(
        "SELECT gp.*, p.name as player_name FROM game_players gp "
        "JOIN players p ON gp.player_id = p.id "
        "WHERE gp.game_id = " + ph(),
        (game_id,)
    )
    if not game_players:
        return {}

    player_ids = [gp["player_id"] for gp in game_players]
    player_names = {gp["player_id"]: gp["player_name"] for gp in game_players}

    # 2. 获取所有行为记录，按发起者分组
    behaviors = query_all(
        "SELECT * FROM behavior_records WHERE game_id = " + ph(),
        (game_id,)
    )
    behaviors_by_actor = {}
    for b in behaviors:
        actor = b["actor_id"]
        if actor not in behaviors_by_actor:
            behaviors_by_actor[actor] = []
        behaviors_by_actor[actor].append(b)
    
    # 获取所有行为名称（用于行为结果状态修正）
    all_actions = query_all("SELECT id, name FROM actions")
    action_names = {a["id"]: a["name"] for a in all_actions}

    # 改进#第四阶段：构建个性化行为统计（基于所有已确认对局）
    personalized_stats, global_stats, player_game_counts = build_personalized_stats()

    # 改进#1：按目标分组的行为（用于修正目标玩家的概率）
    behaviors_by_target = {}
    for b in behaviors:
        target = b.get("target_id")
        if target:
            if target not in behaviors_by_target:
                behaviors_by_target[target] = []
            behaviors_by_target[target].append(b)

    # 3. 获取所有启用身份和行为
    all_roles = query_all("SELECT id, name, camp FROM roles WHERE is_active = TRUE")

    # 根据当前版型过滤身份：只保留版型中包含的身份
    setup_role_names = set()
    if game_info and game_info.get("setup_id"):
        setup = query_one("SELECT role_config FROM setups WHERE id = " + ph(), (game_info["setup_id"],))
        if setup and setup.get("role_config"):
            try:
                config = json.loads(setup["role_config"])
                setup_role_names = set(config.keys())
            except (json.JSONDecodeError, TypeError):
                pass

    # 如果版型有配置，则只保留版型中的身份；否则使用所有启用身份
    if setup_role_names:
        filtered_roles = [r for r in all_roles if r["name"] in setup_role_names]
        if filtered_roles:  # 确保过滤后至少有一个身份
            all_roles = filtered_roles

    role_ids = [r["id"] for r in all_roles]
    role_names = {r["id"]: r["name"] for r in all_roles}
    role_camps = {r["id"]: r["camp"] for r in all_roles}

    all_actions = query_all("SELECT id, name, default_weight, parent_id FROM actions WHERE is_active = TRUE")
    action_defaults = {a["id"]: a.get("default_weight", 1.0) for a in all_actions}

    # 构建行为父子关系：父行为ID -> 子行为ID列表
    parent_to_children = {}
    for a in all_actions:
        pid = a.get("parent_id")
        if pid:
            if pid not in parent_to_children:
                parent_to_children[pid] = []
            parent_to_children[pid].append(a["id"])

    if not role_ids or not all_actions:
        return {}

    # 4. 计算版型先验（作为基础先验）
    setup_prior = calculate_prior(game_id)

    # 5. 获取算法权重 {(action_id, role_id): {"weight": float, "sample_count": int}}
    weights = get_all_weights()
    weight_map = {k: v["weight"] for k, v in weights.items()}
    sample_count_map = {k: v.get("sample_count", 0) for k, v in weights.items()}

    # 6. 第一阶段：计算所有玩家的基础预测（不考虑目标信息）
    base_log_probs = {}  # 保存每个玩家的基础对数概率，用于第二阶段修正
    base_results = {}    # 保存每个玩家的基础概率分布，用于目标信息修正

    for player_id in player_ids:
        # 使用版型先验（身份是随机分配的，所有玩家先验一致）
        prior = setup_prior

        # 从先验开始（对数概率）
        log_probs = {}
        for rid in role_ids:
            p = prior.get(rid, 0.001)
            log_probs[rid] = math.log(max(p, 0.0001))

        # 累积该玩家作为发起者的行为
        actor_behaviors = behaviors_by_actor.get(player_id, [])
        for b in actor_behaviors:
            action_id = b["action_id"]
            default_w = action_defaults.get(action_id, 1.0)
            for rid in role_ids:
                # 获取有效权重：如果行为有子行为，使用子行为的综合权重（按样本数加权平均）
                children = parent_to_children.get(action_id, [])
                if children:
                    # 父行为：综合权重 = 子行为权重按sample_count加权平均
                    total_weighted = 0.0
                    total_samples = 0
                    for child_id in children:
                        child_w = weight_map.get((child_id, rid), action_defaults.get(child_id, 1.0))
                        child_samples = sample_count_map.get((child_id, rid), 0)
                        total_weighted += child_w * max(child_samples, 1)
                        total_samples += max(child_samples, 1)
                    w = total_weighted / total_samples if total_samples > 0 else default_w
                else:
                    # 子行为或一级行为：使用自己的独立权重
                    w = weight_map.get((action_id, rid), default_w)
                log_probs[rid] += math.log(max(w, 0.0001))
                
                # 改进：行为结果状态修正
                # 根据行为记录的result_status（correct/wrong）调整似然度
                result_status = b.get("result_status", "unconfirmed")
                if result_status != "unconfirmed":
                    action_name = action_names.get(action_id, "")
                    is_defend = "保" in action_name  # 保人类行为
                    is_attack = "踩" in action_name  # 踩人类行为
                    is_side = "站边" in action_name  # 站边行为
                    is_vote = "票" in action_name  # 投票行为
                    
                    # 确定修正强度
                    if is_defend or is_attack:
                        correct_factor = 1.5  # 保对/踩对：好人证据
                        wrong_factor = 1.5    # 保错/踩错：狼人证据
                    elif is_side or is_vote:
                        correct_factor = 1.3  # 站对/投对：好人证据
                        wrong_factor = 1.3    # 站错/投错：狼人证据
                    else:
                        correct_factor = 1.2
                        wrong_factor = 1.2
                    
                    if result_status == "correct":
                        # 行为正确：增加好人阵营的似然度
                        if role_camps.get(rid) == "好人":
                            log_probs[rid] += math.log(correct_factor)
                        else:
                            log_probs[rid] += math.log(1.0 / correct_factor)
                    elif result_status == "wrong":
                        # 行为错误：增加狼人阵营的似然度
                        if role_camps.get(rid) == "狼人":
                            log_probs[rid] += math.log(wrong_factor)
                        else:
                            log_probs[rid] += math.log(1.0 / wrong_factor)

                # 改进#第四阶段：个性化似然度修正
                # 根据该玩家历史对局中拿不同身份时的行为倾向，调整似然度
                personalized_factor = get_personalized_factor(
                    player_id, rid, action_id,
                    personalized_stats, global_stats, player_game_counts
                )
                if personalized_factor != 1.0:
                    log_probs[rid] += math.log(max(personalized_factor, 0.0001))

            # ---- 改进#2：利用"声明身份"信息 ----
            declared_role_id = b.get("actor_role_id")
            if declared_role_id and declared_role_id in role_camps:
                declared_camp = role_camps[declared_role_id]
                for rid in role_ids:
                    if rid == declared_role_id:
                        log_probs[rid] += math.log(2.0)       # 声明的身份 ×2
                    elif role_camps.get(rid) == declared_camp:
                        log_probs[rid] += math.log(1.2)       # 同阵营其他身份 ×1.2
                    else:
                        log_probs[rid] += math.log(0.5)       # 对立阵营 ×0.5

            # ---- 改进#2：利用"声明阵营"信息 ----
            declared_camp = b.get("actor_camp")
            if declared_camp:
                for rid in role_ids:
                    if role_camps.get(rid) == declared_camp:
                        log_probs[rid] += math.log(1.5)       # 同声明阵营 ×1.5
                    else:
                        log_probs[rid] += math.log(0.7)       # 不同阵营 ×0.7

        # 改进#6：行为组合模式修正（2-gram）- 在保存基础概率之前应用
        apply_combination_correction(player_id, log_probs, actor_behaviors, role_camps, role_ids)

        # 保存基础对数概率（用于第二阶段修正）
        base_log_probs[player_id] = dict(log_probs)

        # 归一化得到基础概率分布（用于目标信息修正时查询目标的概率）
        max_log = max(log_probs.values())
        base_probs = {}
        total = 0.0
        for rid in role_ids:
            p = math.exp(log_probs[rid] - max_log)
            base_probs[rid] = p
            total += p
        if total > 0:
            for rid in role_ids:
                base_probs[rid] = round(base_probs[rid] / total, 6)
        base_results[player_id] = {"probabilities": base_probs}

    # 7. 第二阶段：改进#1 - 利用行为目标信息修正预测
    results = {}
    for player_id in player_ids:
        # 从基础对数概率开始
        log_probs = dict(base_log_probs[player_id])

        # 应用目标信息修正（作为发起者）
        actor_behaviors = behaviors_by_actor.get(player_id, [])
        apply_target_info_correction(
            player_id, log_probs, actor_behaviors, base_results, role_camps, role_ids
        )

        # 改进#1（续）：应用目标信息修正（作为目标）- 方案B条件概率分解
        target_behaviors = behaviors_by_target.get(player_id, [])
        apply_target_as_target_correction(
            player_id, log_probs, target_behaviors, base_results, role_camps, role_ids, role_names, check_reliability
        )

        # 转换为概率并归一化（用 log-sum-exp 技巧）
        max_log = max(log_probs.values())
        probs = {}
        total = 0.0
        for rid in role_ids:
            p = math.exp(log_probs[rid] - max_log)
            probs[rid] = p
            total += p

        if total > 0:
            for rid in role_ids:
                probs[rid] = round(probs[rid] / total, 6)

        # 找出最高概率身份
        top_role_id = max(probs, key=probs.get) if probs else None
        top_probability = probs[top_role_id] if top_role_id else 0.0

        results[player_id] = {
            "player_id": player_id,
            "player_name": player_names.get(player_id, ""),
            "probabilities": probs,
            "top_role_id": top_role_id,
            "top_role_name": role_names.get(top_role_id, ""),
            "top_probability": round(top_probability, 6)
        }

    # 改进#7：玩家关系图修正（标签传播）- 在所有玩家个体预测完成后，全局修正阵营概率
    rel_matrix = build_relationship_matrix(behaviors, player_ids)
    apply_relationship_correction(results, rel_matrix, role_camps, role_ids, role_names)

    # 改进#第五阶段：ML模型修正（逻辑回归）- 如果模型已训练且样本足够，调整阵营概率
    for player_id in player_ids:
        actor_behaviors = behaviors_by_actor.get(player_id, [])
        apply_ml_correction(player_id, actor_behaviors, results, role_ids, role_camps, role_names)

    # 多情景推理：应用情景假设身份或阵营
    # 对于有假设的玩家：
    #   - 具体身份假设：将假设身份的概率设为置信度，其他身份按原比例分配剩余概率
    #   - 阵营假设：将假设阵营的总概率设为置信度，阵营内按原比例分配，其他阵营按原比例分配剩余
    if scenario_assignments:
        for player_id, assignment in scenario_assignments.items():
            if player_id not in results:
                continue
            assumed_role_id = assignment.get('role_id')
            assumed_camp = assignment.get('camp')
            confidence = assignment['confidence']
            probs = results[player_id]['probabilities']

            if assumed_role_id and assumed_role_id in probs:
                # 具体身份假设
                other_total = sum(p for rid, p in probs.items() if rid != assumed_role_id)
                if other_total > 0:
                    scale = (1 - confidence) / other_total
                    for rid in probs:
                        if rid != assumed_role_id:
                            probs[rid] = round(probs[rid] * scale, 6)
                    probs[assumed_role_id] = round(confidence, 6)
                else:
                    probs[assumed_role_id] = 1.0
            elif assumed_camp:
                # 阵营假设
                camp_role_ids = [rid for rid, camp in role_camps.items() if camp == assumed_camp]
                other_role_ids = [rid for rid, camp in role_camps.items() if camp != assumed_camp]
                camp_total = sum(probs.get(rid, 0) for rid in camp_role_ids)
                other_total = sum(probs.get(rid, 0) for rid in other_role_ids)

                if camp_total > 0 and other_total > 0:
                    # 阵营内按原比例分配confidence
                    camp_scale = confidence / camp_total
                    for rid in camp_role_ids:
                        probs[rid] = round(probs.get(rid, 0) * camp_scale, 6)
                    # 其他阵营按原比例分配(1-confidence)
                    other_scale = (1 - confidence) / other_total
                    for rid in other_role_ids:
                        probs[rid] = round(probs.get(rid, 0) * other_scale, 6)
                elif camp_total > 0:
                    # 只有假设阵营有概率，直接设为1
                    for rid in camp_role_ids:
                        probs[rid] = round(probs.get(rid, 0) / camp_total, 6) if camp_total > 0 else 0
                # 如果camp_total为0，保持原概率不变（无法应用假设）

            # 重新找出最高概率身份
            top_role_id = max(probs, key=probs.get)
            results[player_id]['top_role_id'] = top_role_id
            results[player_id]['top_role_name'] = role_names.get(top_role_id, "")
            results[player_id]['top_probability'] = round(probs[top_role_id], 6)
            results[player_id]['probabilities'] = probs

    # 应用确认身份（逻辑基点，置信度100%）
    # 确认身份是确定的事实，不是假设：
    #   - 具体身份确认：该身份概率设为100%，其他身份设为0%
    #   - 阵营确认：该阵营所有身份的总概率设为100%，阵营内按原比例分配
    confirmed_identities = query_all(
        f"SELECT * FROM game_confirmed_identities WHERE game_id = {ph()}",
        (game_id,)
    )
    if confirmed_identities:
        for ci in confirmed_identities:
            player_id = ci['player_id']
            if player_id not in results:
                continue
            confirmed_role_id = ci.get('role_id')
            confirmed_camp = ci.get('camp')
            probs = results[player_id]['probabilities']

            if confirmed_role_id and confirmed_role_id in probs:
                # 具体身份确认：100%确定
                for rid in probs:
                    probs[rid] = 1.0 if rid == confirmed_role_id else 0.0
            elif confirmed_camp:
                # 阵营确认：该阵营总概率100%，阵营内按原比例分配
                camp_role_ids = [rid for rid, camp in role_camps.items() if camp == confirmed_camp]
                camp_total = sum(probs.get(rid, 0) for rid in camp_role_ids)
                if camp_total > 0:
                    for rid in camp_role_ids:
                        probs[rid] = round(probs.get(rid, 0) / camp_total, 6)
                    for rid in probs:
                        if rid not in camp_role_ids:
                            probs[rid] = 0.0
                else:
                    # 阵营内原概率为0，平均分配
                    count = len(camp_role_ids)
                    if count > 0:
                        for rid in camp_role_ids:
                            probs[rid] = round(1.0 / count, 6)
                        for rid in probs:
                            if rid not in camp_role_ids:
                                probs[rid] = 0.0

            # 重新找出最高概率身份
            top_role_id = max(probs, key=probs.get)
            results[player_id]['top_role_id'] = top_role_id
            results[player_id]['top_role_name'] = role_names.get(top_role_id, "")
            results[player_id]['top_probability'] = round(probs[top_role_id], 6)
            results[player_id]['probabilities'] = probs
            # 标记为已确认
            results[player_id]['is_confirmed'] = True
            results[player_id]['confirmed_reason'] = ci.get('reason', '')

    # 通用身份唯一性推导：对于所有神职身份（预言家、女巫、猎人、守卫），如果有玩家被确认，其他对跳者大概率是狼
    try:
        role_ids_list = list(role_ids)
        results, role_uniqueness_log = apply_role_uniqueness(
            results, role_camps, role_ids_list, game_id
        )
        if role_uniqueness_log:
            results['_role_uniqueness_log'] = role_uniqueness_log
    except Exception as e:
        print(f"通用身份唯一性推导失败: {e}")
        import traceback
        traceback.print_exc()

    # 预言家查验推导：根据起跳玩家的预言家概率，调整被查验玩家的身份概率
    # 如果起跳玩家被确认为预言家（100%），则查验结果100%确定
    #   - 查杀目标 = 铁狼人（100%）
    #   - 金水目标 = 铁好人（100%）
    try:
        prophet_claims = get_prophet_claims(game_id)
        if prophet_claims:
            role_ids_list = list(role_ids)
            results, inference_result = apply_prophet_inference(
                results, role_camps, role_ids_list, prophet_claims
            )
            # 保存推导结果到结果中（用于前端展示）
            results['_prophet_inference_result'] = inference_result
    except Exception as e:
        print(f"预言家查验推导失败: {e}")
        import traceback
        traceback.print_exc()

    # 第二阶段高级推理：逻辑一致性与视角分析
    # 根据逻辑分析结果（矛盾、信息量溢出、逻辑链条）调整玩家身份概率
    try:
        from logic_analysis import analyze_game_logic
        logic_result = analyze_game_logic(game_id)
        player_suspicion = logic_result.get('player_suspicion', {})
        
        # 保存逻辑分析结果到结果中（用于前端展示）
        results['_logic_analysis_result'] = logic_result
        
        # 根据嫌疑分数调整玩家概率
        for player_id, suspicion_score in player_suspicion.items():
            if player_id not in results:
                continue
            # 跳过已确认身份的玩家
            if results[player_id].get('is_confirmed'):
                continue
            
            probs = results[player_id]['probabilities']
            
            # 嫌疑分数越高，狼人概率越大
            # 每1分嫌疑分数，狼人概率增加10%（相对调整）
            if suspicion_score > 0:
                werewolf_factor = 1.0 + (suspicion_score * 0.1)
                for rid in probs:
                    if role_camps.get(rid) == '狼人':
                        probs[rid] = probs[rid] * werewolf_factor
                    else:
                        probs[rid] = probs[rid] / werewolf_factor
                
                # 重新归一化
                total = sum(probs.values())
                if total > 0:
                    for rid in probs:
                        probs[rid] = round(probs[rid] / total, 6)
                
                # 重新找出最高概率身份
                top_role_id = max(probs, key=probs.get)
                results[player_id]['top_role_id'] = top_role_id
                results[player_id]['top_role_name'] = role_names.get(top_role_id, "")
                results[player_id]['top_probability'] = round(probs[top_role_id], 6)
                results[player_id]['probabilities'] = probs
                results[player_id]['suspicion_score'] = suspicion_score
    except Exception as e:
        print(f"逻辑分析集成失败: {e}")
        import traceback
        traceback.print_exc()

    # 8. 保存预测结果到数据库（仅当无scenario_id时，情景预测不覆盖真实预测）
    if not scenario_id:
        save_predictions(game_id, results)

    return results


def save_predictions(game_id, results):
    """保存预测结果到 predictions 表（先删后插）"""
    execute_write(f"DELETE FROM predictions WHERE game_id = {ph()}", (game_id,))

    for player_id, data in results.items():
        # 跳过非玩家ID的键（如'_prophet_inference_log'）
        if isinstance(player_id, str) and player_id.startswith('_'):
            continue
        for role_id, prob in data["probabilities"].items():
            execute_write(
                f"INSERT INTO predictions (game_id, player_id, role_id, probability) VALUES ({ph()}, {ph()}, {ph()}, {ph()})",
                (game_id, player_id, role_id, prob)
            )


def get_predictions(game_id):
    """获取某局的预测结果（从数据库读取）
    如果没有预测结果，自动调用 predict_game 生成
    """
    # 先尝试从数据库读取
    rows = query_all(
        "SELECT pr.*, p.name as player_name, r.name as role_name, r.camp as role_camp "
        "FROM predictions pr "
        "JOIN players p ON pr.player_id = p.id "
        "JOIN roles r ON pr.role_id = r.id "
        "WHERE pr.game_id = " + ph() + " ORDER BY pr.player_id, pr.probability DESC",
        (game_id,)
    )

    if not rows:
        # 没有预测结果，实时生成
        predict_game(game_id)
        rows = query_all(
            "SELECT pr.*, p.name as player_name, r.name as role_name, r.camp as role_camp "
            "FROM predictions pr "
            "JOIN players p ON pr.player_id = p.id "
            "JOIN roles r ON pr.role_id = r.id "
            "WHERE pr.game_id = " + ph() + " ORDER BY pr.player_id, pr.probability DESC",
            (game_id,)
        )

    # 按玩家分组
    result = {}
    for row in rows:
        pid = row["player_id"]
        if pid not in result:
            result[pid] = {
                "player_id": pid,
                "player_name": row["player_name"],
                "probabilities": [],
                "top_role_name": "",
                "top_probability": 0
            }
        result[pid]["probabilities"].append({
            "role_id": row["role_id"],
            "role_name": row["role_name"],
            "role_camp": row["role_camp"],
            "probability": row["probability"]
        })

    # 设置每个玩家的最高概率身份
    for pid, data in result.items():
        if data["probabilities"]:
            top = data["probabilities"][0]
            data["top_role_name"] = top["role_name"]
            data["top_probability"] = top["probability"]

    return list(result.values())


# ============================================================
# 算法自我优化
# ============================================================
def update_weights_from_game(game_id):
    """根据已确认对局的真实身份更新算法权重

    对每条行为记录：
      - 找到行为发起者的真实身份 R
      - weight(R, 行为) += 1
      - sample_count(R, 行为) += 1

    返回更新的行为条数
    """
    # 获取对局玩家的真实身份
    game_players = query_all(
        "SELECT player_id, actual_role_id FROM game_players WHERE game_id = " + ph(),
        (game_id,)
    )
    player_actual_role = {
        gp["player_id"]: gp["actual_role_id"]
        for gp in game_players
        if gp.get("actual_role_id")
    }

    if not player_actual_role:
        return 0

    # 获取所有行为记录
    behaviors = query_all(
        "SELECT actor_id, action_id FROM behavior_records WHERE game_id = " + ph(),
        (game_id,)
    )

    # 获取所有行为的默认权重
    all_actions = query_all("SELECT id, default_weight FROM actions")
    default_weights = {a["id"]: a.get("default_weight", 1.0) for a in all_actions}

    updated_count = 0
    for b in behaviors:
        actor_id = b["actor_id"]
        action_id = b["action_id"]
        actual_role_id = player_actual_role.get(actor_id)

        if actual_role_id:
            default_w = default_weights.get(action_id, 1.0)
            weight_record = get_or_create_weight(action_id, actual_role_id, default_w)

            # 改进#3：使用学习率更新，新数据始终有固定比例的影响力
            new_weight = weight_record["weight"] + LEARNING_RATE
            new_sample_count = weight_record["sample_count"] + 1

            execute_write(
                f"UPDATE algorithm_weights SET weight={ph()}, sample_count={ph()}, "
                f"updated_at=CURRENT_TIMESTAMP WHERE action_id={ph()} AND role_id={ph()}",
                (new_weight, new_sample_count, action_id, actual_role_id)
            )
            updated_count += 1

    # 改进#第四阶段：同时更新个性化行为统计（持久化存储）
    update_personalized_stats(game_id)

    # 改进#第五阶段：训练ML模型（逻辑回归，增量学习）
    try:
        train_ml_model_from_game(game_id)
    except Exception as e:
        print(f"[ML训练] 警告: 对局 {game_id} 训练失败: {e}")

    return updated_count


def score_predictions(game_id):
    """对局结束后，对比预测结果与真实身份，生成打分明细

    对每个玩家：
      - 预测的最高概率身份 vs 真实身份
      - 是否正确
      - 预测时的置信度（最高概率）

    返回打分结果列表
    """
    # 获取玩家真实身份
    game_players = query_all(
        "SELECT gp.player_id, gp.actual_role_id, p.name as player_name "
        "FROM game_players gp JOIN players p ON gp.player_id = p.id "
        "WHERE gp.game_id = " + ph(),
        (game_id,)
    )

    # 获取预测结果（最高概率身份）
    # 注意：DISTINCT ON 是 PostgreSQL 语法，SQLite 不支持
    # 改用 Python 处理：查询所有预测，按玩家取最高概率
    all_preds = query_all(
        "SELECT player_id, role_id, probability FROM predictions WHERE game_id = " + ph(),
        (game_id,)
    )
    top_preds = {}
    for p in all_preds:
        pid = p["player_id"]
        if pid not in top_preds or p["probability"] > top_preds[pid]["probability"]:
            top_preds[pid] = p

    # 清空旧的打分记录
    execute_write(f"DELETE FROM prediction_scores WHERE game_id = {ph()}", (game_id,))

    scores = []
    correct_count = 0
    for gp in game_players:
        pid = gp["player_id"]
        actual_role_id = gp["actual_role_id"]
        pred = top_preds.get(pid)
        predicted_role_id = pred["role_id"] if pred else None
        confidence = pred["probability"] if pred else 0
        is_correct = (predicted_role_id == actual_role_id) if actual_role_id else None

        if is_correct:
            correct_count += 1

        execute_write(
            f"INSERT INTO prediction_scores (game_id, player_id, predicted_role_id, actual_role_id, is_correct, confidence) "
            f"VALUES ({ph()}, {ph()}, {ph()}, {ph()}, {ph()}, {ph()})",
            (game_id, pid, predicted_role_id, actual_role_id, is_correct, confidence)
        )
        scores.append({
            "player_id": pid,
            "player_name": gp["player_name"],
            "predicted_role_id": predicted_role_id,
            "actual_role_id": actual_role_id,
            "is_correct": is_correct,
            "confidence": confidence
        })

    total = len(scores)
    accuracy = correct_count / total if total > 0 else 0

    return {
        "total_players": total,
        "correct_count": correct_count,
        "accuracy": round(accuracy, 4),
        "details": scores
    }
