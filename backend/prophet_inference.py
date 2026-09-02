"""
预言家查验链推导 - werewolf_2优点
支持复杂的查验链推导，包括：
- A给B金水，B又跳预言家给C查杀的链式关系
- 确认A为预言家后，自动推导B、C的身份
- 对跳预言家的双边分析
"""
from sqlalchemy.orm import Session
from models import Action, ActionType, Player, Game, ConfirmedIdentity, Identity, GamePlayer
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


def get_prophet_claims(db: Session, game_id: int) -> List[Dict]:
    """获取所有跳预言家的玩家及其查验信息"""
    action_type_map = {at.id: at.name for at in db.query(ActionType).all()}
    
    # 找所有跳预言家的行为（宽松匹配：名称中包含"跳预言家"或"起跳预言家"）
    prophet_action_ids = [at.id for at in db.query(ActionType).all() 
                          if "预言家" in at.name and ("跳" in at.name or "起跳" in at.name)]
    
    if not prophet_action_ids:
        return []
    
    jump_actions = db.query(Action).filter(
        Action.game_id == game_id,
        Action.action_type_id.in_(prophet_action_ids)
    ).all()
    
    prophets = []
    for action in jump_actions:
        prophet_id = action.player_id
        
        # 找该玩家的所有查验行为（宽松匹配：名称中包含"金水"或"查杀"）
        check_action_ids = [at.id for at in db.query(ActionType).all() 
                           if "金水" in at.name or "查杀" in at.name]
        
        if check_action_ids:
            check_actions = db.query(Action).filter(
                Action.game_id == game_id,
                Action.player_id == prophet_id,
                Action.action_type_id.in_(check_action_ids)
            ).order_by(Action.round_number, Action.created_at).all()
        else:
            check_actions = []
        
        checks = []
        for ca in check_actions:
            check_type = action_type_map.get(ca.action_type_id, "")
            is_gold = "金水" in check_type
            checks.append({
                "target_id": ca.target_player_id,
                "is_gold": is_gold,
                "round": ca.round_number,
                "phase": ca.phase
            })
        
        prophets.append({
            "prophet_id": prophet_id,
            "checks": checks,
            "jump_round": action.round_number
        })
    
    return prophets


def analyze_check_chain(db: Session, game_id: int) -> Dict:
    """
    分析查验链
    返回：{
        "prophets": [...],  # 所有预言家候选人
        "derived_facts": [...],  # 推导出来的事实
        "contradictions": [...],  # 矛盾点
        "common_wolves": [...],  # 公共狼（所有视角都认为是狼的）
        "common_good": [...]  # 公共好人（所有视角都认为是好人的）
    }
    """
    prophets = get_prophet_claims(db, game_id)
    player_map = {p.id: p.name for p in db.query(Player).all()}
    
    derived_facts = []
    contradictions = []
    
    # 检查是否有确认的预言家
    confirmed_prophet = None
    confirmed = db.query(ConfirmedIdentity).filter(
        ConfirmedIdentity.game_id == game_id,
        ConfirmedIdentity.identity.has(name="预言家")
    ).first()
    if confirmed:
        confirmed_prophet = confirmed.player_id
    
    # 如果有确认的预言家，推导所有查验结果
    if confirmed_prophet:
        for prophet in prophets:
            if prophet["prophet_id"] == confirmed_prophet:
                for check in prophet["checks"]:
                    target_name = player_map.get(check["target_id"], f"玩家{check['target_id']}")
                    if check["is_gold"]:
                        derived_facts.append({
                            "type": "gold_water",
                            "prophet_id": confirmed_prophet,
                            "target_id": check["target_id"],
                            "description": f"预言家给{target_name}金水 → {target_name}是好人",
                            "confidence": 1.0
                        })
                    else:
                        derived_facts.append({
                            "type": "check_kill",
                            "prophet_id": confirmed_prophet,
                            "target_id": check["target_id"],
                            "description": f"预言家查杀{target_name} → {target_name}是狼人",
                            "confidence": 1.0
                        })
    
    # 分析对跳预言家
    if len(prophets) >= 2:
        # 检查是否有自爆的预言家候选人（宽松匹配：名称中包含"自爆"）
        self_explode_action_ids = [at.id for at in db.query(ActionType).all() 
                                   if "自爆" in at.name]
        
        for prophet in prophets:
            if self_explode_action_ids:
                self_explode = db.query(Action).filter(
                    Action.game_id == game_id,
                    Action.player_id == prophet["prophet_id"],
                    Action.action_type_id.in_(self_explode_action_ids)
                ).first()
            else:
                self_explode = None
            if self_explode:
                prophet_name = player_map.get(prophet["prophet_id"], "")
                derived_facts.append({
                    "type": "false_prophet",
                    "prophet_id": prophet["prophet_id"],
                    "description": f"{prophet_name}自爆 → {prophet_name}是假预言家（狼人）",
                    "confidence": 1.0
                })
                
                # 推导其他预言家候选人是真预言家
                for other in prophets:
                    if other["prophet_id"] != prophet["prophet_id"]:
                        other_name = player_map.get(other["prophet_id"], "")
                        derived_facts.append({
                            "type": "true_prophet",
                            "prophet_id": other["prophet_id"],
                            "description": f"{prophet_name}自爆 → {other_name}是真预言家",
                            "confidence": 0.9
                        })
    
    # 计算公共狼和公共好人
    wolf_votes = defaultdict(int)
    good_votes = defaultdict(int)
    
    for prophet in prophets:
        for check in prophet["checks"]:
            if check["is_gold"]:
                good_votes[check["target_id"]] += 1
            else:
                wolf_votes[check["target_id"]] += 1
    
    common_wolves = [pid for pid, count in wolf_votes.items() if count >= len(prophets)]
    common_good = [pid for pid, count in good_votes.items() if count >= len(prophets)]
    
    # 检查查验链矛盾
    for i, p1 in enumerate(prophets):
        for j, p2 in enumerate(prophets):
            if i >= j:
                continue
            # 检查是否有同一个玩家被一个给金水，一个给查杀
            p1_targets = {c["target_id"]: c["is_gold"] for c in p1["checks"]}
            p2_targets = {c["target_id"]: c["is_gold"] for c in p2["checks"]}
            
            for target_id in p1_targets:
                if target_id in p2_targets and p1_targets[target_id] != p2_targets[target_id]:
                    target_name = player_map.get(target_id, "")
                    contradictions.append({
                        "type": "check_contradiction",
                        "target_id": target_id,
                        "prophet_1": p1["prophet_id"],
                        "prophet_2": p2["prophet_id"],
                        "description": f"玩家{target_name}被一个预言家给金水，另一个给查杀，存在矛盾"
                    })
    
    return {
        "prophets": prophets,
        "derived_facts": derived_facts,
        "contradictions": contradictions,
        "common_wolves": common_wolves,
        "common_good": common_good
    }
