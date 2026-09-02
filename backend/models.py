"""
SQLAlchemy数据模型 - 狼人杀身份预测系统 v5.0
共20张表
"""
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, DateTime, 
    ForeignKey, JSON, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


# ============================================================
# 1. 阵营表
# ============================================================
class Faction(Base):
    __tablename__ = "factions"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, comment="阵营名称")
    description = Column(Text, default="", comment="阵营描述")
    color = Column(String(20), default="#888888", comment="阵营颜色")
    created_at = Column(DateTime, default=datetime.now)
    
    identities = relationship("Identity", back_populates="faction")


# ============================================================
# 2. 身份表
# ============================================================
class Identity(Base):
    __tablename__ = "identities"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, comment="身份名称")
    faction_id = Column(Integer, ForeignKey("factions.id"), nullable=False, comment="所属阵营")
    description = Column(Text, default="", comment="身份描述")
    is_god = Column(Boolean, default=False, comment="是否神职")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.now)
    
    faction = relationship("Faction", back_populates="identities")
    setup_identities = relationship("SetupIdentity", back_populates="identity")
    game_players = relationship("GamePlayer", back_populates="actual_identity")
    confirmed_identities = relationship("ConfirmedIdentity", back_populates="identity")


# ============================================================
# 3. 版型表
# ============================================================
class Setup(Base):
    __tablename__ = "setups"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, comment="版型名称")
    player_count = Column(Integer, default=12, comment="玩家人数")
    description = Column(Text, default="", comment="版型描述")
    created_at = Column(DateTime, default=datetime.now)
    
    setup_identities = relationship("SetupIdentity", back_populates="setup", cascade="all, delete-orphan")
    games = relationship("Game", back_populates="setup")


# ============================================================
# 4. 版型身份配置表
# ============================================================
class SetupIdentity(Base):
    __tablename__ = "setup_identities"
    
    id = Column(Integer, primary_key=True, index=True)
    setup_id = Column(Integer, ForeignKey("setups.id"), nullable=False, comment="版型ID")
    identity_id = Column(Integer, ForeignKey("identities.id"), nullable=False, comment="身份ID")
    count = Column(Integer, default=1, comment="身份数量")
    
    setup = relationship("Setup", back_populates="setup_identities")
    identity = relationship("Identity", back_populates="setup_identities")
    
    __table_args__ = (
        UniqueConstraint('setup_id', 'identity_id', name='uq_setup_identity'),
    )


# ============================================================
# 5. 行为类型表（支持多级分类）
# ============================================================
class ActionType(Base):
    __tablename__ = "action_types"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="行为名称")
    parent_id = Column(Integer, ForeignKey("action_types.id"), nullable=True, comment="父行为ID")
    category = Column(String(50), default="其他", comment="行为分类")
    description = Column(Text, default="", comment="行为描述")
    default_weight = Column(Float, default=1.0, comment="默认权重")
    has_result_status = Column(Boolean, default=False, comment="是否有结果状态（保对/保错等）")
    sort_order = Column(Integer, default=0, comment="排序")
    created_at = Column(DateTime, default=datetime.now)
    
    parent = relationship("ActionType", remote_side=[id], backref="children")
    actions = relationship("Action", back_populates="action_type")


# ============================================================
# 6. 行为默认权重表
# ============================================================
class ActionTypeWeight(Base):
    __tablename__ = "action_type_weights"
    
    id = Column(Integer, primary_key=True, index=True)
    action_type_id = Column(Integer, ForeignKey("action_types.id"), nullable=False, comment="行为类型ID")
    identity_id = Column(Integer, ForeignKey("identities.id"), nullable=False, comment="身份ID")
    weight = Column(Float, default=1.0, comment="权重值")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    __table_args__ = (
        UniqueConstraint('action_type_id', 'identity_id', name='uq_action_identity_weight'),
    )


# ============================================================
# 7. 玩家表
# ============================================================
class Player(Base):
    __tablename__ = "players"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, comment="玩家名称")
    pinyin = Column(String(200), default="", comment="拼音")
    pinyin_initial = Column(String(50), default="", comment="拼音首字母")
    description = Column(Text, default="", comment="玩家描述")
    created_at = Column(DateTime, default=datetime.now)
    
    game_players = relationship("GamePlayer", back_populates="player")
    actions_as_actor = relationship("Action", foreign_keys="Action.player_id", back_populates="player")
    actions_as_target = relationship("Action", foreign_keys="Action.target_player_id", back_populates="target_player")
    identity_weights = relationship("IdentityWeight", back_populates="player")
    player_statuses = relationship("PlayerStatus", back_populates="player")
    confirmed_identities = relationship("ConfirmedIdentity", back_populates="player")


# ============================================================
# 8. 对局表
# ============================================================
class Game(Base):
    __tablename__ = "games"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), default="未命名对局", comment="对局名称")
    setup_id = Column(Integer, ForeignKey("setups.id"), nullable=True, comment="版型ID")
    player_count = Column(Integer, default=12, comment="玩家人数")
    status = Column(String(20), default="进行中", comment="对局状态：进行中/已确认")
    current_phase = Column(String(50), default="未开始", comment="当前阶段")
    current_round = Column(Integer, default=1, comment="当前轮次")
    notes = Column(Text, default="", comment="备注")
    created_at = Column(DateTime, default=datetime.now)
    confirmed_at = Column(DateTime, nullable=True, comment="确认时间")
    
    setup = relationship("Setup", back_populates="games")
    game_players = relationship("GamePlayer", back_populates="game", cascade="all, delete-orphan")
    actions = relationship("Action", back_populates="game", cascade="all, delete-orphan")
    player_statuses = relationship("PlayerStatus", back_populates="game", cascade="all, delete-orphan")
    wolf_pit_constraints = relationship("WolfPitConstraint", back_populates="game", cascade="all, delete-orphan")
    scenarios = relationship("Scenario", back_populates="game", cascade="all, delete-orphan")
    confirmed_identities = relationship("ConfirmedIdentity", back_populates="game", cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="game", cascade="all, delete-orphan")


# ============================================================
# 9. 对局玩家表
# ============================================================
class GamePlayer(Base):
    __tablename__ = "game_players"
    
    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, comment="对局ID")
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False, comment="玩家ID")
    seat_number = Column(Integer, nullable=True, comment="座位号")
    actual_identity_id = Column(Integer, ForeignKey("identities.id"), nullable=True, comment="真实身份ID")
    
    game = relationship("Game", back_populates="game_players")
    player = relationship("Player", back_populates="game_players")
    actual_identity = relationship("Identity", back_populates="game_players")
    
    __table_args__ = (
        UniqueConstraint('game_id', 'player_id', name='uq_game_player'),
    )


# ============================================================
# 10. 行为记录表
# ============================================================
class Action(Base):
    __tablename__ = "actions"
    
    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, comment="对局ID")
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False, comment="行为发起者ID")
    target_player_id = Column(Integer, ForeignKey("players.id"), nullable=True, comment="行为目标ID")
    action_type_id = Column(Integer, ForeignKey("action_types.id"), nullable=False, comment="行为类型ID")
    round_number = Column(Integer, default=1, comment="轮次")
    phase = Column(String(50), default="", comment="阶段")
    declared_identity_id = Column(Integer, ForeignKey("identities.id"), nullable=True, comment="声明身份ID")
    result_status = Column(String(20), default="unknown", comment="结果状态：correct/incorrect/unknown")
    notes = Column(Text, default="", comment="备注")
    is_verified = Column(Boolean, default=False, comment="是否已验证")
    created_at = Column(DateTime, default=datetime.now)
    
    game = relationship("Game", back_populates="actions")
    player = relationship("Player", foreign_keys=[player_id], back_populates="actions_as_actor")
    target_player = relationship("Player", foreign_keys=[target_player_id], back_populates="actions_as_target")
    action_type = relationship("ActionType", back_populates="actions")


# ============================================================
# 11. 玩家个性化权重表
# ============================================================
class IdentityWeight(Base):
    __tablename__ = "identity_weights"
    
    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False, comment="玩家ID")
    identity_id = Column(Integer, ForeignKey("identities.id"), nullable=False, comment="身份ID")
    action_type_id = Column(Integer, ForeignKey("action_types.id"), nullable=True, comment="行为类型ID（空表示全局系数）")
    weight = Column(Float, default=1.0, comment="权重值")
    sample_count = Column(Integer, default=0, comment="样本数量")
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    player = relationship("Player", back_populates="identity_weights")
    
    __table_args__ = (
        UniqueConstraint('player_id', 'identity_id', 'action_type_id', name='uq_player_identity_action'),
    )


# ============================================================
# 12. 玩家状态表
# ============================================================
class PlayerStatus(Base):
    __tablename__ = "player_statuses"
    
    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, comment="对局ID")
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False, comment="玩家ID")
    is_on_police = Column(Boolean, default=False, comment="是否上警")
    is_retired = Column(Boolean, default=False, comment="是否退水")
    is_alive = Column(Boolean, default=True, comment="是否存活")
    is_sheriff = Column(Boolean, default=False, comment="是否是警长")
    death_type = Column(String(20), nullable=True, comment="死亡类型：night/vote/self_explode")
    death_round = Column(Integer, nullable=True, comment="死亡轮次")
    
    game = relationship("Game", back_populates="player_statuses")
    player = relationship("Player", back_populates="player_statuses")
    
    __table_args__ = (
        UniqueConstraint('game_id', 'player_id', name='uq_game_player_status'),
    )


# ============================================================
# 13. 狼坑约束表
# ============================================================
class WolfPitConstraint(Base):
    __tablename__ = "wolf_pit_constraints"
    
    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, comment="对局ID")
    player_ids = Column(JSON, nullable=False, comment="玩家ID列表")
    wolf_count = Column(Integer, default=1, comment="狼人数")
    description = Column(Text, default="", comment="描述")
    created_at = Column(DateTime, default=datetime.now)
    
    game = relationship("Game", back_populates="wolf_pit_constraints")


# ============================================================
# 14. 情景假设表
# ============================================================
class Scenario(Base):
    __tablename__ = "scenarios"
    
    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, comment="对局ID")
    name = Column(String(100), nullable=False, comment="情景名称")
    description = Column(Text, default="", comment="情景描述")
    sort_order = Column(Integer, default=0, comment="排序")
    created_at = Column(DateTime, default=datetime.now)
    
    game = relationship("Game", back_populates="scenarios")
    assignments = relationship("ScenarioAssignment", back_populates="scenario", cascade="all, delete-orphan")


# ============================================================
# 15. 情景身份分配表
# ============================================================
class ScenarioAssignment(Base):
    __tablename__ = "scenario_assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=False, comment="情景ID")
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False, comment="玩家ID")
    identity_id = Column(Integer, ForeignKey("identities.id"), nullable=True, comment="身份ID")
    camp_only = Column(String(20), nullable=True, comment="仅指定阵营：good/wolf/third_party")
    
    scenario = relationship("Scenario", back_populates="assignments")


# ============================================================
# 16. 确认身份表（逻辑基点）
# ============================================================
class ConfirmedIdentity(Base):
    __tablename__ = "confirmed_identities"
    
    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, comment="对局ID")
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False, comment="玩家ID")
    identity_id = Column(Integer, ForeignKey("identities.id"), nullable=True, comment="确认身份ID")
    camp_only = Column(String(20), nullable=True, comment="仅确认阵营：good/wolf/third_party")
    reason = Column(Text, default="", comment="确认原因")
    created_at = Column(DateTime, default=datetime.now)
    
    game = relationship("Game", back_populates="confirmed_identities")
    player = relationship("Player", back_populates="confirmed_identities")
    identity = relationship("Identity", back_populates="confirmed_identities")


# ============================================================
# 17. 学习日志表
# ============================================================
class LearningLog(Base):
    __tablename__ = "learning_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=True, comment="触发学习的对局ID")
    iteration = Column(Integer, default=0, comment="迭代次数")
    before_score = Column(Float, default=0.0, comment="学习前得分")
    after_score = Column(Float, default=0.0, comment="学习后得分")
    improvement = Column(Float, default=0.0, comment="提升幅度")
    learning_rate = Column(Float, default=0.01, comment="学习率")
    details = Column(JSON, default=dict, comment="详细信息")
    created_at = Column(DateTime, default=datetime.now)


# ============================================================
# 18. 权重备份表
# ============================================================
class WeightBackup(Base):
    __tablename__ = "weight_backups"
    
    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=True, comment="触发学习的对局ID")
    backup_type = Column(String(20), default="before", comment="备份类型：before/after")
    weights_data = Column(JSON, nullable=False, comment="权重数据")
    score = Column(Float, default=0.0, comment="对应得分")
    created_at = Column(DateTime, default=datetime.now)


# ============================================================
# 19. 预测结果表
# ============================================================
class Prediction(Base):
    __tablename__ = "predictions"
    
    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, comment="对局ID")
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False, comment="玩家ID")
    predictions = Column(JSON, default=dict, comment="各身份概率")
    top_guess = Column(String(50), default="", comment="最可能身份")
    confidence = Column(Float, default=0.0, comment="置信度")
    created_at = Column(DateTime, default=datetime.now)
    
    game = relationship("Game", back_populates="predictions")
    
    __table_args__ = (
        UniqueConstraint('game_id', 'player_id', name='uq_game_player_prediction'),
    )


# ============================================================
# 20. 预测打分明细表
# ============================================================
class PredictionScore(Base):
    __tablename__ = "prediction_scores"
    
    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, comment="对局ID")
    player_id = Column(Integer, ForeignKey("players.id"), nullable=False, comment="玩家ID")
    actual_identity_id = Column(Integer, ForeignKey("identities.id"), nullable=True, comment="真实身份ID")
    predicted_identity = Column(String(50), default="", comment="预测身份")
    is_correct = Column(Boolean, default=False, comment="身份预测是否正确")
    camp_is_correct = Column(Boolean, default=False, comment="阵营预测是否正确")
    score = Column(Float, default=0.0, comment="得分")
    created_at = Column(DateTime, default=datetime.now)
