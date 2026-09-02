"""
数据迁移脚本 - 从线上PostgreSQL迁移到本地SQLite（v5格式）
"""
import os
import sys
import json
import sqlite3
from datetime import datetime

# 添加backend目录到路径
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

# 线上PostgreSQL连接字符串
SOURCE_DB_URL = "postgresql://neondb_owner:npg_u1rFnCVX7NTx@ep-restless-feather-azyo5mej-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# 本地SQLite数据库路径
TARGET_DB_PATH = os.path.join(backend_dir, "werewolf_v5.db")

# 导入v5的数据库模块
from database import init_db, SessionLocal
from models import (
    Faction, Identity, Setup, SetupIdentity, ActionType, ActionTypeWeight,
    Player, Game, GamePlayer, Action, IdentityWeight, PlayerStatus,
    WolfPitConstraint, Scenario, ScenarioAssignment, ConfirmedIdentity,
    LearningLog, WeightBackup, Prediction
)


def get_source_connection():
    """获取源数据库（PostgreSQL）连接"""
    import psycopg
    return psycopg.connect(SOURCE_DB_URL)


def migrate_factions(source_conn, target_db):
    """迁移阵营（从roles表的camp字段提取）"""
    print("迁移阵营...")
    
    # 从roles表提取所有不同的camp
    cursor = source_conn.cursor()
    cursor.execute("SELECT DISTINCT camp FROM roles WHERE camp IS NOT NULL AND camp != ''")
    camps = cursor.fetchall()
    
    faction_map = {}  # camp名称 -> faction_id
    
    for (camp,) in camps:
        # 判断阵营名称
        if '狼' in camp:
            faction_name = '狼人'
            color = '#ef4444'
        elif '第三' in camp or 'third' in camp.lower():
            faction_name = '第三方'
            color = '#f59e0b'
        else:
            faction_name = '好人'
            color = '#10b981'
        
        # 检查是否已存在
        existing = target_db.query(Faction).filter(Faction.name == faction_name).first()
        if existing:
            faction_map[camp] = existing.id
        else:
            faction = Faction(name=faction_name, description=f"{camp}阵营", color=color)
            target_db.add(faction)
            target_db.flush()
            faction_map[camp] = faction.id
    
    target_db.commit()
    print(f"  迁移了 {len(faction_map)} 个阵营")
    return faction_map


def migrate_identities(source_conn, target_db, faction_map):
    """迁移身份"""
    print("迁移身份...")
    
    cursor = source_conn.cursor()
    cursor.execute("SELECT id, name, camp, description, is_active, created_at FROM roles ORDER BY id")
    roles = cursor.fetchall()
    
    identity_map = {}  # 旧role_id -> 新identity_id
    
    for role in roles:
        old_id, name, camp, description, is_active, created_at = role
        
        # 检查是否已存在
        existing = target_db.query(Identity).filter(Identity.name == name).first()
        if existing:
            identity_map[old_id] = existing.id
            continue
        
        faction_id = faction_map.get(camp, 1)  # 默认好人阵营
        
        # 判断是否神职
        is_god = name in ['预言家', '女巫', '猎人', '守卫', '骑士', '白痴', '魔术师', '摄梦人']
        
        identity = Identity(
            name=name,
            faction_id=faction_id,
            description=description or '',
            is_god=is_god,
            is_active=bool(is_active) if is_active is not None else True,
            created_at=created_at or datetime.now()
        )
        target_db.add(identity)
        target_db.flush()
        identity_map[old_id] = identity.id
    
    target_db.commit()
    print(f"  迁移了 {len(identity_map)} 个身份")
    return identity_map


def migrate_players(source_conn, target_db):
    """迁移玩家"""
    print("迁移玩家...")
    
    cursor = source_conn.cursor()
    cursor.execute("SELECT id, name, created_at FROM players ORDER BY id")
    players = cursor.fetchall()
    
    player_map = {}  # 旧player_id -> 新player_id
    
    for player in players:
        old_id, name, created_at = player
        
        # 检查是否已存在
        existing = target_db.query(Player).filter(Player.name == name).first()
        if existing:
            player_map[old_id] = existing.id
            continue
        
        new_player = Player(
            name=name,
            pinyin='',
            pinyin_initial='',
            description='',
            created_at=created_at or datetime.now()
        )
        target_db.add(new_player)
        target_db.flush()
        player_map[old_id] = new_player.id
    
    target_db.commit()
    print(f"  迁移了 {len(player_map)} 个玩家")
    return player_map


def migrate_action_types(source_conn, target_db):
    """迁移行为类型"""
    print("迁移行为类型...")
    
    cursor = source_conn.cursor()
    cursor.execute("SELECT id, name, description, default_weight, is_active, created_at, parent_id, action_type, has_result_status FROM actions ORDER BY id")
    actions = cursor.fetchall()
    
    action_map = {}  # 旧action_id -> 新action_type_id
    
    # 先创建一级行为（parent_id为NULL的）
    for action in actions:
        old_id, name, description, default_weight, is_active, created_at, parent_id, action_type, has_result_status = action
        
        if parent_id is not None:
            continue  # 跳过子行为，后面再创建
        
        existing = target_db.query(ActionType).filter(ActionType.name == name).first()
        if existing:
            action_map[old_id] = existing.id
            continue
        
        new_action = ActionType(
            name=name,
            parent_id=None,
            category=action_type or '其他',
            description=description or '',
            default_weight=default_weight or 1.0,
            has_result_status=bool(has_result_status) if has_result_status is not None else False,
            sort_order=0,
            created_at=created_at or datetime.now()
        )
        target_db.add(new_action)
        target_db.flush()
        action_map[old_id] = new_action.id
    
    # 再创建子行为
    for action in actions:
        old_id, name, description, default_weight, is_active, created_at, parent_id, action_type, has_result_status = action
        
        if parent_id is None:
            continue
        
        existing = target_db.query(ActionType).filter(ActionType.name == name).first()
        if existing:
            action_map[old_id] = existing.id
            continue
        
        new_parent_id = action_map.get(parent_id)
        
        new_action = ActionType(
            name=name,
            parent_id=new_parent_id,
            category=action_type or '其他',
            description=description or '',
            default_weight=default_weight or 1.0,
            has_result_status=bool(has_result_status) if has_result_status is not None else False,
            sort_order=0,
            created_at=created_at or datetime.now()
        )
        target_db.add(new_action)
        target_db.flush()
        action_map[old_id] = new_action.id
    
    target_db.commit()
    print(f"  迁移了 {len(action_map)} 个行为类型")
    return action_map


def migrate_setups(source_conn, target_db, identity_map):
    """迁移版型（需要解析role_config JSON）"""
    print("迁移版型...")
    
    cursor = source_conn.cursor()
    cursor.execute("SELECT id, name, role_config, description, is_active, created_at FROM setups ORDER BY id")
    setups = cursor.fetchall()
    
    setup_map = {}  # 旧setup_id -> 新setup_id
    
    for setup in setups:
        old_id, name, role_config, description, is_active, created_at = setup
        
        existing = target_db.query(Setup).filter(Setup.name == name).first()
        if existing:
            setup_map[old_id] = existing.id
            continue
        
        # 解析role_config
        player_count = 0
        identities_config = []
        try:
            if role_config:
                config = json.loads(role_config)
                if isinstance(config, dict):
                    for role_name, count in config.items():
                        # 找到对应的identity_id
                        identity = target_db.query(Identity).filter(Identity.name == role_name).first()
                        if identity:
                            identities_config.append({'identity_id': identity.id, 'count': count})
                            player_count += count
                elif isinstance(config, list):
                    for item in config:
                        if isinstance(item, dict):
                            role_name = item.get('name') or item.get('role')
                            count = item.get('count', 1)
                            identity = target_db.query(Identity).filter(Identity.name == role_name).first()
                            if identity:
                                identities_config.append({'identity_id': identity.id, 'count': count})
                                player_count += count
        except Exception as e:
            print(f"    解析版型 {name} 的role_config失败: {e}")
        
        if player_count == 0:
            player_count = 12  # 默认12人
        
        new_setup = Setup(
            name=name,
            player_count=player_count,
            description=description or '',
            created_at=created_at or datetime.now()
        )
        target_db.add(new_setup)
        target_db.flush()
        setup_map[old_id] = new_setup.id
        
        # 创建版型身份配置
        for si in identities_config:
            new_si = SetupIdentity(
                setup_id=new_setup.id,
                identity_id=si['identity_id'],
                count=si['count']
            )
            target_db.add(new_si)
    
    target_db.commit()
    print(f"  迁移了 {len(setup_map)} 个版型")
    return setup_map


def migrate_games(source_conn, target_db, setup_map, player_map):
    """迁移对局"""
    print("迁移对局...")
    
    cursor = source_conn.cursor()
    cursor.execute("""
        SELECT id, game_code, setup_id, player_count, status, notes, 
               created_at, finished_at, confirmed_at, current_phase, current_round
        FROM games ORDER BY id
    """)
    games = cursor.fetchall()
    
    game_map = {}  # 旧game_id -> 新game_id
    
    for game in games:
        old_id, game_code, setup_id, player_count, status, notes, created_at, finished_at, confirmed_at, current_phase, current_round = game
        
        existing = target_db.query(Game).filter(Game.id == old_id).first()
        if existing:
            game_map[old_id] = existing.id
            continue
        
        new_setup_id = setup_map.get(setup_id) if setup_id else None
        
        # game_code作为name，如果为空则用"未命名对局"
        name = game_code or f"对局{old_id}"
        
        new_game = Game(
            id=old_id,  # 保持原ID
            name=name,
            setup_id=new_setup_id,
            player_count=player_count or 12,
            status=status or '进行中',
            current_phase=current_phase or '未开始',
            current_round=current_round or 1,
            notes=notes or '',
            created_at=created_at or datetime.now(),
            confirmed_at=confirmed_at
        )
        target_db.add(new_game)
        target_db.flush()
        game_map[old_id] = old_id  # 保持原ID
    
    target_db.commit()
    print(f"  迁移了 {len(game_map)} 个对局")
    return game_map


def migrate_game_players(source_conn, target_db, game_map, player_map, identity_map):
    """迁移对局玩家"""
    print("迁移对局玩家...")
    
    cursor = source_conn.cursor()
    cursor.execute("SELECT id, game_id, player_id, seat_number, actual_role_id FROM game_players ORDER BY id")
    game_players = cursor.fetchall()
    
    count = 0
    for gp in game_players:
        old_id, game_id, player_id, seat_number, actual_role_id = gp
        
        new_game_id = game_map.get(game_id)
        new_player_id = player_map.get(player_id)
        
        if not new_game_id or not new_player_id:
            continue
        
        # 检查是否已存在
        existing = target_db.query(GamePlayer).filter(
            GamePlayer.game_id == new_game_id,
            GamePlayer.player_id == new_player_id
        ).first()
        if existing:
            continue
        
        new_actual_identity_id = identity_map.get(actual_role_id) if actual_role_id else None
        
        new_gp = GamePlayer(
            game_id=new_game_id,
            player_id=new_player_id,
            seat_number=seat_number,
            actual_identity_id=new_actual_identity_id
        )
        target_db.add(new_gp)
        target_db.flush()
        
        # 初始化玩家状态
        existing_status = target_db.query(PlayerStatus).filter(
            PlayerStatus.game_id == new_game_id,
            PlayerStatus.player_id == new_player_id
        ).first()
        if not existing_status:
            new_status = PlayerStatus(
                game_id=new_game_id,
                player_id=new_player_id,
                is_on_police=False,
                is_retired=False,
                is_alive=True
            )
            target_db.add(new_status)
        
        count += 1
    
    target_db.commit()
    print(f"  迁移了 {count} 条对局玩家记录")


def migrate_behavior_records(source_conn, target_db, game_map, player_map, action_map, identity_map):
    """迁移行为记录"""
    print("迁移行为记录...")
    
    cursor = source_conn.cursor()
    cursor.execute("""
        SELECT id, game_id, actor_id, target_id, action_id, actor_role_id, actor_camp,
               round_number, phase, notes, is_verified, created_at, result_status
        FROM behavior_records ORDER BY id
    """)
    records = cursor.fetchall()
    
    count = 0
    for record in records:
        old_id, game_id, actor_id, target_id, action_id, actor_role_id, actor_camp, round_number, phase, notes, is_verified, created_at, result_status = record
        
        new_game_id = game_map.get(game_id)
        new_actor_id = player_map.get(actor_id)
        new_action_id = action_map.get(action_id)
        
        if not new_game_id or not new_actor_id or not new_action_id:
            continue
        
        # 检查是否已存在
        existing = target_db.query(Action).filter(Action.id == old_id).first()
        if existing:
            continue
        
        new_target_id = player_map.get(target_id) if target_id else None
        new_declared_identity_id = identity_map.get(actor_role_id) if actor_role_id else None
        
        new_action = Action(
            id=old_id,  # 保持原ID
            game_id=new_game_id,
            player_id=new_actor_id,
            target_player_id=new_target_id,
            action_type_id=new_action_id,
            round_number=round_number or 1,
            phase=phase or '',
            declared_identity_id=new_declared_identity_id,
            result_status=result_status or 'unknown',
            notes=notes or '',
            is_verified=bool(is_verified) if is_verified is not None else False,
            created_at=created_at or datetime.now()
        )
        target_db.add(new_action)
        count += 1
    
    target_db.commit()
    print(f"  迁移了 {count} 条行为记录")


def migrate_algorithm_weights(source_conn, target_db, action_map, identity_map):
    """迁移算法权重（行为默认权重）"""
    print("迁移算法权重...")
    
    cursor = source_conn.cursor()
    cursor.execute("SELECT id, action_id, role_id, weight, sample_count, updated_at FROM algorithm_weights ORDER BY id")
    weights = cursor.fetchall()
    
    count = 0
    for w in weights:
        old_id, action_id, role_id, weight, sample_count, updated_at = w
        
        new_action_id = action_map.get(action_id)
        new_identity_id = identity_map.get(role_id)
        
        if not new_action_id or not new_identity_id:
            continue
        
        # 检查是否已存在
        existing = target_db.query(ActionTypeWeight).filter(
            ActionTypeWeight.action_type_id == new_action_id,
            ActionTypeWeight.identity_id == new_identity_id
        ).first()
        if existing:
            continue
        
        new_weight = ActionTypeWeight(
            action_type_id=new_action_id,
            identity_id=new_identity_id,
            weight=weight or 1.0,
            updated_at=updated_at or datetime.now()
        )
        target_db.add(new_weight)
        count += 1
    
    target_db.commit()
    print(f"  迁移了 {count} 条算法权重")


def migrate_player_behavior_stats(source_conn, target_db, player_map, identity_map, action_map):
    """迁移玩家行为统计（个性化权重）"""
    print("迁移玩家行为统计...")
    
    cursor = source_conn.cursor()
    cursor.execute("SELECT id, player_id, role_id, action_id, count, game_count, updated_at FROM player_behavior_stats ORDER BY id")
    stats = cursor.fetchall()
    
    count = 0
    for stat in stats:
        old_id, player_id, role_id, action_id, stat_count, game_count, updated_at = stat
        
        new_player_id = player_map.get(player_id)
        new_identity_id = identity_map.get(role_id)
        new_action_id = action_map.get(action_id)
        
        if not new_player_id or not new_identity_id:
            continue
        
        # 检查是否已存在
        existing = target_db.query(IdentityWeight).filter(
            IdentityWeight.player_id == new_player_id,
            IdentityWeight.identity_id == new_identity_id,
            IdentityWeight.action_type_id == new_action_id
        ).first()
        if existing:
            continue
        
        new_weight = IdentityWeight(
            player_id=new_player_id,
            identity_id=new_identity_id,
            action_type_id=new_action_id,
            weight=1.0,  # 默认权重，后续可以根据统计数据计算
            sample_count=stat_count or 0,
            updated_at=updated_at or datetime.now()
        )
        target_db.add(new_weight)
        count += 1
    
    target_db.commit()
    print(f"  迁移了 {count} 条玩家行为统计")


def migrate_scenarios(source_conn, target_db, game_map, player_map, identity_map):
    """迁移情景假设"""
    print("迁移情景假设...")
    
    # 迁移情景
    cursor = source_conn.cursor()
    cursor.execute("SELECT id, game_id, name, description, is_active, sort_order, created_at FROM game_scenarios ORDER BY id")
    scenarios = cursor.fetchall()
    
    scenario_map = {}  # 旧scenario_id -> 新scenario_id
    count = 0
    
    for scenario in scenarios:
        old_id, game_id, name, description, is_active, sort_order, created_at = scenario
        
        new_game_id = game_map.get(game_id)
        if not new_game_id:
            continue
        
        existing = target_db.query(Scenario).filter(Scenario.id == old_id).first()
        if existing:
            scenario_map[old_id] = existing.id
            continue
        
        new_scenario = Scenario(
            id=old_id,
            game_id=new_game_id,
            name=name,
            description=description or '',
            sort_order=sort_order or 0,
            created_at=created_at or datetime.now()
        )
        target_db.add(new_scenario)
        target_db.flush()
        scenario_map[old_id] = old_id
        count += 1
    
    target_db.commit()
    print(f"  迁移了 {count} 个情景假设")
    
    # 迁移情景身份分配
    print("迁移情景身份分配...")
    cursor.execute("SELECT id, scenario_id, player_id, role_id, camp, confidence, created_at FROM scenario_assignments ORDER BY id")
    assignments = cursor.fetchall()
    
    count = 0
    for assignment in assignments:
        old_id, scenario_id, player_id, role_id, camp, confidence, created_at = assignment
        
        new_scenario_id = scenario_map.get(scenario_id)
        new_player_id = player_map.get(player_id)
        
        if not new_scenario_id or not new_player_id:
            continue
        
        existing = target_db.query(ScenarioAssignment).filter(ScenarioAssignment.id == old_id).first()
        if existing:
            continue
        
        new_identity_id = identity_map.get(role_id) if role_id else None
        
        # 转换camp格式
        camp_only = None
        if camp:
            if '狼' in camp:
                camp_only = 'wolf'
            elif '第三' in camp:
                camp_only = 'third_party'
            else:
                camp_only = 'good'
        
        new_assignment = ScenarioAssignment(
            id=old_id,
            scenario_id=new_scenario_id,
            player_id=new_player_id,
            identity_id=new_identity_id,
            camp_only=camp_only
        )
        target_db.add(new_assignment)
        count += 1
    
    target_db.commit()
    print(f"  迁移了 {count} 条情景身份分配")


def migrate_confirmed_identities(source_conn, target_db, game_map, player_map, identity_map):
    """迁移确认身份"""
    print("迁移确认身份...")
    
    cursor = source_conn.cursor()
    cursor.execute("SELECT id, game_id, player_id, role_id, camp, reason, confirmed_at FROM game_confirmed_identities ORDER BY id")
    confirmed = cursor.fetchall()
    
    count = 0
    for ci in confirmed:
        old_id, game_id, player_id, role_id, camp, reason, confirmed_at = ci
        
        new_game_id = game_map.get(game_id)
        new_player_id = player_map.get(player_id)
        
        if not new_game_id or not new_player_id:
            continue
        
        existing = target_db.query(ConfirmedIdentity).filter(ConfirmedIdentity.id == old_id).first()
        if existing:
            continue
        
        new_identity_id = identity_map.get(role_id) if role_id else None
        
        # 转换camp格式
        camp_only = None
        if camp:
            if '狼' in camp:
                camp_only = 'wolf'
            elif '第三' in camp:
                camp_only = 'third_party'
            else:
                camp_only = 'good'
        
        new_ci = ConfirmedIdentity(
            id=old_id,
            game_id=new_game_id,
            player_id=new_player_id,
            identity_id=new_identity_id,
            camp_only=camp_only,
            reason=reason or '',
            created_at=confirmed_at or datetime.now()
        )
        target_db.add(new_ci)
        count += 1
    
    target_db.commit()
    print(f"  迁移了 {count} 条确认身份")


def migrate_predictions(source_conn, target_db, game_map, player_map, identity_map):
    """迁移预测结果（从每行一个身份概率转换成JSON格式）"""
    print("迁移预测结果...")
    
    cursor = source_conn.cursor()
    cursor.execute("SELECT id, game_id, player_id, role_id, probability, predicted_at, model_version FROM predictions ORDER BY game_id, player_id, id")
    predictions = cursor.fetchall()
    
    # 按game_id和player_id分组
    grouped = {}
    for pred in predictions:
        old_id, game_id, player_id, role_id, probability, predicted_at, model_version = pred
        key = (game_id, player_id)
        if key not in grouped:
            grouped[key] = {
                'predictions': {},
                'predicted_at': predicted_at,
                'model_version': model_version
            }
        
        identity_name = None
        # 找到对应的身份名称
        for old_role_id, new_identity_id in identity_map.items():
            if old_role_id == role_id:
                # 查询身份名称
                identity = target_db.query(Identity).filter(Identity.id == new_identity_id).first()
                if identity:
                    identity_name = identity.name
                break
        
        if identity_name:
            grouped[key]['predictions'][identity_name] = probability or 0.0
    
    count = 0
    for (game_id, player_id), data in grouped.items():
        new_game_id = game_map.get(game_id)
        new_player_id = player_map.get(player_id)
        
        if not new_game_id or not new_player_id:
            continue
        
        # 检查是否已存在
        existing = target_db.query(Prediction).filter(
            Prediction.game_id == new_game_id,
            Prediction.player_id == new_player_id
        ).first()
        if existing:
            continue
        
        preds = data['predictions']
        # 计算top_guess和confidence
        if preds:
            sorted_preds = sorted(preds.items(), key=lambda x: x[1], reverse=True)
            top_guess = sorted_preds[0][0]
            confidence = sorted_preds[0][1]
        else:
            top_guess = None
            confidence = 0.0
        
        new_pred = Prediction(
            game_id=new_game_id,
            player_id=new_player_id,
            predictions=preds,
            top_guess=top_guess,
            confidence=confidence
        )
        target_db.add(new_pred)
        count += 1
    
    target_db.commit()
    print(f"  迁移了 {count} 条预测结果")


def migrate_learning_logs(source_conn, target_db, game_map):
    """迁移学习日志"""
    print("迁移学习日志...")
    
    cursor = source_conn.cursor()
    try:
        cursor.execute("SELECT id, game_id, start_time, end_time, initial_score, final_score, iterations, status, details FROM learning_logs ORDER BY id")
        logs = cursor.fetchall()
    except:
        print("  学习日志表结构不匹配，跳过")
        return
    
    count = 0
    for log in logs:
        old_id, game_id, start_time, end_time, initial_score, final_score, iterations, status, details = log
        
        new_game_id = game_map.get(game_id) if game_id else None
        
        existing = target_db.query(LearningLog).filter(LearningLog.id == old_id).first()
        if existing:
            continue
        
        # 解析details JSON
        details_dict = {}
        if details:
            try:
                details_dict = json.loads(details) if isinstance(details, str) else details
            except:
                pass
        
        new_log = LearningLog(
            id=old_id,
            game_id=new_game_id,
            iteration=iterations or 0,
            before_score=initial_score or 0.0,
            after_score=final_score or 0.0,
            improvement=(final_score - initial_score) if (initial_score and final_score) else 0.0,
            learning_rate=0.01,
            details=details_dict
        )
        target_db.add(new_log)
        count += 1
    
    target_db.commit()
    print(f"  迁移了 {count} 条学习日志")


def migrate_weight_backups(source_conn, target_db):
    """迁移权重备份"""
    print("迁移权重备份...")
    
    cursor = source_conn.cursor()
    try:
        cursor.execute("SELECT id, backup_name, backup_time, weights_data, score, reason FROM weight_backups ORDER BY id")
        backups = cursor.fetchall()
    except:
        print("  权重备份表结构不匹配，跳过")
        return
    
    count = 0
    for backup in backups:
        old_id, backup_name, backup_time, weights_data, score, reason = backup
        
        existing = target_db.query(WeightBackup).filter(WeightBackup.id == old_id).first()
        if existing:
            continue
        
        # 解析weights_data JSON
        weights_dict = {}
        if weights_data:
            try:
                weights_dict = json.loads(weights_data) if isinstance(weights_data, str) else weights_data
            except:
                pass
        
        new_backup = WeightBackup(
            id=old_id,
            game_id=None,
            backup_type='before',
            weights_data=weights_dict,
            score=score or 0.0
        )
        target_db.add(new_backup)
        count += 1
    
    target_db.commit()
    print(f"  迁移了 {count} 条权重备份")


def main():
    print("=" * 60)
    print("数据迁移 - 从线上PostgreSQL迁移到本地SQLite（v5格式）")
    print("=" * 60)
    print()
    
    # 初始化目标数据库
    print("初始化目标数据库...")
    init_db()
    target_db = SessionLocal()
    
    # 连接源数据库
    print("连接源数据库（线上PostgreSQL）...")
    try:
        source_conn = get_source_connection()
        print("  连接成功！")
    except Exception as e:
        print(f"  连接失败: {e}")
        return
    
    print()
    
    try:
        # 按顺序迁移数据
        faction_map = migrate_factions(source_conn, target_db)
        identity_map = migrate_identities(source_conn, target_db, faction_map)
        player_map = migrate_players(source_conn, target_db)
        action_map = migrate_action_types(source_conn, target_db)
        setup_map = migrate_setups(source_conn, target_db, identity_map)
        game_map = migrate_games(source_conn, target_db, setup_map, player_map)
        migrate_game_players(source_conn, target_db, game_map, player_map, identity_map)
        migrate_behavior_records(source_conn, target_db, game_map, player_map, action_map, identity_map)
        migrate_algorithm_weights(source_conn, target_db, action_map, identity_map)
        migrate_player_behavior_stats(source_conn, target_db, player_map, identity_map, action_map)
        migrate_scenarios(source_conn, target_db, game_map, player_map, identity_map)
        migrate_confirmed_identities(source_conn, target_db, game_map, player_map, identity_map)
        migrate_predictions(source_conn, target_db, game_map, player_map, identity_map)
        migrate_learning_logs(source_conn, target_db, game_map)
        migrate_weight_backups(source_conn, target_db)
        
        print()
        print("=" * 60)
        print("数据迁移完成！")
        print("=" * 60)
        
        # 统计迁移后的数据量
        print()
        print("迁移后数据统计：")
        print(f"  阵营: {target_db.query(Faction).count()} 个")
        print(f"  身份: {target_db.query(Identity).count()} 个")
        print(f"  玩家: {target_db.query(Player).count()} 个")
        print(f"  行为类型: {target_db.query(ActionType).count()} 个")
        print(f"  版型: {target_db.query(Setup).count()} 个")
        print(f"  对局: {target_db.query(Game).count()} 个")
        print(f"  对局玩家: {target_db.query(GamePlayer).count()} 条")
        print(f"  行为记录: {target_db.query(Action).count()} 条")
        print(f"  算法权重: {target_db.query(ActionTypeWeight).count()} 条")
        print(f"  个性化权重: {target_db.query(IdentityWeight).count()} 条")
        print(f"  情景假设: {target_db.query(Scenario).count()} 个")
        print(f"  确认身份: {target_db.query(ConfirmedIdentity).count()} 条")
        print(f"  预测结果: {target_db.query(Prediction).count()} 条")
        
    except Exception as e:
        print(f"\n迁移过程中出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        source_conn.close()
        target_db.close()


if __name__ == "__main__":
    main()
