"""
数据迁移脚本 - 从werewolf_2迁移到werewolf_v5
使用方法：
1. 配置源数据库和目标数据库连接
2. 运行 python migrate_data.py
"""
import os
import sys
import json
from datetime import datetime

# 源数据库（werewolf_2）配置
SOURCE_DB_URL = os.getenv("SOURCE_DB_URL", "sqlite:///../werewolf_2/werewolf.db")

# 目标数据库（werewolf_v5）配置
TARGET_DB_URL = os.getenv("DATABASE_URL", "sqlite:///./werewolf_v5.db")

# 设置目标数据库
os.environ["DATABASE_URL"] = TARGET_DB_URL

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine, text
from database import SessionLocal, init_db
from models import (
    Faction, Identity, Setup, SetupIdentity, ActionType, ActionTypeWeight,
    Player, Game, GamePlayer, Action, IdentityWeight, PlayerStatus,
    WolfPitConstraint, Scenario, ScenarioAssignment, ConfirmedIdentity,
    LearningLog, WeightBackup, Prediction
)


def get_source_engine():
    """获取源数据库引擎"""
    return create_engine(SOURCE_DB_URL)


def migrate_factions(source_conn, target_db):
    """迁移阵营"""
    print("迁移阵营...")
    try:
        result = source_conn.execute(text("SELECT * FROM factions"))
        rows = result.fetchall()
        for row in rows:
            existing = target_db.query(Faction).filter(Faction.name == row.name).first()
            if not existing:
                faction = Faction(
                    name=row.name,
                    description=getattr(row, 'description', ''),
                    color=getattr(row, 'color', '#888888')
                )
                target_db.add(faction)
        target_db.commit()
        print(f"  迁移了 {len(rows)} 个阵营")
    except Exception as e:
        print(f"  迁移阵营失败: {e}")
        # 如果源数据库没有factions表，创建默认阵营
        target_db.execute(text("INSERT OR IGNORE INTO factions (name, description, color) VALUES ('好人', '好人阵营', '#10b981')"))
        target_db.execute(text("INSERT OR IGNORE INTO factions (name, description, color) VALUES ('狼人', '狼人阵营', '#ef4444')"))
        target_db.execute(text("INSERT OR IGNORE INTO factions (name, description, color) VALUES ('第三方', '第三方阵营', '#f59e0b')"))
        target_db.commit()
        print("  创建了默认阵营")


def migrate_identities(source_conn, target_db):
    """迁移身份"""
    print("迁移身份...")
    try:
        result = source_conn.execute(text("SELECT * FROM roles"))
        rows = result.fetchall()
        
        # 获取阵营映射
        factions = {f.name: f.id for f in target_db.query(Faction).all()}
        
        for row in rows:
            existing = target_db.query(Identity).filter(Identity.name == row.name).first()
            if not existing:
                # 判断阵营
                camp = getattr(row, 'camp', '')
                if '狼' in camp:
                    faction_name = '狼人'
                elif '第三' in camp:
                    faction_name = '第三方'
                else:
                    faction_name = '好人'
                
                identity = Identity(
                    name=row.name,
                    faction_id=factions.get(faction_name, 1),
                    description=getattr(row, 'description', '')
                )
                target_db.add(identity)
        target_db.commit()
        print(f"  迁移了 {len(rows)} 个身份")
    except Exception as e:
        print(f"  迁移身份失败: {e}")


def migrate_players(source_conn, target_db):
    """迁移玩家"""
    print("迁移玩家...")
    try:
        result = source_conn.execute(text("SELECT * FROM players"))
        rows = result.fetchall()
        for row in rows:
            existing = target_db.query(Player).filter(Player.name == row.name).first()
            if not existing:
                player = Player(
                    name=row.name,
                    pinyin=getattr(row, 'pinyin', ''),
                    pinyin_initial=getattr(row, 'pinyin_initial', ''),
                    description=getattr(row, 'description', '')
                )
                target_db.add(player)
        target_db.commit()
        print(f"  迁移了 {len(rows)} 个玩家")
    except Exception as e:
        print(f"  迁移玩家失败: {e}")


def migrate_action_types(source_conn, target_db):
    """迁移行为类型"""
    print("迁移行为类型...")
    try:
        result = source_conn.execute(text("SELECT * FROM actions"))
        rows = result.fetchall()
        
        # 先创建一级行为
        action_map = {}  # 源ID -> 目标ID
        for row in rows:
            if not getattr(row, 'parent_id', None):
                existing = target_db.query(ActionType).filter(ActionType.name == row.name).first()
                if not existing:
                    action = ActionType(
                        name=row.name,
                        category=getattr(row, 'category', '其他'),
                        description=getattr(row, 'description', ''),
                        default_weight=getattr(row, 'default_weight', 1.0),
                        has_result_status=getattr(row, 'has_result_status', False),
                        sort_order=getattr(row, 'sort_order', 0)
                    )
                    target_db.add(action)
                    target_db.flush()
                    action_map[row.id] = action.id
        
        # 再创建子行为
        for row in rows:
            if getattr(row, 'parent_id', None):
                existing = target_db.query(ActionType).filter(ActionType.name == row.name).first()
                if not existing:
                    action = ActionType(
                        name=row.name,
                        parent_id=action_map.get(row.parent_id),
                        category=getattr(row, 'category', '其他'),
                        description=getattr(row, 'description', ''),
                        default_weight=getattr(row, 'default_weight', 1.0),
                        has_result_status=getattr(row, 'has_result_status', False),
                        sort_order=getattr(row, 'sort_order', 0)
                    )
                    target_db.add(action)
                    target_db.flush()
                    action_map[row.id] = action.id
        
        target_db.commit()
        print(f"  迁移了 {len(rows)} 个行为类型")
        return action_map
    except Exception as e:
        print(f"  迁移行为类型失败: {e}")
        return {}


def migrate_setups(source_conn, target_db):
    """迁移版型"""
    print("迁移版型...")
    try:
        result = source_conn.execute(text("SELECT * FROM setups"))
        rows = result.fetchall()
        
        identity_map = {i.name: i.id for i in target_db.query(Identity).all()}
        setup_map = {}
        
        for row in rows:
            existing = target_db.query(Setup).filter(Setup.name == row.name).first()
            if not existing:
                setup = Setup(
                    name=row.name,
                    player_count=getattr(row, 'player_count', 12),
                    description=getattr(row, 'description', '')
                )
                target_db.add(setup)
                target_db.flush()
                setup_map[row.id] = setup.id
                
                # 迁移版型身份配置
                try:
                    si_result = source_conn.execute(
                        text(f"SELECT * FROM setup_identities WHERE setup_id = {row.id}")
                    )
                    for si in si_result.fetchall():
                        identity_name = None
                        # 尝试通过identity_id获取身份名称
                        try:
                            i_result = source_conn.execute(text(f"SELECT name FROM roles WHERE id = {si.identity_id}"))
                            i_row = i_result.fetchone()
                            if i_row:
                                identity_name = i_row.name
                        except:
                            pass
                        
                        if identity_name and identity_name in identity_map:
                            setup_identity = SetupIdentity(
                                setup_id=setup.id,
                                identity_id=identity_map[identity_name],
                                count=getattr(si, 'count', 1)
                            )
                            target_db.add(setup_identity)
                except Exception as e:
                    print(f"    迁移版型 {row.name} 的身份配置失败: {e}")
        
        target_db.commit()
        print(f"  迁移了 {len(rows)} 个版型")
        return setup_map
    except Exception as e:
        print(f"  迁移版型失败: {e}")
        return {}


def migrate_games(source_conn, target_db, player_map, action_map, setup_map):
    """迁移对局和行为记录"""
    print("迁移对局...")
    try:
        result = source_conn.execute(text("SELECT * FROM games"))
        rows = result.fetchall()
        
        game_map = {}
        
        for row in rows:
            existing = target_db.query(Game).filter(Game.id == row.id).first()
            if not existing:
                game = Game(
                    id=row.id,
                    name=getattr(row, 'name', '未命名对局'),
                    setup_id=setup_map.get(getattr(row, 'setup_id')),
                    player_count=getattr(row, 'player_count', 12),
                    status=getattr(row, 'status', '进行中'),
                    current_phase=getattr(row, 'current_phase', '未开始'),
                    current_round=getattr(row, 'current_round', 1),
                    notes=getattr(row, 'notes', ''),
                    created_at=getattr(row, 'created_at', datetime.now()),
                    confirmed_at=getattr(row, 'confirmed_at', None)
                )
                target_db.add(game)
                target_db.flush()
                game_map[row.id] = game.id
                
                # 迁移对局玩家
                try:
                    gp_result = source_conn.execute(
                        text(f"SELECT * FROM game_players WHERE game_id = {row.id}")
                    )
                    for gp in gp_result.fetchall():
                        game_player = GamePlayer(
                            game_id=game.id,
                            player_id=player_map.get(gp.player_id, gp.player_id),
                            seat_number=getattr(gp, 'seat_number', None),
                            actual_identity_id=getattr(gp, 'actual_role_id', None)
                        )
                        target_db.add(game_player)
                        
                        # 迁移玩家状态
                        player_status = PlayerStatus(
                            game_id=game.id,
                            player_id=player_map.get(gp.player_id, gp.player_id),
                            is_on_police=getattr(gp, 'is_on_police', False),
                            is_retired=getattr(gp, 'is_retired', False),
                            is_alive=getattr(gp, 'is_alive', True),
                            death_type=getattr(gp, 'death_type', None),
                            death_round=getattr(gp, 'death_round', None)
                        )
                        target_db.add(player_status)
                except Exception as e:
                    print(f"    迁移对局 {row.id} 的玩家失败: {e}")
                
                # 迁移行为记录
                try:
                    action_result = source_conn.execute(
                        text(f"SELECT * FROM behavior_records WHERE game_id = {row.id}")
                    )
                    for ar in action_result.fetchall():
                        action = Action(
                            game_id=game.id,
                            player_id=player_map.get(ar.actor_id, ar.actor_id),
                            target_player_id=player_map.get(ar.target_id, ar.target_id) if getattr(ar, 'target_id', None) else None,
                            action_type_id=action_map.get(ar.action_id, ar.action_id),
                            round_number=getattr(ar, 'round_number', 1),
                            phase=getattr(ar, 'phase', ''),
                            declared_identity_id=getattr(ar, 'declared_role_id', None),
                            result_status=getattr(ar, 'result_status', 'unknown'),
                            notes=getattr(ar, 'notes', ''),
                            is_verified=getattr(ar, 'is_verified', False),
                            created_at=getattr(ar, 'created_at', datetime.now())
                        )
                        target_db.add(action)
                except Exception as e:
                    print(f"    迁移对局 {row.id} 的行为记录失败: {e}")
        
        target_db.commit()
        print(f"  迁移了 {len(rows)} 个对局")
    except Exception as e:
        print(f"  迁移对局失败: {e}")


def main():
    print("=" * 60)
    print("数据迁移 - 从werewolf_2迁移到werewolf_v5")
    print("=" * 60)
    print(f"源数据库: {SOURCE_DB_URL}")
    print(f"目标数据库: {TARGET_DB_URL}")
    print()
    
    # 初始化目标数据库
    print("初始化目标数据库...")
    init_db()
    
    # 获取源数据库连接
    source_engine = get_source_engine()
    source_conn = source_engine.connect()
    
    try:
        target_db = SessionLocal()
        
        # 迁移数据
        migrate_factions(source_conn, target_db)
        migrate_identities(source_conn, target_db)
        
        # 迁移玩家并建立映射
        print("迁移玩家...")
        players = target_db.query(Player).all()
        player_map = {p.id: p.id for p in players}  # 假设ID不变
        
        action_map = migrate_action_types(source_conn, target_db)
        setup_map = migrate_setups(source_conn, target_db)
        migrate_games(source_conn, target_db, player_map, action_map, setup_map)
        
        target_db.close()
        
        print()
        print("=" * 60)
        print("数据迁移完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"迁移失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        source_conn.close()
        source_engine.dispose()


if __name__ == "__main__":
    main()
