"""
狼人杀身份预测系统 - FastAPI主程序
融合werewolf_2和werewolf_4的所有功能
"""
import os
import sys
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from database import get_db, init_db, engine
from models import (
    Faction, Identity, Setup, SetupIdentity, ActionType, Player, Game,
    GamePlayer, Action, ConfirmedIdentity, WolfPitConstraint, Prediction,
    PlayerStatus, LearningLog
)
from schemas import *

# 获取项目根目录
backend_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(backend_dir)
frontend_dir = os.path.join(project_dir, "frontend")

app = FastAPI(title="狼人杀身份预测系统", version="5.0.0")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
if os.path.exists(frontend_dir):
    app.mount("/static", StaticFiles(directory=frontend_dir), name="static")

# 启动时初始化数据库
@app.on_event("startup")
def startup_event():
    init_db()
    print("数据库初始化完成")


# ==================== 首页 ====================

@app.get("/")
def read_root():
    """首页"""
    index_path = os.path.join(frontend_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "狼人杀身份预测系统 API", "docs": "/docs"}


@app.get("/health")
def health_check():
    """健康检查"""
    return {"status": "ok", "version": "5.0.0"}


# ==================== 阵营管理 ====================

@app.get("/api/factions", response_model=List[FactionOut])
def list_factions(db: Session = Depends(get_db)):
    return db.query(Faction).order_by(Faction.id).all()


@app.post("/api/factions", response_model=FactionOut)
def create_faction(faction: FactionCreate, db: Session = Depends(get_db)):
    db_faction = Faction(**faction.dict())
    db.add(db_faction)
    db.commit()
    db.refresh(db_faction)
    return db_faction


# ==================== 身份管理 ====================

@app.get("/api/identities", response_model=List[IdentityOut])
def list_identities(db: Session = Depends(get_db)):
    identities = db.query(Identity).filter(Identity.is_active == True).order_by(Identity.id).all()
    result = []
    for ident in identities:
        out = IdentityOut.from_orm(ident)
        out.faction_name = ident.faction.name if ident.faction else None
        result.append(out)
    return result


@app.post("/api/identities", response_model=IdentityOut)
def create_identity(identity: IdentityCreate, db: Session = Depends(get_db)):
    db_identity = Identity(**identity.dict())
    db.add(db_identity)
    db.commit()
    db.refresh(db_identity)
    return db_identity


@app.put("/api/identities/{identity_id}", response_model=IdentityOut)
def update_identity(identity_id: int, identity: IdentityUpdate, db: Session = Depends(get_db)):
    db_identity = db.query(Identity).filter(Identity.id == identity_id).first()
    if not db_identity:
        raise HTTPException(status_code=404, detail="身份不存在")
    for key, value in identity.dict(exclude_unset=True).items():
        setattr(db_identity, key, value)
    db.commit()
    db.refresh(db_identity)
    return db_identity


@app.delete("/api/identities/{identity_id}")
def delete_identity(identity_id: int, db: Session = Depends(get_db)):
    db_identity = db.query(Identity).filter(Identity.id == identity_id).first()
    if not db_identity:
        raise HTTPException(status_code=404, detail="身份不存在")
    db_identity.is_active = False
    db.commit()
    return {"success": True, "message": "身份已删除"}


# ==================== 版型管理 ====================

@app.get("/api/setups", response_model=List[SetupOut])
def list_setups(db: Session = Depends(get_db)):
    from sqlalchemy.orm import joinedload
    setups = db.query(Setup).options(
        joinedload(Setup.setup_identities).joinedload(SetupIdentity.identity)
    ).order_by(Setup.id).all()
    result = []
    for setup in setups:
        # 手动构建identities字段
        identities = []
        for si in setup.setup_identities:
            identity_name = si.identity.name if si.identity else None
            identities.append({
                "id": si.id,
                "identity_id": si.identity_id,
                "identity_name": identity_name,
                "count": si.count
            })
        result.append({
            "id": setup.id,
            "name": setup.name,
            "player_count": setup.player_count,
            "description": setup.description,
            "identities": identities,
            "created_at": setup.created_at
        })
    return result


@app.post("/api/setups", response_model=SetupOut)
def create_setup(setup: SetupCreate, db: Session = Depends(get_db)):
    setup_data = setup.dict()
    identities_data = setup_data.pop("identities", [])
    db_setup = Setup(**setup_data)
    db.add(db_setup)
    db.flush()
    
    for si in identities_data:
        db_si = SetupIdentity(setup_id=db_setup.id, **si)
        db.add(db_si)
    
    db.commit()
    db.refresh(db_setup)
    
    # 手动构建返回对象
    identities = []
    for si in db_setup.setup_identities:
        identity_name = si.identity.name if si.identity else None
        identities.append({
            "id": si.id,
            "identity_id": si.identity_id,
            "identity_name": identity_name,
            "count": si.count
        })
    return {
        "id": db_setup.id,
        "name": db_setup.name,
        "player_count": db_setup.player_count,
        "description": db_setup.description,
        "identities": identities,
        "created_at": db_setup.created_at
    }


@app.put("/api/setups/{setup_id}", response_model=SetupOut)
def update_setup(setup_id: int, setup: SetupUpdate, db: Session = Depends(get_db)):
    db_setup = db.query(Setup).filter(Setup.id == setup_id).first()
    if not db_setup:
        raise HTTPException(status_code=404, detail="版型不存在")
    
    update_data = setup.dict(exclude_unset=True)
    identities_data = update_data.pop("identities", None)
    
    # 更新基本信息
    for key, value in update_data.items():
        setattr(db_setup, key, value)
    
    # 更新身份配置
    if identities_data is not None:
        # 删除旧的身份配置
        db.query(SetupIdentity).filter(SetupIdentity.setup_id == setup_id).delete()
        # 添加新的身份配置
        for si in identities_data:
            db_si = SetupIdentity(setup_id=setup_id, **si)
            db.add(db_si)
    
    db.commit()
    db.refresh(db_setup)
    
    # 手动构建返回对象
    identities = []
    for si in db_setup.setup_identities:
        identity_name = si.identity.name if si.identity else None
        identities.append({
            "id": si.id,
            "identity_id": si.identity_id,
            "identity_name": identity_name,
            "count": si.count
        })
    return {
        "id": db_setup.id,
        "name": db_setup.name,
        "player_count": db_setup.player_count,
        "description": db_setup.description,
        "identities": identities,
        "created_at": db_setup.created_at
    }


@app.delete("/api/setups/{setup_id}")
def delete_setup(setup_id: int, db: Session = Depends(get_db)):
    db_setup = db.query(Setup).filter(Setup.id == setup_id).first()
    if not db_setup:
        raise HTTPException(status_code=404, detail="版型不存在")
    db.delete(db_setup)
    db.commit()
    return {"success": True, "message": "版型已删除"}


# ==================== 行为管理 ====================

@app.get("/api/action_types")
def list_action_types(db: Session = Depends(get_db)):
    # 返回所有行为（包括子行为），前端自己构建层级
    all_actions = db.query(ActionType).order_by(ActionType.sort_order, ActionType.id).all()
    result = []
    for action in all_actions:
        out = ActionTypeOut.from_orm(action)
        result.append(out)
    return result


@app.post("/api/action_types", response_model=ActionTypeOut)
def create_action_type(action: ActionTypeCreate, db: Session = Depends(get_db)):
    db_action = ActionType(**action.dict())
    db.add(db_action)
    db.commit()
    db.refresh(db_action)
    return db_action


@app.put("/api/action_types/{action_id}", response_model=ActionTypeOut)
def update_action_type(action_id: int, action: ActionTypeUpdate, db: Session = Depends(get_db)):
    db_action = db.query(ActionType).filter(ActionType.id == action_id).first()
    if not db_action:
        raise HTTPException(status_code=404, detail="行为不存在")
    for key, value in action.dict(exclude_unset=True).items():
        setattr(db_action, key, value)
    db.commit()
    db.refresh(db_action)
    return db_action


@app.delete("/api/action_types/{action_id}")
def delete_action_type(action_id: int, db: Session = Depends(get_db)):
    db_action = db.query(ActionType).filter(ActionType.id == action_id).first()
    if not db_action:
        raise HTTPException(status_code=404, detail="行为不存在")
    db.delete(db_action)
    db.commit()
    return {"success": True, "message": "行为已删除"}


# ==================== 玩家管理 ====================

@app.get("/api/players", response_model=List[PlayerOut])
def list_players(db: Session = Depends(get_db)):
    return db.query(Player).order_by(Player.id).all()


@app.post("/api/players", response_model=PlayerOut)
def create_player(player: PlayerCreate, db: Session = Depends(get_db)):
    db_player = Player(**player.dict())
    db.add(db_player)
    db.commit()
    db.refresh(db_player)
    return db_player


@app.put("/api/players/{player_id}", response_model=PlayerOut)
def update_player(player_id: int, player: PlayerUpdate, db: Session = Depends(get_db)):
    db_player = db.query(Player).filter(Player.id == player_id).first()
    if not db_player:
        raise HTTPException(status_code=404, detail="玩家不存在")
    for key, value in player.dict(exclude_unset=True).items():
        setattr(db_player, key, value)
    db.commit()
    db.refresh(db_player)
    return db_player


@app.delete("/api/players/{player_id}")
def delete_player(player_id: int, db: Session = Depends(get_db)):
    db_player = db.query(Player).filter(Player.id == player_id).first()
    if not db_player:
        raise HTTPException(status_code=404, detail="玩家不存在")
    db.delete(db_player)
    db.commit()
    return {"success": True, "message": "玩家已删除"}


# ==================== 对局管理 ====================

@app.get("/api/games", response_model=List[GameOut])
def list_games(db: Session = Depends(get_db)):
    games = db.query(Game).order_by(Game.id.desc()).all()
    return games


@app.get("/api/games/{game_id}")
def get_game(game_id: int, db: Session = Depends(get_db)):
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="对局不存在")
    
    # 手动构建返回对象，添加players字段
    result = {
        "id": game.id,
        "name": game.name,
        "setup_id": game.setup_id,
        "setup_name": game.setup.name if game.setup else None,
        "player_count": game.player_count,
        "status": game.status,
        "current_phase": game.current_phase,
        "current_round": game.current_round,
        "notes": game.notes,
        "created_at": game.created_at,
        "confirmed_at": game.confirmed_at,
        "players": []
    }
    
    # 添加玩家列表
    # 优化：一次性查询所有玩家状态，避免N+1查询
    player_statuses = db.query(PlayerStatus).filter(
        PlayerStatus.game_id == game_id
    ).all()
    # 构建player_id -> status的映射
    status_map = {ps.player_id: ps for ps in player_statuses}
    
    for gp in game.game_players:
        # 从映射中获取玩家状态，避免每次查询
        player_status = status_map.get(gp.player_id)
        
        player_data = {
            "id": gp.id,
            "game_id": gp.game_id,
            "player_id": gp.player_id,
            "player_name": gp.player.name if gp.player else None,
            "seat_number": gp.seat_number,
            "actual_identity_id": gp.actual_identity_id,
            "actual_identity_name": gp.actual_identity.name if gp.actual_identity else None,
            "is_on_police": player_status.is_on_police if player_status else False,
            "is_retired": player_status.is_retired if player_status else False,
            "is_alive": player_status.is_alive if player_status else True,
            "is_sheriff": player_status.is_sheriff if player_status else False
        }
        result["players"].append(player_data)
    
    return result


@app.post("/api/games", response_model=GameOut)
def create_game(game: GameCreate, db: Session = Depends(get_db)):
    game_data = game.dict()
    players_data = game_data.pop("players", [])
    db_game = Game(**game_data)
    db.add(db_game)
    db.flush()
    
    for gp in players_data:
        db_gp = GamePlayer(game_id=db_game.id, **gp)
        db.add(db_gp)
        # 初始化玩家状态
        db_status = PlayerStatus(game_id=db_game.id, player_id=gp["player_id"])
        db.add(db_status)
    
    db.commit()
    db.refresh(db_game)
    return db_game


@app.put("/api/games/{game_id}", response_model=GameOut)
def update_game(game_id: int, game: GameUpdate, db: Session = Depends(get_db)):
    db_game = db.query(Game).filter(Game.id == game_id).first()
    if not db_game:
        raise HTTPException(status_code=404, detail="对局不存在")
    for key, value in game.dict(exclude_unset=True).items():
        setattr(db_game, key, value)
    db.commit()
    db.refresh(db_game)
    return db_game


@app.delete("/api/games/{game_id}")
def delete_game(game_id: int, db: Session = Depends(get_db)):
    db_game = db.query(Game).filter(Game.id == game_id).first()
    if not db_game:
        raise HTTPException(status_code=404, detail="对局不存在")
    db.delete(db_game)
    db.commit()
    return {"success": True, "message": "对局已删除"}


# ==================== 对局玩家管理 ====================

@app.post("/api/games/{game_id}/players", response_model=GamePlayerOut)
def add_game_player(game_id: int, player: GamePlayerCreate, db: Session = Depends(get_db)):
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="对局不存在")
    
    # 检查是否已存在
    existing = db.query(GamePlayer).filter(
        GamePlayer.game_id == game_id,
        GamePlayer.player_id == player.player_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该玩家已在对局中")
    
    db_player = GamePlayer(game_id=game_id, **player.dict())
    db.add(db_player)
    # 初始化玩家状态
    db_status = PlayerStatus(game_id=game_id, player_id=player.player_id)
    db.add(db_status)
    db.commit()
    db.refresh(db_player)
    return db_player


@app.put("/api/games/{game_id}/players/{player_id}", response_model=GamePlayerOut)
def update_game_player(game_id: int, player_id: int, player: GamePlayerUpdate, db: Session = Depends(get_db)):
    db_player = db.query(GamePlayer).filter(
        GamePlayer.game_id == game_id,
        GamePlayer.player_id == player_id
    ).first()
    if not db_player:
        raise HTTPException(status_code=404, detail="玩家不在对局中")
    for key, value in player.dict(exclude_unset=True).items():
        setattr(db_player, key, value)
    db.commit()
    db.refresh(db_player)
    return db_player


@app.delete("/api/games/{game_id}/players/{player_id}")
def remove_game_player(game_id: int, player_id: int, db: Session = Depends(get_db)):
    db_player = db.query(GamePlayer).filter(
        GamePlayer.game_id == game_id,
        GamePlayer.player_id == player_id
    ).first()
    if not db_player:
        raise HTTPException(status_code=404, detail="玩家不在对局中")
    db.delete(db_player)
    db.commit()
    return {"success": True, "message": "玩家已从对局中移除"}


@app.put("/api/games/{game_id}/players/{player_id}/status")
def update_player_status(game_id: int, player_id: int, status_data: dict, db: Session = Depends(get_db)):
    """更新玩家状态（上警、退水、存活等）"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="对局不存在")
    
    # 检查玩家是否在对局中
    game_player = db.query(GamePlayer).filter(
        GamePlayer.game_id == game_id,
        GamePlayer.player_id == player_id
    ).first()
    if not game_player:
        raise HTTPException(status_code=404, detail="玩家不在对局中")
    
    # 获取或创建玩家状态
    status = db.query(PlayerStatus).filter(
        PlayerStatus.game_id == game_id,
        PlayerStatus.player_id == player_id
    ).first()
    if not status:
        status = PlayerStatus(game_id=game_id, player_id=player_id)
        db.add(status)
        db.flush()
    
    # 更新状态字段
    if "is_on_police" in status_data:
        status.is_on_police = status_data["is_on_police"]
    if "is_retired" in status_data:
        status.is_retired = status_data["is_retired"]
    if "is_alive" in status_data:
        status.is_alive = status_data["is_alive"]
    
    db.commit()
    db.refresh(status)
    
    return {
        "success": True,
        "player_id": player_id,
        "is_on_police": status.is_on_police,
        "is_retired": status.is_retired,
        "is_alive": status.is_alive
    }


@app.post("/api/games/{game_id}/police/select")
def select_police_players(game_id: int, police_data: dict, db: Session = Depends(get_db)):
    """警上发言环节：选择上警的玩家"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="对局不存在")
    
    player_ids = police_data.get("player_ids", [])
    
    # 先重置所有玩家的上警状态
    db.query(PlayerStatus).filter(
        PlayerStatus.game_id == game_id
    ).update({PlayerStatus.is_on_police: False, PlayerStatus.is_retired: False})
    
    # 设置选中玩家的上警状态
    for pid in player_ids:
        status = db.query(PlayerStatus).filter(
            PlayerStatus.game_id == game_id,
            PlayerStatus.player_id == pid
        ).first()
        if not status:
            status = PlayerStatus(game_id=game_id, player_id=pid, is_on_police=True)
            db.add(status)
        else:
            status.is_on_police = True
    
    # 更新游戏阶段为警上发言
    game.current_phase = "警上发言"
    db.commit()
    
    return {"success": True, "phase": game.current_phase, "police_players": player_ids}


@app.post("/api/games/{game_id}/sheriff/set")
def set_sheriff(game_id: int, sheriff_data: dict, db: Session = Depends(get_db)):
    """设置警长（竞选警长环节结束后，警徽票最多的玩家获得警徽）"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="对局不存在")
    
    sheriff_id = sheriff_data.get("player_id")
    if not sheriff_id:
        raise HTTPException(status_code=400, detail="请指定警长玩家")
    
    # 先重置所有玩家的警长状态
    db.query(PlayerStatus).filter(
        PlayerStatus.game_id == game_id
    ).update({PlayerStatus.is_sheriff: False})
    
    # 设置指定玩家为警长
    status = db.query(PlayerStatus).filter(
        PlayerStatus.game_id == game_id,
        PlayerStatus.player_id == sheriff_id
    ).first()
    if not status:
        status = PlayerStatus(game_id=game_id, player_id=sheriff_id, is_sheriff=True)
        db.add(status)
    else:
        status.is_sheriff = True
    
    db.commit()
    
    return {"success": True, "sheriff_id": sheriff_id, "message": "警长已设置"}


# ==================== 行为记录 ====================

@app.get("/api/games/{game_id}/actions", response_model=List[ActionOut])
def list_game_actions(game_id: int, db: Session = Depends(get_db)):
    actions = db.query(Action).filter(Action.game_id == game_id).order_by(Action.id).all()
    result = []
    for action in actions:
        out = ActionOut.from_orm(action)
        out.player_name = action.player.name if action.player else None
        out.target_player_name = action.target_player.name if action.target_player else None
        out.action_type_name = action.action_type.name if action.action_type else None
        result.append(out)
    return result


@app.post("/api/actions", response_model=ActionOut)
def create_action(action: ActionCreate, db: Session = Depends(get_db)):
    db_action = Action(**action.dict())
    db.add(db_action)
    db.commit()
    db.refresh(db_action)
    return db_action


@app.post("/api/actions/batch", response_model=List[ActionOut])
def create_actions_batch(actions: ActionBatchCreate, db: Session = Depends(get_db)):
    result = []
    for action_type_id in actions.action_type_ids:
        db_action = Action(
            game_id=actions.game_id,
            player_id=actions.player_id,
            target_player_id=actions.target_player_id,
            action_type_id=action_type_id,
            round_number=actions.round_number,
            phase=actions.phase,
            declared_identity_id=actions.declared_identity_id,
            notes=actions.notes
        )
        db.add(db_action)
        db.flush()
        result.append(db_action)
    db.commit()
    for action in result:
        db.refresh(action)
    return result


@app.put("/api/actions/{action_id}", response_model=ActionOut)
def update_action(action_id: int, action: ActionUpdate, db: Session = Depends(get_db)):
    db_action = db.query(Action).filter(Action.id == action_id).first()
    if not db_action:
        raise HTTPException(status_code=404, detail="行为记录不存在")
    for key, value in action.dict(exclude_unset=True).items():
        setattr(db_action, key, value)
    db.commit()
    db.refresh(db_action)
    return db_action


@app.delete("/api/actions/{action_id}")
def delete_action(action_id: int, db: Session = Depends(get_db)):
    db_action = db.query(Action).filter(Action.id == action_id).first()
    if not db_action:
        raise HTTPException(status_code=404, detail="行为记录不存在")
    db.delete(db_action)
    db.commit()
    return {"success": True, "message": "行为记录已删除"}


# ==================== 预测 ====================

@app.get("/api/games/{game_id}/predictions")
def get_predictions(game_id: int, db: Session = Depends(get_db)):
    """获取对局的身份预测结果（贝叶斯推理 + 综合逻辑调整）"""
    from inference import predict_game_identities
    from logic_engine_v2 import ComprehensiveLogicEngine
    
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="对局不存在")
    
    # 1. 调用贝叶斯推理引擎获取基础预测
    predictions = predict_game_identities(db, game_id)
    
    # 2. 调用综合逻辑引擎获取概率调整
    try:
        engine = ComprehensiveLogicEngine(db, game_id)
        logic_result = engine.run_full_analysis()
        
        wolf_adjustments = logic_result.get("wolf_prob_adjustments", {})
        good_adjustments = logic_result.get("good_prob_adjustments", {})
        prophet_adjustments = logic_result.get("prophet_prob_adjustments", {})
        
        # 3. 应用逻辑调整到预测结果
        identity_name_map = {ident.id: ident.name for ident in db.query(Identity).all()}
        
        for pred in predictions:
            player_id = pred["player_id"]
            probs = pred.get("predictions", {})
            
            # 狼人概率调整
            if player_id in wolf_adjustments:
                adjustment = wolf_adjustments[player_id]
                for ident_name in list(probs.keys()):
                    if "狼" in ident_name:
                        probs[ident_name] = min(1.0, probs[ident_name] * (1 + adjustment))
                    else:
                        probs[ident_name] = max(0.001, probs[ident_name] * (1 - adjustment * 0.5))
            
            # 好人概率调整
            if player_id in good_adjustments:
                adjustment = good_adjustments[player_id]
                for ident_name in list(probs.keys()):
                    if "狼" not in ident_name and "混血" not in ident_name:
                        probs[ident_name] = min(1.0, probs[ident_name] * (1 + adjustment))
                    else:
                        probs[ident_name] = max(0.001, probs[ident_name] * (1 - adjustment * 0.5))
            
            # 预言家概率调整
            if player_id in prophet_adjustments:
                adjustment = prophet_adjustments[player_id]
                for ident_name in list(probs.keys()):
                    if "预言家" in ident_name:
                        probs[ident_name] = max(0.001, probs[ident_name] * (1 + adjustment))
                    else:
                        probs[ident_name] = min(1.0, probs[ident_name] * (1 - adjustment * 0.3))
            
            # 重新归一化
            total = sum(probs.values())
            if total > 0:
                probs = {k: v / total for k, v in probs.items()}
            
            pred["predictions"] = probs
            
            # 更新top_guess和confidence
            if probs:
                sorted_probs = sorted(probs.items(), key=lambda x: x[1], reverse=True)
                pred["top_guess"] = sorted_probs[0][0]
                pred["confidence"] = round(sorted_probs[0][1], 4)
                pred["camp_prediction"] = "wolf" if "狼" in sorted_probs[0][0] else ("third_party" if "混血" in sorted_probs[0][0] else "good")
    except Exception as e:
        import traceback
        print("应用逻辑调整时出错:", traceback.format_exc())
    
    return {"game_id": game_id, "predictions": predictions}


# ==================== 确认身份 ====================

@app.get("/api/games/{game_id}/confirmed_identities", response_model=List[ConfirmedIdentityOut])
def list_confirmed_identities(game_id: int, db: Session = Depends(get_db)):
    cis = db.query(ConfirmedIdentity).filter(ConfirmedIdentity.game_id == game_id).order_by(ConfirmedIdentity.id).all()
    result = []
    for ci in cis:
        out = ConfirmedIdentityOut.from_orm(ci)
        out.player_name = ci.player.name if ci.player else None
        out.identity_name = ci.identity.name if ci.identity else None
        result.append(out)
    return result


@app.post("/api/games/{game_id}/confirmed_identities", response_model=ConfirmedIdentityOut)
def create_confirmed_identity(ci: ConfirmedIdentityCreate, db: Session = Depends(get_db)):
    db_ci = ConfirmedIdentity(**ci.dict())
    db.add(db_ci)
    db.commit()
    db.refresh(db_ci)
    return db_ci


@app.delete("/api/confirmed_identities/{ci_id}")
def delete_confirmed_identity(ci_id: int, db: Session = Depends(get_db)):
    db_ci = db.query(ConfirmedIdentity).filter(ConfirmedIdentity.id == ci_id).first()
    if not db_ci:
        raise HTTPException(status_code=404, detail="确认身份不存在")
    db.delete(db_ci)
    db.commit()
    return {"success": True, "message": "确认身份已删除"}


# ==================== 狼坑约束 ====================

@app.get("/api/games/{game_id}/wolf_pit/constraints", response_model=List[WolfPitConstraintOut])
def list_wolf_pit_constraints(game_id: int, db: Session = Depends(get_db)):
    return db.query(WolfPitConstraint).filter(WolfPitConstraint.game_id == game_id).order_by(WolfPitConstraint.id).all()


@app.post("/api/games/{game_id}/wolf_pit/constraints", response_model=WolfPitConstraintOut)
def create_wolf_pit_constraint(game_id: int, constraint: WolfPitConstraintCreate, db: Session = Depends(get_db)):
    db_constraint = WolfPitConstraint(**constraint.dict())
    db.add(db_constraint)
    db.commit()
    db.refresh(db_constraint)
    return db_constraint


@app.delete("/api/wolf_pit/constraints/{constraint_id}")
def delete_wolf_pit_constraint(constraint_id: int, db: Session = Depends(get_db)):
    db_constraint = db.query(WolfPitConstraint).filter(WolfPitConstraint.id == constraint_id).first()
    if not db_constraint:
        raise HTTPException(status_code=404, detail="约束不存在")
    db.delete(db_constraint)
    db.commit()
    return {"success": True, "message": "约束已删除"}


# ==================== 游戏流程 ====================

@app.post("/api/games/{game_id}/phase/init")
def init_game_phase(game_id: int, db: Session = Depends(get_db)):
    """初始化游戏阶段"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="对局不存在")
    game.current_phase = "第一个黑夜"
    game.current_round = 1
    db.commit()
    return {"success": True, "phase": game.current_phase, "round": game.current_round}


@app.post("/api/games/{game_id}/phase/advance")
def advance_game_phase(game_id: int, custom_phase: Optional[str] = None, db: Session = Depends(get_db)):
    """进入下一阶段"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="对局不存在")
    
    if custom_phase:
        game.current_phase = custom_phase
    else:
        # 简单的阶段流转
        phases = ["第一个黑夜", "警上发言", "警徽投票", "死讯公布", "白天发言", "放逐投票", "遗言"]
        current_idx = phases.index(game.current_phase) if game.current_phase in phases else -1
        if current_idx < len(phases) - 1:
            game.current_phase = phases[current_idx + 1]
        else:
            game.current_round += 1
            game.current_phase = "黑夜"
    
    db.commit()
    return {"success": True, "phase": game.current_phase, "round": game.current_round}


@app.post("/api/games/{game_id}/wolf_explode")
def wolf_explode(game_id: int, player_id: int, db: Session = Depends(get_db)):
    """狼人自爆"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="对局不存在")
    
    # 更新玩家状态
    status = db.query(PlayerStatus).filter(
        PlayerStatus.game_id == game_id,
        PlayerStatus.player_id == player_id
    ).first()
    if status:
        status.is_alive = False
        status.death_type = "self_explode"
        status.death_round = game.current_round
    
    # 进入下一黑夜
    game.current_phase = "黑夜"
    game.current_round += 1
    db.commit()
    
    return {"success": True, "phase": game.current_phase, "round": game.current_round}


# ==================== 对局确认与学习 ====================

@app.post("/api/games/{game_id}/confirm")
def confirm_game(game_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """确认对局结束，触发学习"""
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="对局不存在")
    
    game.status = "已确认"
    game.confirmed_at = datetime.now()
    db.commit()
    
    # 后台触发梯度下降学习
    def run_learning():
        try:
            from gradient_learning import run_gradient_learning
            print(f"开始学习对局 {game_id}")
            result = run_gradient_learning(db, game_id)
            print(f"对局 {game_id} 学习完成: {result}")
        except Exception as e:
            import traceback
            print(f"学习失败: {e}")
            traceback.print_exc()
    
    background_tasks.add_task(run_learning)
    
    return {"success": True, "message": "对局已确认，梯度下降学习已在后台启动"}


# ==================== 梯度下降学习 ====================

@app.post("/api/gradient_learning/run")
def run_gradient_learning_api(game_id: Optional[int] = None, db: Session = Depends(get_db)):
    """运行梯度下降学习"""
    try:
        from gradient_learning import run_gradient_learning
        result = run_gradient_learning(db, game_id)
        return {"success": True, "message": "梯度下降学习已完成", "result": result}
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print("梯度学习错误:", error_detail)
        raise HTTPException(status_code=500, detail=f"梯度学习错误: {str(e)}")


@app.get("/api/gradient_learning/history")
def get_learning_history(limit: int = 10, db: Session = Depends(get_db)):
    """获取学习历史"""
    logs = db.query(LearningLog).order_by(LearningLog.id.desc()).limit(limit).all()
    return logs


# ==================== 预言家分析 ====================

@app.get("/api/games/{game_id}/prophet_analysis")
def get_prophet_analysis(game_id: int, db: Session = Depends(get_db)):
    """获取预言家查验链分析（使用新的综合逻辑引擎）"""
    try:
        from logic_engine_v2 import ComprehensiveLogicEngine
        
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            raise HTTPException(status_code=404, detail="对局不存在")
        
        # 调用综合逻辑引擎
        engine = ComprehensiveLogicEngine(db, game_id)
        result = engine.run_full_analysis()
        
        return {"game_id": game_id, "data": result}
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print("预言家分析错误:", error_detail)
        raise HTTPException(status_code=500, detail=f"预言家分析错误: {str(e)}")


# ==================== 综合逻辑分析 ====================

@app.get("/api/games/{game_id}/comprehensive_analysis")
def get_comprehensive_analysis(game_id: int, db: Session = Depends(get_db)):
    """获取综合逻辑分析结果（包含所有逻辑模块）"""
    try:
        from logic_engine_v2 import ComprehensiveLogicEngine
        
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            raise HTTPException(status_code=404, detail="对局不存在")
        
        # 调用综合逻辑引擎
        engine = ComprehensiveLogicEngine(db, game_id)
        result = engine.run_full_analysis()
        
        return {"game_id": game_id, "data": result}
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print("综合逻辑分析错误:", error_detail)
        raise HTTPException(status_code=500, detail=f"综合逻辑分析错误: {str(e)}")


# ==================== 狼坑分析 ====================

@app.get("/api/games/{game_id}/wolf_pit/analysis")
def get_wolf_pit_analysis(game_id: int, total_wolves: int = 4, db: Session = Depends(get_db)):
    """获取狼坑分析"""
    try:
        from wolf_pit import analyze_wolf_pits
        
        game = db.query(Game).filter(Game.id == game_id).first()
        if not game:
            raise HTTPException(status_code=404, detail="对局不存在")
        
        # 如果对局有版型，从版型获取狼人阵营的总数量
        if game.setup_id:
            # 找到狼人阵营
            wolf_faction = db.query(Faction).filter(Faction.name.contains("狼")).first()
            if wolf_faction:
                setup_identities = db.query(SetupIdentity).filter(
                    SetupIdentity.setup_id == game.setup_id
                ).all()
                # 统计所有属于狼人阵营的身份数量
                total_wolves = 0
                for si in setup_identities:
                    if si.identity and si.identity.faction_id == wolf_faction.id:
                        total_wolves += si.count
        
        # 调用狼坑分析
        result = analyze_wolf_pits(db, game_id, total_wolves)
        
        return {"game_id": game_id, "data": result}
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print("狼坑分析错误:", error_detail)
        raise HTTPException(status_code=500, detail=f"狼坑分析错误: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
