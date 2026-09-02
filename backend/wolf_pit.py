"""
狼坑分析模块 - werewolf_4核心优点

核心功能：
1. 约束管理：用户录入或系统推算的狼坑约束（如"3/4/5里出2狼"）
2. 排除法：根据约束和已知身份，自动调整剩余玩家的狼人概率
3. 公共狼：多个狼坑集合的交集，交集玩家狼人概率大幅提升
4. 狼坑不够检测：某阵营的狼坑凑不够时，提示可能有倒钩狼或站错边
5. 概率修正：将狼坑分析结果应用到贝叶斯推理的身份概率上
"""
from sqlalchemy.orm import Session
from models import (
    Game, GamePlayer, WolfPitConstraint, Player, Identity,
    ConfirmedIdentity, Action, ActionType
)
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict
import json


def add_constraint(
    db: Session,
    game_id: int,
    player_ids: List[int],
    wolf_count: int,
    description: str = "",
    confidence: float = 1.0,
    source: str = "user",
    round_number: int = 1
) -> WolfPitConstraint:
    """添加一个狼坑约束"""
    constraint = WolfPitConstraint(
        game_id=game_id,
        player_ids=player_ids,
        wolf_count=wolf_count,
        description=description or f"{','.join(map(str, player_ids))}里出{wolf_count}狼"
    )
    db.add(constraint)
    db.commit()
    db.refresh(constraint)
    return constraint


def get_constraints(db: Session, game_id: int) -> List[WolfPitConstraint]:
    """获取某局的所有约束"""
    return db.query(WolfPitConstraint).filter(
        WolfPitConstraint.game_id == game_id
    ).order_by(WolfPitConstraint.created_at).all()


def delete_constraint(db: Session, constraint_id: int) -> bool:
    """删除一个约束"""
    constraint = db.query(WolfPitConstraint).filter(WolfPitConstraint.id == constraint_id).first()
    if constraint:
        db.delete(constraint)
        db.commit()
        return True
    return False


def parse_constraint(constraint: WolfPitConstraint) -> Tuple[List[int], int, float]:
    """解析约束，返回 (玩家ID列表, 狼人数, 置信度)"""
    player_ids = constraint.player_ids if isinstance(constraint.player_ids, list) else json.loads(constraint.player_ids)
    return player_ids, constraint.wolf_count, 1.0  # confidence默认1.0


def get_confirmed_wolves(db: Session, game_id: int) -> Set[int]:
    """获取已确认的狼人玩家ID集合"""
    wolves = set()
    
    # 从确认身份表获取
    confirmed = db.query(ConfirmedIdentity).filter(ConfirmedIdentity.game_id == game_id).all()
    identity_map = {i.id: i.name for i in db.query(Identity).all()}
    
    for c in confirmed:
        if c.identity_id:
            identity_name = identity_map.get(c.identity_id, "")
            if "狼" in identity_name:
                wolves.add(c.player_id)
        elif c.camp_only == "wolf":
            wolves.add(c.player_id)
    
    # 从自爆行为获取（宽松匹配：名称中包含"自爆"）
    self_explode_action_ids = [at.id for at in db.query(ActionType).all() 
                               if "自爆" in at.name]
    
    if self_explode_action_ids:
        self_explode_actions = db.query(Action).filter(
            Action.game_id == game_id,
            Action.action_type_id.in_(self_explode_action_ids)
        ).all()
        for action in self_explode_actions:
            wolves.add(action.player_id)
    
    return wolves


def get_confirmed_good(db: Session, game_id: int) -> Set[int]:
    """获取已确认的好人玩家ID集合"""
    good = set()
    
    confirmed = db.query(ConfirmedIdentity).filter(ConfirmedIdentity.game_id == game_id).all()
    identity_map = {i.id: i.name for i in db.query(Identity).all()}
    
    for c in confirmed:
        if c.identity_id:
            identity_name = identity_map.get(c.identity_id, "")
            if "狼" not in identity_name and "混血" not in identity_name:
                good.add(c.player_id)
        elif c.camp_only == "good":
            good.add(c.player_id)
    
    return good


def apply_constraints_to_probabilities(
    db: Session,
    game_id: int,
    base_probabilities: Dict[int, Dict[str, float]]
) -> Dict[int, Dict[str, float]]:
    """
    将狼坑约束应用到身份概率上，使用排除法修正
    
    核心逻辑：
    1. 对于每个约束"玩家集合S里有N只狼"
    2. 如果S中某些玩家已经被确认为好人，则剩余玩家的狼人概率提高
    3. 如果S中某些玩家已经被确认为狼人，则剩余玩家的狼人概率降低
    4. 公共狼（多个约束的交集）的狼人概率大幅提升
    """
    constraints = get_constraints(db, game_id)
    if not constraints:
        return base_probabilities
    
    confirmed_wolves = get_confirmed_wolves(db, game_id)
    confirmed_good = get_confirmed_good(db, game_id)
    
    # 计算每个玩家出现在多少个约束中，以及约束中的狼人数
    player_constraint_count = defaultdict(int)
    player_wolf_budget = defaultdict(float)
    
    for constraint in constraints:
        player_ids, wolf_count, confidence = parse_constraint(constraint)
        
        # 排除已确认的好人和狼人
        remaining_players = [pid for pid in player_ids if pid not in confirmed_good and pid not in confirmed_wolves]
        known_wolves = [pid for pid in player_ids if pid in confirmed_wolves]
        remaining_wolves = max(0, wolf_count - len(known_wolves))
        
        if len(remaining_players) > 0 and remaining_wolves > 0:
            # 剩余玩家平均分配狼人概率预算
            wolf_prob_per_player = remaining_wolves / len(remaining_players) * confidence
            
            for pid in remaining_players:
                player_constraint_count[pid] += 1
                player_wolf_budget[pid] += wolf_prob_per_player
    
    # 应用到概率上
    result = {}
    for player_id, probs in base_probabilities.items():
        new_probs = dict(probs)
        
        if player_id in player_wolf_budget:
            # 提高狼人身份的概率，降低好人身份的概率
            budget = player_wolf_budget[player_id]
            constraint_count = player_constraint_count[player_id]
            boost_factor = 1.0 + min(budget * 2.0, 1.0)  # 最多提升100%
            
            for identity_name in new_probs:
                if "狼" in identity_name:
                    new_probs[identity_name] *= boost_factor
                else:
                    new_probs[identity_name] /= boost_factor
            
            # 重新归一化
            total = sum(new_probs.values())
            if total > 0:
                new_probs = {k: v / total for k, v in new_probs.items()}
        
        result[player_id] = new_probs
    
    return result


def find_common_wolves(db: Session, game_id: int) -> List[Dict]:
    """
    找公共狼：多个狼坑集合的交集
    交集玩家狼人概率大幅提升
    """
    constraints = get_constraints(db, game_id)
    if len(constraints) < 2:
        return []
    
    confirmed_wolves = get_confirmed_wolves(db, game_id)
    player_map = {p.id: p.name for p in db.query(Player).all()}
    
    # 收集所有约束的玩家集合
    constraint_sets = []
    for constraint in constraints:
        player_ids, wolf_count, confidence = parse_constraint(constraint)
        if wolf_count > 0:
            constraint_sets.append(set(player_ids))
    
    if not constraint_sets:
        return []
    
    # 计算交集
    common = set.intersection(*constraint_sets) if constraint_sets else set()
    common = common - confirmed_wolves  # 排除已确认的狼人
    
    result = []
    for pid in common:
        result.append({
            "player_id": pid,
            "player_name": player_map.get(pid, f"玩家{pid}"),
            "constraint_count": len(constraint_sets),
            "confidence": min(0.9, 0.5 + len(constraint_sets) * 0.1)
        })
    
    return result


def detect_wolf_pit_insufficient(db: Session, game_id: int, total_wolves: int) -> Dict:
    """
    检测狼坑不够：某阵营的狼坑凑不够时，提示可能有倒钩狼或站错边
    
    参数：
    - total_wolves: 版型中狼人的总数
    """
    constraints = get_constraints(db, game_id)
    confirmed_wolves = get_confirmed_wolves(db, game_id)
    
    # 计算所有约束中能找到的狼人数
    found_wolves = set(confirmed_wolves)
    for constraint in constraints:
        player_ids, wolf_count, confidence = parse_constraint(constraint)
        # 如果约束中只有狼_count个玩家，那这些都是狼
        if len(player_ids) == wolf_count:
            found_wolves.update(player_ids)
    
    remaining_wolves = total_wolves - len(found_wolves)
    
    result = {
        "total_wolves": total_wolves,
        "found_wolves": len(found_wolves),
        "remaining_wolves": remaining_wolves,
        "is_insufficient": remaining_wolves > 0,
        "suggestion": "",
        "found_wolf_ids": list(found_wolves)
    }
    
    if remaining_wolves > 0:
        result["suggestion"] = (
            f"目前只找到{len(found_wolves)}只狼，还差{remaining_wolves}只。"
            f"可能存在倒钩狼（站边真预言家的狼人），或者有玩家站错边被误认为是好人。"
            f"建议重新审视站边真预言家的玩家，以及行为异常的玩家。"
        )
    
    return result


def analyze_wolf_pits(db: Session, game_id: int, total_wolves: int) -> Dict:
    """
    完整的狼坑分析
    """
    constraints = get_constraints(db, game_id)
    common_wolves = find_common_wolves(db, game_id)
    insufficient = detect_wolf_pit_insufficient(db, game_id, total_wolves)
    
    return {
        "constraints": [
            {
                "id": c.id,
                "player_ids": c.player_ids if isinstance(c.player_ids, list) else json.loads(c.player_ids),
                "wolf_count": c.wolf_count,
                "description": c.description,
                "confidence": 1.0,
                "source": "user",
                "round_number": 1
            }
            for c in constraints
        ],
        "common_wolves": common_wolves,
        "insufficient_detection": insufficient,
        "confirmed_wolves": list(get_confirmed_wolves(db, game_id)),
        "confirmed_good": list(get_confirmed_good(db, game_id))
    }
