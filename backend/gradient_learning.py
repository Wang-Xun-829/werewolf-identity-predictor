"""
梯度下降迭代学习 - 优化版
对局结束后，通过梯度下降算法自动优化预测权重
性能优化：预加载所有对局数据到内存，避免重复数据库查询
"""
from sqlalchemy.orm import Session
from models import (
    Game, GamePlayer, Action, ActionType, Identity, IdentityWeight,
    ActionTypeWeight, LearningLog, WeightBackup
)
from typing import Dict, List, Optional, Tuple
import math
import copy
import json
import time
from datetime import datetime


# 超参数
MAX_ITERATIONS = 5  # 最多迭代5次
INITIAL_LEARNING_RATE = 0.3
MIN_LEARNING_RATE = 0.01
LEARNING_RATE_DECAY = 0.5
GRADIENT_EPSILON = 0.05
WEIGHT_MIN = 0.1
WEIGHT_MAX = 10.0
HISTORY_GAMES = 20  # 最近20局
SCORE_WEIGHT_ROLE = 0.7
SCORE_WEIGHT_CAMP = 0.3
MIN_SCORE_IMPROVEMENT = 0.001


# ==================== 数据预加载（性能优化核心） ====================

def preload_game_data(db: Session, game_ids: List[int]) -> Dict:
    """
    预加载所有对局数据到内存
    返回结构：
    {
        "identity_map": {identity_id: identity_name},
        "games": {
            game_id: {
                "players": [
                    {
                        "player_id": int,
                        "actual_identity_id": int,
                        "actual_identity_name": str,
                        "actual_camp": str,
                        "action_type_ids": [int, ...]
                    }
                ]
            }
        }
    }
    """
    start_time = time.time()
    
    # 1. 加载身份映射
    identity_map = {i.id: i.name for i in db.query(Identity).all()}
    
    # 2. 加载所有对局的玩家和行为
    games_data = {}
    
    for game_id in game_ids:
        # 加载玩家（有真实身份的）
        game_players = db.query(GamePlayer).filter(
            GamePlayer.game_id == game_id,
            GamePlayer.actual_identity_id.isnot(None)
        ).all()
        
        if not game_players:
            continue
        
        # 加载所有行为
        all_actions = db.query(Action).filter(
            Action.game_id == game_id
        ).all()
        
        # 按玩家分组行为
        player_actions = {}
        for action in all_actions:
            if action.player_id not in player_actions:
                player_actions[action.player_id] = []
            player_actions[action.player_id].append(action.action_type_id)
        
        # 构建玩家数据
        players_data = []
        for gp in game_players:
            actual_identity_id = gp.actual_identity_id
            actual_identity_name = identity_map.get(actual_identity_id, "")
            actual_camp = "wolf" if "狼" in actual_identity_name else ("third_party" if "混血" in actual_identity_name else "good")
            
            players_data.append({
                "player_id": gp.player_id,
                "actual_identity_id": actual_identity_id,
                "actual_identity_name": actual_identity_name,
                "actual_camp": actual_camp,
                "action_type_ids": player_actions.get(gp.player_id, [])
            })
        
        games_data[game_id] = {
            "players": players_data
        }
    
    elapsed = time.time() - start_time
    print(f"[梯度学习] 数据预加载完成：{len(games_data)}局，耗时 {elapsed:.2f}秒")
    
    return {
        "identity_map": identity_map,
        "games": games_data
    }


# ==================== 权重管理 ====================

def get_current_weights(db: Session) -> Dict[Tuple[int, int], float]:
    """获取当前所有行为默认权重"""
    weights = db.query(ActionTypeWeight).all()
    return {(w.action_type_id, w.identity_id): w.weight for w in weights}


def save_weights(db: Session, weights: Dict[Tuple[int, int], float]):
    """保存权重到数据库"""
    for (action_type_id, identity_id), weight in weights.items():
        weight = max(WEIGHT_MIN, min(WEIGHT_MAX, weight))
        record = db.query(ActionTypeWeight).filter(
            ActionTypeWeight.action_type_id == action_type_id,
            ActionTypeWeight.identity_id == identity_id
        ).first()
        if record:
            record.weight = weight
        else:
            new_record = ActionTypeWeight(
                action_type_id=action_type_id,
                identity_id=identity_id,
                weight=weight
            )
            db.add(new_record)
    db.commit()


def backup_weights(db: Session, backup_name: str) -> int:
    """备份当前权重"""
    weights = get_current_weights(db)
    weights_data = {f"{k[0]}_{k[1]}": v for k, v in weights.items()}
    
    backup = WeightBackup(
        backup_type="before_learning",
        weights_data=weights_data,
        score=0.0
    )
    db.add(backup)
    db.commit()
    db.refresh(backup)
    return backup.id


def restore_weights(db: Session, backup_id: int) -> bool:
    """从备份恢复权重"""
    backup = db.query(WeightBackup).filter(WeightBackup.id == backup_id).first()
    if not backup:
        return False
    
    weights_data = backup.weights_data
    if isinstance(weights_data, str):
        weights_data = json.loads(weights_data)
    
    for key, weight in weights_data.items():
        action_type_id, identity_id = map(int, key.split('_'))
        record = db.query(ActionTypeWeight).filter(
            ActionTypeWeight.action_type_id == action_type_id,
            ActionTypeWeight.identity_id == identity_id
        ).first()
        if record:
            record.weight = weight
    
    db.commit()
    return True


def get_recent_games(db: Session, limit: int = HISTORY_GAMES) -> List[int]:
    """获取最近的已确认对局"""
    games = db.query(Game).filter(
        Game.status == "已确认"
    ).order_by(Game.id.desc()).limit(limit).all()
    return [g.id for g in games]


# ==================== 权重评估（使用预加载数据，纯内存计算） ====================

def evaluate_weights_on_game_preloaded(
    weights: Dict[Tuple[int, int], float],
    game_data: Dict,
    identity_map: Dict[int, str]
) -> Optional[Tuple[float, float, int]]:
    """
    在单个对局上评估权重（使用预加载数据，纯内存计算）
    返回 (role_accuracy, camp_accuracy, total_players)
    """
    players = game_data.get("players", [])
    
    if not players:
        return None
    
    role_correct = 0
    camp_correct = 0
    total_players = 0
    
    for player in players:
        actual_identity_id = player["actual_identity_id"]
        actual_camp = player["actual_camp"]
        action_type_ids = player["action_type_ids"]
        
        # 计算各身份的对数概率
        log_probs = {}
        for identity_id, identity_name in identity_map.items():
            log_prob = 0.0
            for action_type_id in action_type_ids:
                weight = weights.get((action_type_id, identity_id), 1.0)
                log_prob += math.log(max(weight, 1e-10))
            log_probs[identity_id] = log_prob
        
        if not log_probs:
            continue
        
        # 找出最高概率的身份
        predicted_identity_id = max(log_probs, key=log_probs.get)
        predicted_identity_name = identity_map.get(predicted_identity_id, "")
        predicted_camp = "wolf" if "狼" in predicted_identity_name else ("third_party" if "混血" in predicted_identity_name else "good")
        
        total_players += 1
        if predicted_identity_id == actual_identity_id:
            role_correct += 1
        if predicted_camp == actual_camp:
            camp_correct += 1
    
    if total_players == 0:
        return None
    
    return role_correct / total_players, camp_correct / total_players, total_players


def evaluate_weights_preloaded(
    weights: Dict[Tuple[int, int], float],
    preloaded_data: Dict,
    game_ids: List[int]
) -> float:
    """评估权重在所有历史对局上的综合得分（使用预加载数据）"""
    total_role_correct = 0
    total_camp_correct = 0
    total_players = 0
    
    identity_map = preloaded_data["identity_map"]
    games = preloaded_data["games"]
    
    for game_id in game_ids:
        game_data = games.get(game_id)
        if not game_data:
            continue
        
        result = evaluate_weights_on_game_preloaded(weights, game_data, identity_map)
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


def calculate_gradient_preloaded(
    weights: Dict[Tuple[int, int], float],
    preloaded_data: Dict,
    game_ids: List[int]
) -> Dict[Tuple[int, int], float]:
    """计算数值梯度（使用预加载数据）"""
    gradient = {}
    
    for key in weights.keys():
        original_weight = weights[key]
        
        # 权重+epsilon
        weights_plus = copy.deepcopy(weights)
        weights_plus[key] = min(WEIGHT_MAX, original_weight + GRADIENT_EPSILON)
        score_plus = evaluate_weights_preloaded(weights_plus, preloaded_data, game_ids)
        
        # 权重-epsilon
        weights_minus = copy.deepcopy(weights)
        weights_minus[key] = max(WEIGHT_MIN, original_weight - GRADIENT_EPSILON)
        score_minus = evaluate_weights_preloaded(weights_minus, preloaded_data, game_ids)
        
        # 计算梯度
        grad = (score_plus - score_minus) / (2 * GRADIENT_EPSILON)
        gradient[key] = grad
    
    return gradient


# ==================== 主学习函数 ====================

def run_gradient_learning(db: Session, game_id: int = None) -> Dict:
    """运行梯度下降迭代学习（优化版：预加载数据）"""
    start_time = time.time()
    
    game_ids = get_recent_games(db)
    
    if len(game_ids) < 2:
        return {
            "status": "error",
            "message": "历史对局太少，至少需要2局已确认对局",
            "iterations": 0
        }
    
    print(f"[梯度学习] 开始学习，历史对局：{len(game_ids)}局，最大迭代：{MAX_ITERATIONS}次")
    
    # 预加载所有数据到内存（性能优化核心）
    preloaded_data = preload_game_data(db, game_ids)
    
    # 备份当前权重
    backup_name = f"gradient_learning_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    backup_id = backup_weights(db, backup_name)
    
    # 获取当前权重和初始得分
    current_weights = get_current_weights(db)
    initial_score = evaluate_weights_preloaded(current_weights, preloaded_data, game_ids)
    
    best_weights = copy.deepcopy(current_weights)
    best_score = initial_score
    current_score = initial_score
    learning_rate = INITIAL_LEARNING_RATE
    iterations = 0
    iteration_details = []
    
    # 迭代学习
    for iteration in range(MAX_ITERATIONS):
        iter_start = time.time()
        iterations = iteration + 1
        print(f"[梯度学习] 第 {iteration + 1}/{MAX_ITERATIONS} 次迭代，当前得分: {current_score:.4f}，学习率: {learning_rate:.4f}")
        
        # 计算梯度（使用预加载数据）
        gradient = calculate_gradient_preloaded(current_weights, preloaded_data, game_ids)
        
        # 尝试调整权重
        improved = False
        attempts = 0
        
        while not improved and attempts < 3 and learning_rate >= MIN_LEARNING_RATE:
            attempts += 1
            
            # 调整权重
            new_weights = copy.deepcopy(current_weights)
            for key, grad in gradient.items():
                original = new_weights[key]
                adjusted = original + learning_rate * grad
                new_weights[key] = max(WEIGHT_MIN, min(WEIGHT_MAX, adjusted))
            
            # 评估新权重（使用预加载数据）
            new_score = evaluate_weights_preloaded(new_weights, preloaded_data, game_ids)
            score_improvement = new_score - current_score
            
            iter_elapsed = time.time() - iter_start
            print(f"[梯度学习]   尝试 {attempts}: 学习率={learning_rate:.4f}, 新得分={new_score:.4f}, 提升={score_improvement:.4f}, 耗时={iter_elapsed:.2f}秒")
            
            iteration_details.append({
                "iteration": iteration + 1,
                "attempt": attempts,
                "learning_rate": learning_rate,
                "score_before": current_score,
                "score_after": new_score,
                "improvement": score_improvement,
                "status": "improved" if score_improvement > MIN_SCORE_IMPROVEMENT else "no_improvement"
            })
            
            if score_improvement > MIN_SCORE_IMPROVEMENT:
                current_weights = new_weights
                current_score = new_score
                improved = True
                
                if new_score > best_score:
                    best_weights = copy.deepcopy(new_weights)
                    best_score = new_score
            else:
                learning_rate *= LEARNING_RATE_DECAY
        
        if not improved:
            print(f"[梯度学习] 第 {iteration + 1} 次迭代没有提高，停止迭代")
            break
    
    # 保存最优权重
    save_weights(db, best_weights)
    
    # 计算最终得分
    final_score = evaluate_weights_preloaded(best_weights, preloaded_data, game_ids)
    total_improvement = final_score - initial_score
    
    total_elapsed = time.time() - start_time
    
    # 记录日志
    log = LearningLog(
        game_id=game_id,
        iteration=iterations,
        before_score=initial_score,
        after_score=final_score,
        improvement=total_improvement,
        learning_rate=learning_rate,
        details={
            "backup_id": backup_id,
            "total_improvement": total_improvement,
            "iteration_details": iteration_details,
            "history_games_count": len(game_ids),
            "total_time_seconds": total_elapsed,
            "status": "success" if total_improvement > MIN_SCORE_IMPROVEMENT else "no_improvement"
        }
    )
    db.add(log)
    db.commit()
    
    print(f"[梯度学习] 完成！初始得分: {initial_score:.4f}, 最终得分: {final_score:.4f}, 提升: {total_improvement:.4f}, 总耗时: {total_elapsed:.2f}秒")
    
    return {
        "status": "success",
        "initial_score": initial_score,
        "final_score": final_score,
        "improvement": total_improvement,
        "iterations": iterations,
        "backup_id": backup_id,
        "total_time_seconds": total_elapsed,
        "details": {
            "iteration_details": iteration_details,
            "history_games_count": len(game_ids)
        }
    }
