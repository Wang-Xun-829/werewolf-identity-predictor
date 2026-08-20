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

    # 3. 获取所有启用身份和行为
    all_roles = query_all("SELECT id, name, camp FROM roles WHERE is_active = TRUE")
    role_ids = [r["id"] for r in all_roles]
    role_names = {r["id"]: r["name"] for r in all_roles}

    all_actions = query_all("SELECT id, name, default_weight FROM actions WHERE is_active = TRUE")
    action_defaults = {a["id"]: a.get("default_weight", 1.0) for a in all_actions}

    if not role_ids or not all_actions:
        return {}

    # 4. 计算先验
    prior = calculate_prior(game_id)

    # 5. 获取算法权重 {(action_id, role_id): weight}
    weights = get_all_weights()
    weight_map = {k: v["weight"] for k, v in weights.items()}

    # 6. 对每个玩家计算后验
    results = {}
    for player_id in player_ids:
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

    # 7. 保存预测结果到数据库
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

            new_weight = weight_record["weight"] + 1
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
