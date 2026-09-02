"""
游戏流程管理 - werewolf_2优点
完整的游戏阶段流转、玩家状态管理、投票权过滤、投票结果计算
"""
from sqlalchemy.orm import Session
from models import Game, GamePlayer, PlayerStatus, Action, ActionType
from typing import Dict, List, Optional, Tuple
from datetime import datetime


# 游戏阶段定义
GAME_PHASES = [
    "未开始",
    "第一夜-夜间行动",
    "第一天-警上发言",
    "第一天-警徽投票",
    "第一天-退水自爆",
    "第一天-死讯公布",
    "第一天-警下发言",
    "第一天-放逐投票",
    "第一天-PK发言",
    "第一天-遗言",
    "第二夜-夜间行动",
    "第二天-死讯公布",
    "第二天-白天发言",
    "第二天-放逐投票",
    "第二天-PK发言",
    "第二天-遗言",
]


def get_current_phase(db: Session, game_id: int) -> Dict:
    """获取对局当前阶段"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        return {"phase": "未知", "round": 1}
    
    return {
        "phase": game.current_phase,
        "round": game.current_round,
        "status": game.status
    }


def advance_phase(db: Session, game_id: int, custom_phase: str = None) -> Dict:
    """
    进入下一个阶段
    如果指定custom_phase，则直接跳转到该阶段
    """
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        return {"success": False, "error": "对局不存在"}
    
    if custom_phase:
        game.current_phase = custom_phase
    else:
        # 简单的阶段推进逻辑
        current = game.current_phase
        if current == "未开始":
            game.current_phase = "第一夜-夜间行动"
        elif "夜间行动" in current:
            round_num = game.current_round
            if round_num == 1:
                game.current_phase = "第一天-警上发言"
            else:
                game.current_phase = f"第{round_num}天-死讯公布"
        elif "警上发言" in current:
            game.current_phase = "第一天-警徽投票"
        elif "警徽投票" in current:
            game.current_phase = "第一天-退水自爆"
        elif "退水自爆" in current:
            game.current_phase = "第一天-死讯公布"
        elif "死讯公布" in current:
            round_num = game.current_round
            if round_num == 1:
                game.current_phase = "第一天-警下发言"
            else:
                game.current_phase = f"第{round_num}天-白天发言"
        elif "发言" in current and "PK" not in current:
            round_num = game.current_round
            game.current_phase = f"第{round_num}天-放逐投票"
        elif "放逐投票" in current:
            round_num = game.current_round
            game.current_phase = f"第{round_num}天-遗言"
        elif "遗言" in current:
            game.current_round += 1
            game.current_phase = f"第{game.current_round}夜-夜间行动"
        elif "PK发言" in current:
            round_num = game.current_round
            game.current_phase = f"第{round_num}天-放逐投票"
    
    db.commit()
    
    return {
        "success": True,
        "phase": game.current_phase,
        "round": game.current_round
    }


def wolf_self_explode(db: Session, game_id: int, player_id: int) -> Dict:
    """
    狼人自爆：直接进入下一个黑夜
    """
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        return {"success": False, "error": "对局不存在"}
    
    # 记录自爆行为
    action_type = db.query(ActionType).filter(ActionType.name == "自爆").first()
    if action_type:
        action = Action(
            game_id=game_id,
            player_id=player_id,
            action_type_id=action_type.id,
            round_number=game.current_round,
            phase=game.current_phase,
            notes="狼人自爆"
        )
        db.add(action)
    
    # 更新玩家状态
    status = db.query(PlayerStatus).filter(
        PlayerStatus.game_id == game_id,
        PlayerStatus.player_id == player_id
    ).first()
    if status:
        status.is_alive = False
        status.death_type = "self_explode"
        status.death_round = game.current_round
    
    # 进入下一个黑夜
    game.current_round += 1
    game.current_phase = f"第{game.current_round}夜-夜间行动"
    
    db.commit()
    
    return {
        "success": True,
        "player_id": player_id,
        "phase": game.current_phase,
        "round": game.current_round
    }


def init_game_phase(db: Session, game_id: int) -> Dict:
    """初始化对局阶段"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        return {"success": False, "error": "对局不存在"}
    
    game.current_phase = "未开始"
    game.current_round = 1
    
    # 初始化所有玩家状态
    game_players = db.query(GamePlayer).filter(GamePlayer.game_id == game_id).all()
    for gp in game_players:
        existing = db.query(PlayerStatus).filter(
            PlayerStatus.game_id == game_id,
            PlayerStatus.player_id == gp.player_id
        ).first()
        if not existing:
            status = PlayerStatus(
                game_id=game_id,
                player_id=gp.player_id,
                is_on_police=False,
                is_retired=False,
                is_alive=True
            )
            db.add(status)
    
    db.commit()
    
    return {"success": True, "phase": game.current_phase, "round": game.current_round}


def update_player_status(
    db: Session,
    game_id: int,
    player_id: int,
    is_on_police: bool = None,
    is_retired: bool = None,
    is_alive: bool = None,
    death_type: str = None,
    death_round: int = None
) -> Dict:
    """更新玩家状态"""
    status = db.query(PlayerStatus).filter(
        PlayerStatus.game_id == game_id,
        PlayerStatus.player_id == player_id
    ).first()
    
    if not status:
        status = PlayerStatus(
            game_id=game_id,
            player_id=player_id,
            is_on_police=False,
            is_retired=False,
            is_alive=True
        )
        db.add(status)
        db.flush()
    
    if is_on_police is not None:
        status.is_on_police = is_on_police
    if is_retired is not None:
        status.is_retired = is_retired
    if is_alive is not None:
        status.is_alive = is_alive
    if death_type is not None:
        status.death_type = death_type
    if death_round is not None:
        status.death_round = death_round
    
    db.commit()
    
    return {
        "success": True,
        "player_id": player_id,
        "is_on_police": status.is_on_police,
        "is_retired": status.is_retired,
        "is_alive": status.is_alive,
        "death_type": status.death_type
    }


def get_eligible_voters(db: Session, game_id: int, vote_type: str) -> List[int]:
    """
    获取有投票权的玩家ID列表
    
    vote_type:
    - "police": 警徽投票，只有未上警的玩家可以投
    - "exile": 放逐投票，只有存活的玩家可以投
    - "pk": PK投票，除了PK台上的玩家之外的玩家可以投
    """
    statuses = db.query(PlayerStatus).filter(PlayerStatus.game_id == game_id).all()
    status_map = {s.player_id: s for s in statuses}
    
    eligible = []
    for s in statuses:
        if vote_type == "police":
            # 警徽投票：只有未上警的玩家可以投
            if not s.is_on_police and s.is_alive:
                eligible.append(s.player_id)
        elif vote_type == "exile":
            # 放逐投票：只有存活的玩家可以投
            if s.is_alive:
                eligible.append(s.player_id)
        elif vote_type == "pk":
            # PK投票：除了PK台上的玩家之外的存活玩家
            # PK台玩家需要通过参数排除，这里先返回所有存活玩家
            if s.is_alive:
                eligible.append(s.player_id)
    
    return eligible


def calculate_vote_result(db: Session, game_id: int, vote_type: str) -> Dict:
    """
    计算投票结果
    返回：{
        "votes": {player_id: count},  # 每个玩家的得票数
        "max_votes": int,  # 最高票数
        "elected": [player_id],  # 得票最多的玩家（可能多人平票）
        "is_tie": bool,  # 是否平票
        "eligible_voters": [player_id]  # 有投票权的玩家
    }
    """
    # 获取投票行为
    action_type_name = "投警徽票" if vote_type == "police" else "投放逐票"
    action_type = db.query(ActionType).filter(ActionType.name == action_type_name).first()
    
    if not action_type:
        return {"success": False, "error": f"找不到行为类型: {action_type_name}"}
    
    votes = db.query(Action).filter(
        Action.game_id == game_id,
        Action.action_type_id == action_type.id
    ).all()
    
    # 统计得票
    vote_count = {}
    for vote in votes:
        target_id = vote.target_player_id
        if target_id:
            vote_count[target_id] = vote_count.get(target_id, 0) + 1
    
    if not vote_count:
        return {
            "success": True,
            "votes": {},
            "max_votes": 0,
            "elected": [],
            "is_tie": False,
            "eligible_voters": get_eligible_voters(db, game_id, vote_type)
        }
    
    max_votes = max(vote_count.values())
    elected = [pid for pid, count in vote_count.items() if count == max_votes]
    is_tie = len(elected) > 1
    
    return {
        "success": True,
        "votes": vote_count,
        "max_votes": max_votes,
        "elected": elected,
        "is_tie": is_tie,
        "eligible_voters": get_eligible_voters(db, game_id, vote_type)
    }
