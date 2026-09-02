"""
Pydantic模型定义 - API请求/响应格式
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ==================== 阵营与身份 ====================

class FactionBase(BaseModel):
    name: str
    description: Optional[str] = ""
    color: Optional[str] = "#888888"

class FactionCreate(FactionBase):
    pass

class FactionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None

class FactionOut(FactionBase):
    id: int
    created_at: Optional[datetime] = None
    class Config:
        orm_mode = True


class IdentityBase(BaseModel):
    name: str
    faction_id: int
    description: Optional[str] = ""
    is_god: Optional[bool] = False
    is_active: Optional[bool] = True

class IdentityCreate(IdentityBase):
    pass

class IdentityUpdate(BaseModel):
    name: Optional[str] = None
    faction_id: Optional[int] = None
    description: Optional[str] = None
    is_god: Optional[bool] = None
    is_active: Optional[bool] = None

class IdentityOut(IdentityBase):
    id: int
    faction_name: Optional[str] = None
    created_at: Optional[datetime] = None
    class Config:
        orm_mode = True


# ==================== 版型配置 ====================

class SetupIdentityBase(BaseModel):
    identity_id: int
    count: int = 1

class SetupBase(BaseModel):
    name: str
    player_count: int
    description: Optional[str] = ""
    identities: List[SetupIdentityBase] = []

class SetupCreate(SetupBase):
    pass

class SetupUpdate(BaseModel):
    name: Optional[str] = None
    player_count: Optional[int] = None
    description: Optional[str] = None
    identities: Optional[List[SetupIdentityBase]] = None

class SetupIdentityOut(SetupIdentityBase):
    id: int
    identity_name: Optional[str] = None
    class Config:
        orm_mode = True

class SetupOut(BaseModel):
    id: int
    name: str
    player_count: int
    description: Optional[str] = ""
    identities: List[SetupIdentityOut] = []
    created_at: Optional[datetime] = None
    class Config:
        orm_mode = True


# ==================== 行为体系 ====================

class ActionTypeBase(BaseModel):
    name: str
    parent_id: Optional[int] = None
    category: Optional[str] = "其他"
    description: Optional[str] = ""
    default_weight: Optional[float] = 1.0
    has_result_status: Optional[bool] = False
    sort_order: Optional[int] = 0

class ActionTypeCreate(ActionTypeBase):
    pass

class ActionTypeUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None
    category: Optional[str] = None
    description: Optional[str] = None
    default_weight: Optional[float] = None
    has_result_status: Optional[bool] = None
    sort_order: Optional[int] = None

class ActionTypeOut(ActionTypeBase):
    id: int
    children: List[Any] = []
    created_at: Optional[datetime] = None
    class Config:
        orm_mode = True


# ==================== 玩家 ====================

class PlayerBase(BaseModel):
    name: str
    pinyin: Optional[str] = ""
    pinyin_initial: Optional[str] = ""
    description: Optional[str] = ""

class PlayerCreate(PlayerBase):
    pass

class PlayerUpdate(BaseModel):
    name: Optional[str] = None
    pinyin: Optional[str] = None
    pinyin_initial: Optional[str] = None
    description: Optional[str] = None

class PlayerOut(PlayerBase):
    id: int
    created_at: Optional[datetime] = None
    class Config:
        orm_mode = True


# ==================== 对局 ====================

class GamePlayerBase(BaseModel):
    player_id: int
    seat_number: Optional[int] = None
    actual_identity_id: Optional[int] = None

class GamePlayerCreate(GamePlayerBase):
    pass

class GamePlayerUpdate(BaseModel):
    seat_number: Optional[int] = None
    actual_identity_id: Optional[int] = None

class GamePlayerOut(GamePlayerBase):
    id: int
    game_id: int
    player_name: Optional[str] = None
    actual_identity_name: Optional[str] = None
    class Config:
        orm_mode = True

class GameBase(BaseModel):
    name: Optional[str] = "未命名对局"
    setup_id: Optional[int] = None
    player_count: Optional[int] = 12
    notes: Optional[str] = ""

class GameCreate(GameBase):
    players: List[GamePlayerCreate] = []

class GameUpdate(BaseModel):
    name: Optional[str] = None
    setup_id: Optional[int] = None
    player_count: Optional[int] = None
    status: Optional[str] = None
    current_phase: Optional[str] = None
    current_round: Optional[int] = None
    notes: Optional[str] = None

class GameOut(GameBase):
    id: int
    status: str
    current_phase: Optional[str] = None
    current_round: Optional[int] = None
    setup_name: Optional[str] = None
    players: List[GamePlayerOut] = []
    created_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    class Config:
        orm_mode = True


# ==================== 行为记录 ====================

class ActionBase(BaseModel):
    game_id: int
    player_id: int
    target_player_id: Optional[int] = None
    action_type_id: int
    round_number: Optional[int] = 1
    phase: Optional[str] = ""
    declared_identity_id: Optional[int] = None
    result_status: Optional[str] = "unknown"
    notes: Optional[str] = ""

class ActionCreate(ActionBase):
    pass

class ActionBatchCreate(BaseModel):
    game_id: int
    player_id: int
    target_player_id: Optional[int] = None
    action_type_ids: List[int]
    round_number: Optional[int] = 1
    phase: Optional[str] = ""
    declared_identity_id: Optional[int] = None
    notes: Optional[str] = ""
    duel_result: Optional[str] = None  # 骑士决斗结果：initiator_dies（发起者死亡）或 target_dies（被决斗者死亡）

class ActionUpdate(BaseModel):
    target_player_id: Optional[int] = None
    round_number: Optional[int] = None
    phase: Optional[str] = None
    declared_identity_id: Optional[int] = None
    result_status: Optional[str] = None
    notes: Optional[str] = None

class ActionOut(ActionBase):
    id: int
    player_name: Optional[str] = None
    target_player_name: Optional[str] = None
    action_type_name: Optional[str] = None
    declared_identity_name: Optional[str] = None
    is_verified: bool = False
    created_at: Optional[datetime] = None
    class Config:
        orm_mode = True


# ==================== 预测 ====================

class PredictionOut(BaseModel):
    game_id: int
    player_id: int
    player_name: Optional[str] = None
    predictions: Dict[str, float] = {}
    top_guess: Optional[str] = None
    confidence: Optional[float] = 0.0
    class Config:
        orm_mode = True


# ==================== 确认身份 ====================

class ConfirmedIdentityBase(BaseModel):
    game_id: int
    player_id: int
    identity_id: Optional[int] = None
    camp_only: Optional[str] = None
    reason: Optional[str] = ""

class ConfirmedIdentityCreate(ConfirmedIdentityBase):
    pass

class ConfirmedIdentityOut(ConfirmedIdentityBase):
    id: int
    player_name: Optional[str] = None
    identity_name: Optional[str] = None
    created_at: Optional[datetime] = None
    class Config:
        orm_mode = True


# ==================== 狼坑约束 ====================

class WolfPitConstraintBase(BaseModel):
    game_id: int
    player_ids: List[int]
    wolf_count: int = 1
    description: Optional[str] = ""

class WolfPitConstraintCreate(WolfPitConstraintBase):
    pass

class WolfPitConstraintOut(WolfPitConstraintBase):
    id: int
    created_at: Optional[datetime] = None
    class Config:
        orm_mode = True


# ==================== 通用响应 ====================

class ApiResponse(BaseModel):
    success: bool = True
    message: Optional[str] = None
    data: Optional[Any] = None
