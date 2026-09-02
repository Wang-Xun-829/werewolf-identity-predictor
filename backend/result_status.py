"""
行为结果状态推断 - werewolf_2优点
自动判断保对/保错、踩对/踩错、站对/站错等
"""
from sqlalchemy.orm import Session
from models import Action, ActionType, Player, Game, ConfirmedIdentity, Identity
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


def get_player_wolf_probability(db: Session, game_id: int, player_id: int) -> float:
    """估算某玩家是狼人的概率（基于确认身份和行为）"""
    # 检查是否有确认身份
    confirmed = db.query(ConfirmedIdentity).filter(
        ConfirmedIdentity.game_id == game_id,
        ConfirmedIdentity.player_id == player_id
    ).first()
    
    if confirmed:
        if confirmed.identity_id:
            identity = db.query(Identity).filter(Identity.id == confirmed.identity_id).first()
            if identity and "狼" in identity.name:
                return 1.0
            else:
                return 0.0
        elif confirmed.camp_only == "wolf":
            return 1.0
        elif confirmed.camp_only == "good":
            return 0.0
    
    # 检查是否有自爆行为
    self_explode = db.query(Action).filter(
        Action.game_id == game_id,
        Action.player_id == player_id,
        Action.action_type.has(name="自爆")
    ).first()
    if self_explode:
        return 1.0
    
    return 0.5  # 未知


def is_stance_action(action_type_name: str) -> bool:
    """判断是否是立场类行为（站边、保人、踩人等）"""
    stance_keywords = ["站边", "保人", "踩人", "投警徽票", "投放逐票"]
    return any(keyword in action_type_name for keyword in stance_keywords)


def infer_result_status(db: Session, game_id: int) -> Dict[int, str]:
    """
    推断所有行为的结果状态
    返回：{action_id: result_status}
    result_status: unknown、correct、incorrect
    """
    actions = db.query(Action).filter(Action.game_id == game_id).all()
    action_type_map = {at.id: at.name for at in db.query(ActionType).all()}
    
    result = {}
    
    for action in actions:
        action_name = action_type_map.get(action.action_type_id, "")
        target_id = action.target_player_id
        
        if not target_id or not is_stance_action(action_name):
            result[action.id] = "unknown"
            continue
        
        # 获取目标玩家的狼人概率
        target_wolf_prob = get_player_wolf_probability(db, game_id, target_id)
        
        if target_wolf_prob >= 0.9:
            # 目标基本确定是狼
            if "踩" in action_name or "查杀" in action_name or "投放逐票" in action_name:
                result[action.id] = "correct"  # 踩对了
            elif "保" in action_name or "金水" in action_name or "站边" in action_name:
                result[action.id] = "incorrect"  # 保错了
            else:
                result[action.id] = "unknown"
        elif target_wolf_prob <= 0.1:
            # 目标基本确定是好人
            if "踩" in action_name or "查杀" in action_name or "投放逐票" in action_name:
                result[action.id] = "incorrect"  # 踩错了
            elif "保" in action_name or "金水" in action_name or "站边" in action_name:
                result[action.id] = "correct"  # 保对了
            else:
                result[action.id] = "unknown"
        else:
            result[action.id] = "unknown"
    
    return result


def update_result_statuses(db: Session, game_id: int) -> int:
    """更新所有行为的结果状态，返回更新的数量"""
    result_map = infer_result_status(db, game_id)
    updated = 0
    
    for action_id, status in result_map.items():
        if status != "unknown":
            action = db.query(Action).filter(Action.id == action_id).first()
            if action and action.result_status != status:
                action.result_status = status
                updated += 1
    
    db.commit()
    return updated
