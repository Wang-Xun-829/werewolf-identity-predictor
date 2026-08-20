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

# ============================================================
# 算法超参数（可根据效果调整）
# ============================================================
LEARNING_RATE = 0.1  # 改进#3：权重更新学习率，新数据的影响力占比


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
                if total > 0:
                    # 版型中有该身份则按比例，没有则给极小值避免对数无穷
                    prior = {}
                    for rid in role_ids:
                        cnt = role_counts.get(rid, 0)
                        prior[rid] = cnt / total if cnt > 0 else 0.001
                    return prior
            except (json.JSONDecodeError, TypeError):
                pass

    # 均匀分布
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
# 主预测函数
# ============================================================
def predict_game(game_id):
    """主预测函数：根据对局中所有行为，预测每个玩家的身份概率

    算法步骤：
    1. 获取对局玩家列表
    2. 获取所有行为记录，按发起者分组
    3. 计算先验概率 P(身份)
    4. 获取算法权重 weight(身份,行为)，直接作为相对似然度 P(行为|身份) ∝ weight
    5. 对每个玩家：log后验 = log先验 + Σ log(weight(身份,该玩家的行为))
    6. 归一化得到概率
    7. 保存到 predictions 表

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
    role_ids = [r["id"] for r in all_roles]
    role_names = {r["id"]: r["name"] for r in all_roles}
    role_camps = {r["id"]: r["camp"] for r in all_roles}

    all_actions = query_all("SELECT id, name, default_weight FROM actions WHERE is_active = TRUE")
    action_defaults = {a["id"]: a.get("default_weight", 1.0) for a in all_actions}

    if not role_ids or not all_actions:
        return {}

    # 4. 计算版型先验（作为基础先验）
    setup_prior = calculate_prior(game_id)

    # 5. 获取算法权重 {(action_id, role_id): weight}
    weights = get_all_weights()
    weight_map = {k: v["weight"] for k, v in weights.items()}

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
                # 直接用 weight 作为相对似然度，不按身份归一化
                w = weight_map.get((action_id, rid), default_w)
                log_probs[rid] += math.log(max(w, 0.0001))

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

    # 8. 保存预测结果到数据库
    save_predictions(game_id, results)

    return results


def save_predictions(game_id, results):
    """保存预测结果到 predictions 表（先删后插）"""
    execute_write(f"DELETE FROM predictions WHERE game_id = {ph()}", (game_id,))

    for player_id, data in results.items():
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
