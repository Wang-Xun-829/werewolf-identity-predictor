"""
数据库连接模块
支持PostgreSQL和SQLite
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./werewolf_v5.db")

# 如果是PostgreSQL，使用psycopg3驱动（SQLAlchemy 2.0支持）
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql+psycopg2://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)

if DATABASE_URL.startswith("postgresql"):
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)
else:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库表"""
    from models import (
        Faction, Identity, Setup, SetupIdentity, ActionType, ActionTypeWeight,
        Player, Game, GamePlayer, Action, IdentityWeight, PlayerStatus,
        WolfPitConstraint, Scenario, ScenarioAssignment, ConfirmedIdentity,
        LearningLog, WeightBackup, Prediction, PredictionScore
    )
    Base.metadata.create_all(bind=engine)
    print("[数据库初始化] 完成")
