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
    
    # 检查并添加新列（用于数据库迁移）
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            # 检查player_statuses表是否有is_sheriff列
            # 兼容PostgreSQL和SQLite
            if DATABASE_URL.startswith("postgresql"):
                result = conn.execute(text("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'player_statuses' AND column_name = 'is_sheriff'
                """))
            else:
                # SQLite使用PRAGMA
                result = conn.execute(text("PRAGMA table_info(player_statuses)"))
                columns = [row[1] for row in result.fetchall()]
                has_column = 'is_sheriff' in columns
                if not has_column:
                    conn.execute(text("ALTER TABLE player_statuses ADD COLUMN is_sheriff BOOLEAN DEFAULT 0"))
                    conn.commit()
                    print("[数据库迁移] SQLite 已添加 is_sheriff 列")
                    return
            
            if not result.fetchone():
                # PostgreSQL 添加is_sheriff列
                conn.execute(text("ALTER TABLE player_statuses ADD COLUMN is_sheriff BOOLEAN DEFAULT FALSE"))
                conn.commit()
                print("[数据库迁移] PostgreSQL 已添加 is_sheriff 列")
    except Exception as e:
        print(f"[数据库迁移] 检查/添加列时出错: {e}")
    
    print("[数据库初始化] 完成")
