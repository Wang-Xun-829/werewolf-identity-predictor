# -*- coding: utf-8 -*-
"""
梯度下降迭代学习引擎
==================
通过梯度下降算法自动优化预测算法的权重。

核心流程：
1. 对局结束后，获取真实身份
2. 用当前权重重跑最近20局，计算综合得分
3. 计算每个权重的梯度（数值梯度）
4. 沿梯度方向调整权重（自适应学习率）
5. 用新权重重跑历史对局，验证得分是否提高
6. 如果提高，保留新权重；如果没有提高，减小学习率继续尝试
7. 最多迭代3次，保留得分最高的权重

评估指标：
- 身份预测准确率（70%）：Top-1预测身份是否正确
- 阵营预测准确率（30%）：预测阵营（好人/狼人）是否正确
"""

import json
import math
import copy
import time
from datetime import datetime
from db import query_all, query_one, execute_write, ph, DB_TYPE


# ============================================================
# 超参数配置
# ============================================================
MAX_ITERATIONS = 3              # 最大迭代次数
INITIAL_LEARNING_RATE = 0.5    # 初始学习率
MIN_LEARNING_RATE = 0.01       # 最小学习率
LEARNING_RATE_DECAY = 0.5      # 学习率衰减系数（每次失败后减半）
GRADIENT_EPSILON = 0.01        # 数值梯度的微小变化量
WEIGHT_MIN = 0.1                # 权重最小值
WEIGHT_MAX = 10.0               # 权重最大值
HISTORY_GAMES = 20              # 使用最近多少局历史对局进行评估
SCORE_WEIGHT_ROLE = 0.7        # 身份预测准确率的权重
SCORE_WEIGHT_CAMP = 0.3        # 阵营预测准确率的权重
MIN_SCORE_IMPROVEMENT = 0.001  # 最小得分提升（小于这个值认为没有提升）


def ph():
    """参数占位符"""
    return '%s' if DB_TYPE == 'postgresql' else '?'


# ============================================================
# 权重管理
# ============================================================
def get_current_weights():
    """获取当前所有算法权重
    返回 {(action_id, role_id): weight}
    """
    rows = query_all("SELECT action_id, role_id, weight FROM algorithm_weights")
    return {(r['action_id'], r['role_id']): r['weight'] for r in rows}


def save_weights(weights, reason=''):
    """保存权重到数据库
    weights: {(action_id, role_id): weight}
    """
    for (action_id, role_id), weight in weights.items():
        # 限制权重范围
        weight = max(WEIGHT_MIN, min(WEIGHT_MAX, weight))
        execute_write(
            f"UPDATE algorithm_weights SET weight={ph()}, updated_at=CURRENT_TIMESTAMP "
            f"WHERE action_id={ph()} AND role_id={ph()}",
            (weight, action_id, role_id)
        )


def backup_weights(backup_name):
    """备份当前权重到权重历史表
    返回备份ID
    """
    # 检查权重历史表是否存在
    try:
        execute_write("""
            CREATE TABLE IF NOT EXISTS weight_backups (
                id SERIAL PRIMARY KEY,
                backup_name VARCHAR(100),
                backup_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                weights_data JSONB,
                score FLOAT,
                reason TEXT
            )
        """)
    except Exception:
        pass
    
    current_weights = get_current_weights()
    weights_json = json.dumps({f"{k[0]}_{k[1]}": v for k, v in current_weights.items()})
    
    # 使用execute_write执行INSERT，它会自动返回新插入的ID
    new_id = execute_write(
        f"INSERT INTO weight_backups (backup_name, weights_data, reason) "
        f"VALUES ({ph()}, {ph()}, {ph()})",
        (backup_name, weights_json, 'gradient_learning')
    )
    return new_id


def restore_weights(backup_id):
    """从备份恢复权重"""
    backup = query_one(f"SELECT * FROM weight_backups WHERE id={ph()}", (backup_id,))
    if not backup:
        return False
    
    # 处理weights_data：PostgreSQL的JSONB字段可能返回dict，也可能返回字符串
    weights_raw = backup['weights_data']
    if isinstance(weights_raw, dict):
        weights_data = weights_raw
    elif isinstance(weights_raw, str):
        weights_data = json.loads(weights_raw)
    else:
        weights_data = {}
    
    for key, weight in weights_data.items():
        action_id, role_id = map(int, key.split('_'))
        execute_write(
            f"UPDATE algorithm_weights SET weight={ph()}, updated_at=CURRENT_TIMESTAMP "
            f"WHERE action_id={ph()} AND role_id={ph()}",
            (weight, action_id, role_id)
        )
    return True


# ============================================================
# 学习日志
# ============================================================
def init_learning_log_table():
    """初始化学习日志表"""
    try:
        execute_write("""
            CREATE TABLE IF NOT EXISTS learning_logs (
                id SERIAL PRIMARY KEY,
                game_id INTEGER,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                initial_score FLOAT,
                final_score FLOAT,
                iterations INTEGER,
                status VARCHAR(20),
                details JSONB
            )
        """)
    except Exception:
        pass


def save_learning_log(log_data):
    """保存学习日志"""
    init_learning_log_table()
    details_json = json.dumps(log_data.get('details', {}))
    # 使用execute_write执行INSERT，它会自动返回新插入的ID
    new_id = execute_write(
        f"""INSERT INTO learning_logs 
            (game_id, initial_score, final_score, iterations, status, details)
            VALUES ({ph()}, {ph()}, {ph()}, {ph()}, {ph()}, {ph()})""",
        (
            log_data.get('game_id'),
            log_data.get('initial_score'),
            log_data.get('final_score'),
            log_data.get('iterations'),
            log_data.get('status'),
            details_json
        )
    )
    return new_id


# ============================================================
# 评估函数
# ============================================================
def get_recent_games(limit=HISTORY_GAMES):
    """获取最近的已确认对局
    返回 [game_id, ...]
    """
    rows = query_all(
        f"""SELECT id FROM games WHERE status = '已确认' 
            ORDER BY id DESC LIMIT {ph()}""",
        (limit,)
    )
    return [r['id'] for r in rows]


def evaluate_weights_on_game(weights, game_id):
    """在单个对局上评估权重
    返回 (role_accuracy, camp_accuracy, total_players)
    
    注意：这里使用简化版的预测算法，只基于权重计算似然度，
    不包含预言家推理、逻辑推理等复杂逻辑。
    这样可以更快地评估权重的效果。
    """
    # 获取对局玩家的真实身份
    game_players = query_all(
        f"""SELECT gp.player_id, gp.actual_role_id, r.camp as actual_camp
            FROM game_players gp
            LEFT JOIN roles r ON gp.actual_role_id = r.id
            WHERE gp.game_id = {ph()} AND gp.actual_role_id IS NOT NULL""",
        (game_id,)
    )
    
    if not game_players:
        return None
    
    # 获取所有身份
    all_roles = query_all("SELECT id, name, camp FROM roles WHERE is_active = TRUE")
    role_ids = [r['id'] for r in all_roles]
    role_camps = {r['id']: r['camp'] for r in all_roles}
    
    # 获取所有行为
    all_actions = query_all("SELECT id, default_weight FROM actions")
    action_ids = [a['id'] for a in all_actions]
    default_weights = {a['id']: a.get('default_weight', 1.0) for a in all_actions}
    
    # 获取对局的行为记录
    behaviors = query_all(
        f"""SELECT actor_id, action_id FROM behavior_records WHERE game_id = {ph()}""",
        (game_id,)
    )
    
    # 按玩家分组行为
    player_behaviors = {}
    for b in behaviors:
        actor_id = b['actor_id']
        if actor_id not in player_behaviors:
            player_behaviors[actor_id] = []
        player_behaviors[actor_id].append(b['action_id'])
    
    # 计算似然度表
    likelihood = {}
    for rid in role_ids:
        total_weight = 0.0
        for aid in action_ids:
            w = weights.get((aid, rid), default_weights.get(aid, 1.0))
            total_weight += w
        for aid in action_ids:
            w = weights.get((aid, rid), default_weights.get(aid, 1.0))
            if total_weight > 0:
                likelihood[(aid, rid)] = w / total_weight
            else:
                likelihood[(aid, rid)] = 1.0 / len(action_ids)
    
    # 对每个玩家进行预测
    role_correct = 0
    camp_correct = 0
    total_players = 0
    
    for gp in game_players:
        player_id = gp['player_id']
        actual_role_id = gp['actual_role_id']
        actual_camp = gp['actual_camp']
        
        if not actual_role_id:
            continue
        
        # 计算该玩家各身份的对数概率
        log_probs = {rid: 0.0 for rid in role_ids}
        player_actions = player_behaviors.get(player_id, [])
        
        for action_id in player_actions:
            for rid in role_ids:
                prob = likelihood.get((action_id, rid), 1.0 / len(action_ids))
                log_probs[rid] += math.log(max(prob, 1e-10))
        
        # 找出最高概率的身份
        predicted_role_id = max(log_probs, key=log_probs.get)
        predicted_camp = role_camps.get(predicted_role_id)
        
        # 统计准确率
        total_players += 1
        if predicted_role_id == actual_role_id:
            role_correct += 1
        if predicted_camp == actual_camp:
            camp_correct += 1
    
    if total_players == 0:
        return None
    
    return (
        role_correct / total_players,
        camp_correct / total_players,
        total_players
    )


def evaluate_weights(weights, game_ids=None):
    """在多个对局上评估权重
    返回综合得分（0-1之间，越高越好）
    
    综合得分 = 0.7 * 身份预测准确率 + 0.3 * 阵营预测准确率
    """
    if game_ids is None:
        game_ids = get_recent_games()
    
    if not game_ids:
        return 0.0
    
    total_role_correct = 0
    total_camp_correct = 0
    total_players = 0
    
    for game_id in game_ids:
        result = evaluate_weights_on_game(weights, game_id)
        if result:
            role_acc, camp_acc, players = result
            total_role_correct += role_acc * players
            total_camp_correct += camp_acc * players
            total_players += players
    
    if total_players == 0:
        return 0.0
    
    role_accuracy = total_role_correct / total_players
    camp_accuracy = total_camp_correct / total_players
    
    return SCORE_WEIGHT_ROLE * role_accuracy + SCORE_WEIGHT_CAMP * camp_accuracy


# ============================================================
# 梯度计算
# ============================================================
def calculate_gradient(weights, game_ids):
    """计算数值梯度
    返回 {(action_id, role_id): gradient}
    
    梯度 = (得分(权重+epsilon) - 得分(权重-epsilon)) / (2*epsilon)
    """
    gradient = {}
    weight_keys = list(weights.keys())
    
    # 为了提高效率，只对有数据的权重计算梯度
    # （权重在数据库中存在，说明至少有一个样本）
    for key in weight_keys:
        action_id, role_id = key
        original_weight = weights[key]
        
        # 权重+epsilon
        weights_plus = copy.deepcopy(weights)
        weights_plus[key] = min(WEIGHT_MAX, original_weight + GRADIENT_EPSILON)
        score_plus = evaluate_weights(weights_plus, game_ids)
        
        # 权重-epsilon
        weights_minus = copy.deepcopy(weights)
        weights_minus[key] = max(WEIGHT_MIN, original_weight - GRADIENT_EPSILON)
        score_minus = evaluate_weights(weights_minus, game_ids)
        
        # 计算梯度
        grad = (score_plus - score_minus) / (2 * GRADIENT_EPSILON)
        gradient[key] = grad
    
    return gradient


# ============================================================
# 迭代学习主函数
# ============================================================
def run_gradient_learning(game_id=None):
    """运行梯度下降迭代学习
    
    参数:
        game_id: 触发学习的对局ID（可选，用于日志记录）
    
    返回:
        {
            'initial_score': 初始得分,
            'final_score': 最终得分,
            'iterations': 迭代次数,
            'status': 'success' / 'no_improvement' / 'error',
            'details': {...}
        }
    """
    start_time = time.time()
    init_learning_log_table()
    
    # 1. 获取历史对局
    game_ids = get_recent_games()
    if len(game_ids) < 2:
        return {
            'status': 'error',
            'message': '历史对局太少，至少需要2局已确认对局',
            'iterations': 0
        }
    
    # 2. 备份当前权重
    backup_name = f"gradient_learning_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_id = backup_weights(backup_name)
    
    # 3. 获取当前权重和初始得分
    current_weights = get_current_weights()
    initial_score = evaluate_weights(current_weights, game_ids)
    
    best_weights = copy.deepcopy(current_weights)
    best_score = initial_score
    current_score = initial_score
    learning_rate = INITIAL_LEARNING_RATE
    iterations = 0
    iteration_details = []
    
    # 4. 迭代学习
    for iteration in range(MAX_ITERATIONS):
        iterations = iteration + 1
        print(f"[梯度学习] 第 {iteration + 1} 次迭代，当前得分: {current_score:.4f}，学习率: {learning_rate:.4f}")
        
        # 4.1 计算梯度
        gradient = calculate_gradient(current_weights, game_ids)
        
        # 4.2 尝试调整权重（如果失败，减小学习率重试）
        improved = False
        attempts = 0
        max_attempts = 3  # 每次迭代最多尝试3次不同的学习率
        
        while not improved and attempts < max_attempts and learning_rate >= MIN_LEARNING_RATE:
            attempts += 1
            
            # 调整权重
            new_weights = copy.deepcopy(current_weights)
            for key, grad in gradient.items():
                original = new_weights[key]
                adjusted = original + learning_rate * grad
                # 限制权重范围
                new_weights[key] = max(WEIGHT_MIN, min(WEIGHT_MAX, adjusted))
            
            # 评估新权重
            new_score = evaluate_weights(new_weights, game_ids)
            score_improvement = new_score - current_score
            
            print(f"[梯度学习]   尝试 {attempts}: 学习率={learning_rate:.4f}, 新得分={new_score:.4f}, 提升={score_improvement:.4f}")
            
            if score_improvement > MIN_SCORE_IMPROVEMENT:
                # 得分提高，保留新权重
                current_weights = new_weights
                current_score = new_score
                improved = True
                
                if new_score > best_score:
                    best_weights = copy.deepcopy(new_weights)
                    best_score = new_score
                
                iteration_details.append({
                    'iteration': iteration + 1,
                    'attempt': attempts,
                    'learning_rate': learning_rate,
                    'score_before': current_score - score_improvement,
                    'score_after': new_score,
                    'improvement': score_improvement,
                    'status': 'improved'
                })
            else:
                # 得分没有提高，减小学习率
                iteration_details.append({
                    'iteration': iteration + 1,
                    'attempt': attempts,
                    'learning_rate': learning_rate,
                    'score_before': current_score,
                    'score_after': new_score,
                    'improvement': score_improvement,
                    'status': 'no_improvement'
                })
                learning_rate *= LEARNING_RATE_DECAY
        
        # 如果连续多次没有提高，提前停止
        if not improved:
            print(f"[梯度学习] 第 {iteration + 1} 次迭代没有提高，停止迭代")
            break
    
    # 5. 保存最优权重
    save_weights(best_weights)
    
    # 6. 计算最终得分
    final_score = evaluate_weights(best_weights, game_ids)
    total_improvement = final_score - initial_score
    
    # 7. 记录日志
    end_time = time.time()
    log_data = {
        'game_id': game_id,
        'initial_score': initial_score,
        'final_score': final_score,
        'iterations': iterations,
        'status': 'success' if total_improvement > MIN_SCORE_IMPROVEMENT else 'no_improvement',
        'details': {
            'backup_id': backup_id,
            'total_time': end_time - start_time,
            'total_improvement': total_improvement,
            'iteration_details': iteration_details,
            'history_games_count': len(game_ids)
        }
    }
    save_learning_log(log_data)
    
    print(f"[梯度学习] 完成！初始得分: {initial_score:.4f}, 最终得分: {final_score:.4f}, 提升: {total_improvement:.4f}")
    
    return log_data


# ============================================================
# 查询学习历史
# ============================================================
def get_learning_history(limit=10):
    """获取最近的学习日志"""
    init_learning_log_table()
    try:
        rows = query_all(
            f"SELECT * FROM learning_logs ORDER BY id DESC LIMIT {ph()}",
            (limit,)
        )
        return rows
    except Exception:
        return []


def get_weight_backups(limit=10):
    """获取最近的权重备份"""
    try:
        rows = query_all(
            f"SELECT id, backup_name, backup_time, score, reason FROM weight_backups ORDER BY id DESC LIMIT {ph()}",
            (limit,)
        )
        return rows
    except Exception:
        return []


# ============================================================
# 手动触发学习
# ============================================================
if __name__ == '__main__':
    print("=" * 60)
    print("梯度下降迭代学习 - 手动运行")
    print("=" * 60)
    
    result = run_gradient_learning()
    
    print()
    print("=" * 60)
    print("学习结果:")
    print(f"  初始得分: {result.get('initial_score', 0):.4f}")
    print(f"  最终得分: {result.get('final_score', 0):.4f}")
    print(f"  提升: {result.get('final_score', 0) - result.get('initial_score', 0):.4f}")
    print(f"  迭代次数: {result.get('iterations', 0)}")
    print(f"  状态: {result.get('status', 'unknown')}")
    print("=" * 60)
