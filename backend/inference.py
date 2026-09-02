"""
贝叶斯推理引擎 - 融合werewolf_2和werewolf_4的优点

核心特性：
1. 先验概率从版型配置动态计算（werewolf_4优点）
2. 系统的默认行为权重表（werewolf_4优点）
3. 玩家个性化权重的平滑机制（werewolf_4优点）
4. 版型身份过滤，只预测当前版型包含的身份（werewolf_2优点）
5. 行为结果状态推断（werewolf_2优点）
"""
from sqlalchemy.orm import Session
from models import (
    Identity, Setup, SetupIdentity, ActionType, ActionTypeWeight,
    Player, Game, GamePlayer, Action, IdentityWeight, ConfirmedIdentity
)
from typing import Dict, List, Optional, Tuple
import math
from collections import defaultdict


# ==================== 默认行为权重表（融合werewolf_4的系统权重） ====================

DEFAULT_ACTION_WEIGHTS: Dict[str, Dict[str, float]] = {
    "跳预言家": {"预言家": 0.95, "狼人": 0.35, "狼王": 0.45, "狼美人": 0.25,
                "平民": 0.03, "女巫": 0.03, "猎人": 0.03, "白痴": 0.05,
                "骑士": 0.05, "守卫": 0.03, "混血儿": 0.05},
    "跳女巫": {"女巫": 0.75, "狼人": 0.15, "狼美人": 0.20, "狼王": 0.10,
              "平民": 0.02, "预言家": 0.02, "猎人": 0.02, "白痴": 0.02,
              "骑士": 0.02, "守卫": 0.02, "混血儿": 0.03},
    "跳猎人": {"猎人": 0.50, "狼人": 0.10, "狼王": 0.25, "狼美人": 0.05,
              "平民": 0.02, "预言家": 0.02, "女巫": 0.02, "白痴": 0.02,
              "骑士": 0.02, "守卫": 0.02, "混血儿": 0.03},
    "跳守卫": {"守卫": 0.30, "狼人": 0.08, "平民": 0.02, "预言家": 0.02,
              "女巫": 0.02, "猎人": 0.02, "白痴": 0.02, "骑士": 0.02,
              "狼王": 0.06, "狼美人": 0.05, "混血儿": 0.03},
    "跳骑士": {"骑士": 0.70, "狼人": 0.08, "狼王": 0.10, "平民": 0.02,
              "预言家": 0.02, "女巫": 0.02, "猎人": 0.02, "白痴": 0.02,
              "守卫": 0.02, "狼美人": 0.05, "混血儿": 0.03},
    "跳混子": {"混血儿": 0.40, "平民": 0.05, "狼人": 0.05, "预言家": 0.02,
              "女巫": 0.02, "猎人": 0.02, "白痴": 0.02, "骑士": 0.02,
              "守卫": 0.02, "狼王": 0.03, "狼美人": 0.03},
    "认民": {"平民": 0.70, "狼人": 0.40, "狼王": 0.35, "狼美人": 0.45,
            "预言家": 0.05, "女巫": 0.10, "猎人": 0.10, "白痴": 0.10,
            "骑士": 0.08, "守卫": 0.12, "混血儿": 0.20},
    "站边": {"预言家": 0.70, "狼人": 0.60, "狼王": 0.65, "狼美人": 0.50,
            "平民": 0.50, "女巫": 0.50, "猎人": 0.50, "白痴": 0.50,
            "骑士": 0.50, "守卫": 0.45, "混血儿": 0.60},
    "强势站边": {"预言家": 0.75, "狼人": 0.65, "狼王": 0.70, "狼美人": 0.55,
                "平民": 0.45, "女巫": 0.50, "猎人": 0.50, "白痴": 0.45,
                "骑士": 0.50, "守卫": 0.40, "混血儿": 0.55},
    "软站边": {"预言家": 0.60, "狼人": 0.55, "狼王": 0.55, "狼美人": 0.50,
              "平民": 0.55, "女巫": 0.55, "猎人": 0.55, "白痴": 0.55,
              "骑士": 0.55, "守卫": 0.50, "混血儿": 0.60},
    "不站边": {"狼人": 0.50, "狼王": 0.45, "狼美人": 0.55, "平民": 0.30,
              "预言家": 0.10, "女巫": 0.30, "猎人": 0.30, "白痴": 0.30,
              "骑士": 0.25, "守卫": 0.35, "混血儿": 0.35},
    "晃边": {"狼人": 0.45, "狼王": 0.40, "狼美人": 0.50, "平民": 0.35,
            "预言家": 0.15, "女巫": 0.30, "猎人": 0.30, "白痴": 0.30,
            "骑士": 0.25, "守卫": 0.35, "混血儿": 0.40},
    "踩人": {"狼人": 0.45, "狼王": 0.50, "狼美人": 0.40, "预言家": 0.40,
            "猎人": 0.35, "平民": 0.30, "女巫": 0.30, "白痴": 0.30,
            "骑士": 0.40, "守卫": 0.25, "混血儿": 0.35},
    "保人": {"狼人": 0.40, "狼王": 0.35, "狼美人": 0.50, "女巫": 0.30,
            "预言家": 0.25, "平民": 0.25, "猎人": 0.20, "白痴": 0.25,
            "骑士": 0.20, "守卫": 0.25, "混血儿": 0.35},
    "弃票": {"狼人": 0.30, "狼王": 0.25, "狼美人": 0.30, "平民": 0.15,
            "白痴": 0.15, "女巫": 0.10, "猎人": 0.10, "预言家": 0.05,
            "骑士": 0.08, "守卫": 0.12, "混血儿": 0.20},
    "划水": {"狼人": 0.50, "狼王": 0.45, "狼美人": 0.45, "平民": 0.20,
            "白痴": 0.20, "女巫": 0.15, "猎人": 0.15, "预言家": 0.05,
            "骑士": 0.15, "守卫": 0.25, "混血儿": 0.30},
    "自爆": {"狼人": 1.00, "狼王": 1.00, "狼美人": 1.00,
            "预言家": 0.00, "平民": 0.00, "女巫": 0.00, "猎人": 0.00,
            "白痴": 0.00, "骑士": 0.00, "守卫": 0.00, "混血儿": 0.00},
    "认狼": {"狼人": 0.98, "狼王": 0.98, "狼美人": 0.98,
            "预言家": 0.01, "平民": 0.02, "女巫": 0.01, "猎人": 0.01,
            "白痴": 0.01, "骑士": 0.01, "守卫": 0.01, "混血儿": 0.02},
    "金水": {"预言家": 0.90, "平民": 0.30, "女巫": 0.20, "猎人": 0.15,
            "白痴": 0.15, "骑士": 0.15, "守卫": 0.15, "混血儿": 0.15,
            "狼人": 0.05, "狼王": 0.05, "狼美人": 0.05},
    "查杀": {"预言家": 0.85, "狼人": 0.40, "狼王": 0.45, "狼美人": 0.35,
            "平民": 0.05, "女巫": 0.05, "猎人": 0.05, "白痴": 0.05,
            "骑士": 0.05, "守卫": 0.05, "混血儿": 0.05},
    "银水": {"女巫": 0.90, "平民": 0.40, "预言家": 0.20, "猎人": 0.15,
            "白痴": 0.15, "骑士": 0.15, "守卫": 0.10, "混血儿": 0.20,
            "狼人": 0.10, "狼王": 0.10, "狼美人": 0.10},
}

GENERIC_DEFAULT_WEIGHT = 0.1


# ==================== 辅助函数 ====================

def get_identity_name_map(db: Session) -> Dict[int, str]:
    """获取 identity_id -> name 映射"""
    identities = db.query(Identity).filter(Identity.is_active == True).all()
    return {ident.id: ident.name for ident in identities}


def get_identity_id_map(db: Session) -> Dict[str, int]:
    """获取 name -> identity_id 映射"""
    identities = db.query(Identity).filter(Identity.is_active == True).all()
    return {ident.name: ident.id for ident in identities}


def get_setup_identity_ids(db: Session, setup_id: Optional[int]) -> List[int]:
    """获取版型包含的身份ID列表（werewolf_2优点：版型身份过滤）"""
    if not setup_id:
        return [r.id for r in db.query(Identity).filter(Identity.is_active == True).all()]
    
    setup_identities = db.query(SetupIdentity).filter(SetupIdentity.setup_id == setup_id).all()
    return [si.identity_id for si in setup_identities]


# ==================== 先验概率（werewolf_4优点：从版型配置动态计算） ====================

def get_prior_probabilities(db: Session, game_id: int) -> Dict[int, float]:
    """
    根据对局使用的版型配置动态计算先验概率
    返回：{identity_id: probability}
    """
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        return {}
    
    identity_name_map = get_identity_name_map(db)
    player_count = game.player_count or 12
    
    # 优先从版型配置读取
    if game.setup_id:
        setup_identities = db.query(SetupIdentity).filter(
            SetupIdentity.setup_id == game.setup_id
        ).all()
        if setup_identities:
            priors = {}
            for si in setup_identities:
                priors[si.identity_id] = si.count / player_count
            return priors
    
    # 没有版型配置，用通用比例
    wolf_count = max(1, int(player_count / 3))
    god_count = 3 if player_count <= 9 else 4
    villager_count = player_count - wolf_count - god_count
    villager_count = max(0, villager_count)
    
    priors = {}
    id_map = get_identity_id_map(db)
    
    if "狼人" in id_map:
        priors[id_map["狼人"]] = wolf_count / player_count
    if "平民" in id_map:
        priors[id_map["平民"]] = villager_count / player_count
    
    god_identities = ["预言家", "女巫", "猎人", "白痴"]
    for i, gname in enumerate(god_identities[:god_count]):
        if gname in id_map:
            priors[id_map[gname]] = 1.0 / player_count
    
    # 其他身份默认概率很小
    for ident_id in identity_name_map.keys():
        if ident_id not in priors:
            priors[ident_id] = 0.01
    
    return priors


# ==================== 行为权重获取（融合双方优点） ====================

def get_action_default_weight(db: Session, action_type_name: str, identity_name: str) -> float:
    """
    获取某个行为对某身份的默认条件概率 P(行为|身份)
    优先查数据库配置，没有则回退到硬编码默认值，再没有用通用值
    """
    # 1. 从数据库查
    action_type = db.query(ActionType).filter(ActionType.name == action_type_name).first()
    identity = db.query(Identity).filter(Identity.name == identity_name).first()
    
    if action_type and identity:
        weight_config = db.query(ActionTypeWeight).filter(
            ActionTypeWeight.action_type_id == action_type.id,
            ActionTypeWeight.identity_id == identity.id
        ).first()
        if weight_config:
            return weight_config.weight
    
    # 2. 回退到硬编码默认值
    if action_type_name in DEFAULT_ACTION_WEIGHTS:
        return DEFAULT_ACTION_WEIGHTS[action_type_name].get(identity_name, GENERIC_DEFAULT_WEIGHT)
    
    # 3. 通用默认值
    return GENERIC_DEFAULT_WEIGHT


def get_action_weight(
    db: Session,
    player_id: int,
    action_type_name: str,
    identity_name: str,
    result_status: str = "unknown"
) -> float:
    """
    获取某个玩家在某行为下某身份的条件概率 P(行为|身份)
    融合werewolf_4的平滑机制 + werewolf_2的结果状态修正
    
    平滑机制：alpha = min(sample_count / 10.0, 0.8)
    final_weight = default_weight * (1 - alpha) + learned_weight * alpha
    
    结果状态修正：
    - correct（保对/踩对）：好人权重提升，狼人权重降低
    - incorrect（保错/踩错）：狼人权重提升，好人权重降低
    """
    id_map = get_identity_id_map(db)
    identity_id = id_map.get(identity_name)
    
    # 1. 获取默认权重
    default_w = get_action_default_weight(db, action_type_name, identity_name)
    
    # 2. 如果有玩家个性化权重，用平滑机制混合（werewolf_4优点）
    if identity_id:
        action_type = db.query(ActionType).filter(ActionType.name == action_type_name).first()
        if action_type:
            weight_record = db.query(IdentityWeight).filter(
                IdentityWeight.player_id == player_id,
                IdentityWeight.action_type_id == action_type.id,
                IdentityWeight.identity_id == identity_id
            ).first()
            
            if weight_record and weight_record.sample_count >= 3:
                alpha = min(weight_record.sample_count / 10.0, 0.8)
                final_w = default_w * (1 - alpha) + weight_record.weight * alpha
            else:
                final_w = default_w
        else:
            final_w = default_w
    else:
        final_w = default_w
    
    # 3. 结果状态修正（werewolf_2优点）
    if result_status == "correct":
        # 保对/踩对：好人权重提升，狼人权重降低
        if "狼" in identity_name:
            final_w *= 0.5
        else:
            final_w *= 1.5
    elif result_status == "incorrect":
        # 保错/踩错：狼人权重提升，好人权重降低
        if "狼" in identity_name:
            final_w *= 1.5
        else:
            final_w *= 0.5
    
    return final_w


# ==================== 贝叶斯更新 ====================

def bayesian_update(
    current_probs: Dict[int, float],
    action_type_name: str,
    result_status: str = "unknown",
    db: Session = None,
    player_id: int = None,
    allowed_identity_ids: List[int] = None
) -> Dict[int, float]:
    """
    贝叶斯更新：根据一个行为更新身份概率
    P(身份|行为) = P(行为|身份) × P(身份) / P(行为)
    """
    new_probs = {}
    evidence = 0.0
    
    identity_name_map = get_identity_name_map(db) if db else {}
    
    for identity_id in current_probs.keys():
        # 版型身份过滤（werewolf_2优点）
        if allowed_identity_ids and identity_id not in allowed_identity_ids:
            new_probs[identity_id] = 0.0
            continue
        
        identity_name = identity_name_map.get(identity_id, f"身份{identity_id}")
        
        if db and player_id:
            likelihood = get_action_weight(db, player_id, action_type_name, identity_name, result_status)
        else:
            likelihood = DEFAULT_ACTION_WEIGHTS.get(action_type_name, {}).get(identity_name, GENERIC_DEFAULT_WEIGHT)
        
        prior = current_probs.get(identity_id, 0.01)
        new_probs[identity_id] = prior * likelihood
        evidence += new_probs[identity_id]
    
    if evidence > 0:
        for identity_id in new_probs:
            new_probs[identity_id] = new_probs[identity_id] / evidence
    
    return new_probs


# ==================== 确认身份修正（werewolf_2优点：逻辑基点） ====================

def apply_confirmed_identities(
    db: Session,
    game_id: int,
    current_probs: Dict[int, Dict[int, float]]
) -> Dict[int, Dict[int, float]]:
    """
    应用确认身份（逻辑基点）：
    - 如果某玩家身份已确认，则该身份概率=1，其他=0
    - 如果某玩家阵营已确认，则该阵营身份概率提升，其他降低
    """
    confirmed = db.query(ConfirmedIdentity).filter(ConfirmedIdentity.game_id == game_id).all()
    
    for c in confirmed:
        if c.player_id not in current_probs:
            continue
        
        if c.identity_id:
            # 确认具体身份
            for ident_id in current_probs[c.player_id]:
                current_probs[c.player_id][ident_id] = 1.0 if ident_id == c.identity_id else 0.0
        elif c.camp_only:
            # 只确认阵营
            identity_name_map = get_identity_name_map(db)
            for ident_id in current_probs[c.player_id]:
                ident_name = identity_name_map.get(ident_id, "")
                if c.camp_only == "good" and "狼" not in ident_name:
                    current_probs[c.player_id][ident_id] *= 2.0
                elif c.camp_only == "wolf" and "狼" in ident_name:
                    current_probs[c.player_id][ident_id] *= 2.0
                else:
                    current_probs[c.player_id][ident_id] *= 0.5
            
            # 归一化
            total = sum(current_probs[c.player_id].values())
            if total > 0:
                for ident_id in current_probs[c.player_id]:
                    current_probs[c.player_id][ident_id] /= total
    
    return current_probs


# ==================== 主预测函数 ====================

def predict_player_identity(
    db: Session,
    game_id: int,
    player_id: int,
    allowed_identity_ids: List[int] = None
) -> Dict[int, float]:
    """推测单个玩家的身份概率分布"""
    # 1. 获取先验概率（werewolf_4优点：从版型配置动态计算）
    probs = get_prior_probabilities(db, game_id)
    
    if not probs:
        return {}
    
    # 2. 版型身份过滤（werewolf_2优点）
    if allowed_identity_ids:
        probs = {k: v for k, v in probs.items() if k in allowed_identity_ids}
        # 重新归一化
        total = sum(probs.values())
        if total > 0:
            probs = {k: v / total for k, v in probs.items()}
    
    # 3. 获取该玩家在本局的所有行为
    actions = db.query(Action).filter(
        Action.game_id == game_id,
        Action.player_id == player_id
    ).order_by(Action.round_number, Action.created_at).all()
    
    # 4. 获取行为类型名称映射
    action_type_map = {}
    for at in db.query(ActionType).all():
        action_type_map[at.id] = at.name
    
    # 5. 逐个行为做贝叶斯更新
    for action in actions:
        action_name = action_type_map.get(action.action_type_id, "")
        if not action_name:
            continue
        
        # 如果是子行为，也考虑父行为的影响
        parent_name = None
        action_type = db.query(ActionType).filter(ActionType.id == action.action_type_id).first()
        if action_type and action_type.parent_id:
            parent = db.query(ActionType).filter(ActionType.id == action_type.parent_id).first()
            if parent:
                parent_name = parent.name
        
        # 先应用父行为
        if parent_name:
            probs = bayesian_update(probs, parent_name, action.result_status, db, player_id, allowed_identity_ids)
        
        # 再应用子行为
        probs = bayesian_update(probs, action_name, action.result_status, db, player_id, allowed_identity_ids)
    
    return probs


def predict_game_identities(db: Session, game_id: int) -> List[Dict]:
    """推测整局游戏所有玩家的身份概率"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        return []
    
    # 获取版型包含的身份（werewolf_2优点：版型身份过滤）
    allowed_identity_ids = get_setup_identity_ids(db, game.setup_id)
    
    game_players = db.query(GamePlayer).filter(
        GamePlayer.game_id == game_id
    ).order_by(GamePlayer.seat_number).all()
    
    # 先计算所有玩家的基础预测
    all_probs = {}
    for gp in game_players:
        probs = predict_player_identity(db, game_id, gp.player_id, allowed_identity_ids)
        all_probs[gp.player_id] = probs
    
    # 应用确认身份（逻辑基点）
    all_probs = apply_confirmed_identities(db, game_id, all_probs)
    
    identity_name_map = get_identity_name_map(db)
    
    results = []
    for gp in game_players:
        player = db.query(Player).filter(Player.id == gp.player_id).first()
        if not player:
            continue
        
        probs = all_probs.get(gp.player_id, {})
        
        if probs:
            # 转换为身份名称->概率的格式
            probs_with_names = {identity_name_map.get(k, str(k)): v for k, v in probs.items()}
            sorted_probs = sorted(probs_with_names.items(), key=lambda x: x[1], reverse=True)
            top_guess = sorted_probs[0][0]
            confidence = sorted_probs[0][1]
            
            # 阵营预测
            top_identity_id = max(probs, key=probs.get)
            camp = "wolf" if "狼" in top_guess else ("third_party" if "混血" in top_guess else "good")
        else:
            probs_with_names = {}
            top_guess = "未知"
            confidence = 0.0
            camp = None
            top_identity_id = None
        
        results.append({
            "player_id": gp.player_id,
            "player_name": player.name,
            "seat_number": gp.seat_number,
            "predictions": probs_with_names,
            "top_guess": top_guess,
            "top_identity_id": top_identity_id,
            "confidence": round(confidence, 4),
            "camp_prediction": camp
        })
    
    return results
