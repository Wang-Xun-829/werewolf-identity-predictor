"""
假数据生成脚本 - 用于测试算法功能
生成虚拟玩家、对局、行为记录，并自动确认对局

使用方法:
    python generate_fake_data.py

生成内容:
    - 20个虚拟玩家
    - 200局虚拟对局（随机版型）
    - 每局根据身份生成合理行为序列
    - 自动确认对局（填入真实身份，触发算法自我优化）

清空假数据:
    执行 clear_fake_data.sql
"""

import random
import json
import sys
import os

# 导入项目数据库模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import query_one, query_all, execute_write
from prediction import update_weights_from_game

# ============================================================
# 配置
# ============================================================
NUM_PLAYERS = 20       # 虚拟玩家数量
NUM_GAMES = 200        # 虚拟对局数量
NOISE_RATE = 0.15      # 噪声率（模拟判断错误、行为不一致）
BEHAVIORS_PER_GAME = 15  # 每局平均行为数量

# ============================================================
# 身份ID映射（从init.sql确认）
# ============================================================
ROLE_IDS = {
    '预言家': 1, '女巫': 2, '猎人': 3, '白痴': 4, '守卫': 5,
    '平民': 6, '狼人': 7, '狼王': 8, '白狼王': 9, '丘比特': 10, '盗贼': 11
}

# ============================================================
# 行为ID映射
# ============================================================
ACTION_IDS = {
    '跳预言家': 1, '查杀': 2, '发金水': 3, '跳女巫': 4, '跳猎人': 5,
    '跳守卫': 6, '认平民': 7, '投票': 8, '弃票': 9, '站边': 10,
    '倒钩': 11, '冲锋': 12, '自爆': 13, '开枪': 14, '使用解药': 15,
    '使用毒药': 16, '守护': 17, '质疑': 18, '划水': 19
}

# ============================================================
# 各身份的行为倾向配置
# 格式: {行为名: (概率, 是否需要目标)}
# ============================================================
ROLE_BEHAVIOR_TENDENCIES = {
    '预言家': [
        ('跳预言家', 0.85, False),
        ('发金水', 0.40, True),
        ('查杀', 0.35, True),
        ('站边', 0.60, True),   # 站边自己
        ('质疑', 0.20, True),
        ('划水', 0.05, False),
    ],
    '女巫': [
        ('跳女巫', 0.40, False),
        ('使用解药', 0.25, True),
        ('使用毒药', 0.20, True),
        ('认平民', 0.20, False),
        ('站边', 0.50, True),
        ('质疑', 0.25, True),
        ('划水', 0.15, False),
    ],
    '猎人': [
        ('跳猎人', 0.25, False),
        ('开枪', 0.15, True),
        ('认平民', 0.25, False),
        ('站边', 0.55, True),
        ('质疑', 0.30, True),
        ('划水', 0.15, False),
    ],
    '白痴': [
        ('认平民', 0.50, False),
        ('站边', 0.50, True),
        ('质疑', 0.25, True),
        ('划水', 0.30, False),
    ],
    '守卫': [
        ('跳守卫', 0.20, False),
        ('守护', 0.35, True),
        ('认平民', 0.25, False),
        ('站边', 0.50, True),
        ('质疑', 0.25, True),
        ('划水', 0.15, False),
    ],
    '平民': [
        ('认平民', 0.60, False),
        ('站边', 0.65, True),
        ('质疑', 0.35, True),
        ('划水', 0.40, False),
        ('投票', 0.50, True),
        ('弃票', 0.10, False),
    ],
    '狼人': [
        ('跳预言家', 0.30, False),   # 悍跳
        ('查杀', 0.25, True),          # 查杀好人
        ('发金水', 0.25, True),         # 发金水（可能给狼队友或好人）
        ('冲锋', 0.45, True),           # 站边悍跳狼
        ('倒钩', 0.20, True),           # 站边真预言家
        ('站边', 0.15, True),
        ('质疑', 0.30, True),
        ('划水', 0.25, False),
        ('自爆', 0.05, False),
        ('投票', 0.45, True),
    ],
    '狼王': [
        ('跳预言家', 0.25, False),
        ('查杀', 0.25, True),
        ('发金水', 0.20, True),
        ('冲锋', 0.50, True),
        ('倒钩', 0.15, True),
        ('开枪', 0.20, True),           # 狼王被淘汰可开枪
        ('质疑', 0.30, True),
        ('划水', 0.20, False),
        ('自爆', 0.05, False),
        ('投票', 0.45, True),
    ],
    '白狼王': [
        ('跳预言家', 0.20, False),
        ('查杀', 0.20, True),
        ('发金水', 0.20, True),
        ('冲锋', 0.40, True),
        ('倒钩', 0.15, True),
        ('自爆', 0.20, False),           # 白狼王自爆带人
        ('质疑', 0.25, True),
        ('划水', 0.20, False),
        ('投票', 0.40, True),
    ],
    '丘比特': [
        ('认平民', 0.50, False),
        ('站边', 0.45, True),
        ('质疑', 0.20, True),
        ('划水', 0.35, False),
    ],
    '盗贼': [
        ('认平民', 0.50, False),
        ('站边', 0.45, True),
        ('质疑', 0.20, True),
        ('划水', 0.35, False),
    ],
}


def generate_players():
    """生成虚拟玩家"""
    print(f"正在生成 {NUM_PLAYERS} 个虚拟玩家...")
    player_ids = []
    for i in range(1, NUM_PLAYERS + 1):
        name = f"测试玩家{i:02d}"
        # 检查是否已存在
        existing = query_one("SELECT id FROM players WHERE name = " + _ph(), (name,))
        if existing:
            player_ids.append(existing['id'])
        else:
            pid = execute_write(
                f"INSERT INTO players (name) VALUES ({_ph()})",
                (name,)
            )
            player_ids.append(pid)
    print(f"  玩家生成完成，共 {len(player_ids)} 个")
    return player_ids


def _ph():
    """获取占位符（SQLite用?，PostgreSQL用%s）"""
    # 简单判断：如果DATABASE_URL以postgresql开头则用%s，否则用?
    db_url = os.environ.get('DATABASE_URL', '')
    return '%s' if db_url.startswith('postgresql') else '?'


def get_setups():
    """获取所有版型"""
    return query_all("SELECT * FROM setups WHERE is_active = 1")


def assign_roles(setup, player_ids):
    """根据版型配置随机分配身份

    返回: [(player_id, role_name, role_id), ...]
    """
    role_config = json.loads(setup['role_config'])
    assignments = []

    # 构建身份列表
    role_list = []
    for role_name, count in role_config.items():
        for _ in range(count):
            role_list.append(role_name)

    # 随机打乱并分配
    random.shuffle(role_list)
    selected_players = random.sample(player_ids, min(len(role_list), len(player_ids)))

    for i, role_name in enumerate(role_list):
        if i < len(selected_players):
            role_id = ROLE_IDS.get(role_name)
            if role_id:
                assignments.append((selected_players[i], role_name, role_id))

    return assignments


def pick_random_target(actor_id, all_player_ids, exclude_self=True):
    """随机选择一个目标玩家"""
    candidates = [p for p in all_player_ids if not exclude_self or p != actor_id]
    if not candidates:
        return None
    return random.choice(candidates)


def generate_behaviors(game_id, assignments, all_player_ids):
    """根据玩家身份生成合理的行为序列

    返回: 行为记录数量
    """
    behavior_count = 0
    player_role_map = {pid: (rname, rid) for pid, rname, rid in assignments}
    role_player_map = {}
    for pid, rname, rid in assignments:
        role_player_map.setdefault(rname, []).append(pid)

    # 找出预言家和狼人（用于站边/冲锋/倒钩的目标选择）
    prophet_players = role_player_map.get('预言家', [])
    wolf_players = role_player_map.get('狼人', []) + role_player_map.get('狼王', []) + role_player_map.get('白狼王', [])

    # 为每个玩家生成行为
    for player_id, role_name, role_id in assignments:
        tendencies = ROLE_BEHAVIOR_TENDENCIES.get(role_name, [])
        if not tendencies:
            continue

        # 每个玩家生成1-4条行为
        num_behaviors = random.randint(1, 4)
        for _ in range(num_behaviors):
            # 噪声：有一定概率随机选择行为，而不是按身份倾向
            if random.random() < NOISE_RATE:
                action_name = random.choice(list(ACTION_IDS.keys()))
                action_id = ACTION_IDS[action_name]
                needs_target = action_name in ['查杀', '发金水', '站边', '倒钩', '冲锋', '投票', '开枪', '使用解药', '使用毒药', '守护', '质疑']
            else:
                # 按身份倾向选择行为
                action_name, prob, needs_target = random.choice(tendencies)
                if random.random() > prob:
                    continue  # 概率不满足，跳过
                action_id = ACTION_IDS[action_name]

            # 选择目标
            target_id = None
            if needs_target:
                if action_name == '站边' and prophet_players:
                    # 站边：优先站边预言家
                    if role_name in ['狼人', '狼王', '白狼王'] and random.random() < 0.6:
                        # 狼人有概率站边狼队友（悍跳狼）
                        wolf_prophets = [p for p in prophet_players if p in wolf_players]
                        if wolf_prophets:
                            target_id = random.choice(wolf_prophets)
                        else:
                            target_id = random.choice(prophet_players)
                    else:
                        target_id = random.choice(prophet_players)
                elif action_name == '冲锋' and wolf_players:
                    # 冲锋：站边狼队友
                    wolf_prophets = [p for p in prophet_players if p in wolf_players]
                    if wolf_prophets:
                        target_id = random.choice(wolf_prophets)
                    else:
                        target_id = random.choice(wolf_players)
                elif action_name == '倒钩' and prophet_players:
                    # 倒钩：站边真预言家（非狼人预言家）
                    real_prophets = [p for p in prophet_players if p not in wolf_players]
                    if real_prophets:
                        target_id = random.choice(real_prophets)
                    else:
                        target_id = random.choice(prophet_players)
                elif action_name == '查杀':
                    # 查杀：预言家查杀狼人，狼人查杀好人
                    if role_name == '预言家' and wolf_players:
                        target_id = random.choice(wolf_players)
                    elif role_name in ['狼人', '狼王', '白狼王']:
                        good_players = [p for p in all_player_ids if p not in wolf_players and p != player_id]
                        if good_players:
                            target_id = random.choice(good_players)
                    else:
                        target_id = pick_random_target(player_id, all_player_ids)
                elif action_name == '发金水':
                    # 发金水：预言家发好人，狼人可能发狼队友或好人
                    if role_name == '预言家':
                        good_players = [p for p in all_player_ids if p not in wolf_players and p != player_id]
                        if good_players:
                            target_id = random.choice(good_players)
                    elif role_name in ['狼人', '狼王', '白狼王']:
                        if random.random() < 0.5 and wolf_players:
                            target_id = random.choice([p for p in wolf_players if p != player_id])
                        else:
                            good_players = [p for p in all_player_ids if p not in wolf_players and p != player_id]
                            if good_players:
                                target_id = random.choice(good_players)
                    else:
                        target_id = pick_random_target(player_id, all_player_ids)
                else:
                    target_id = pick_random_target(player_id, all_player_ids)

            # 插入行为记录
            execute_write(
                f"""INSERT INTO behavior_records
                    (game_id, actor_id, target_id, action_id, actor_role_id, actor_camp, round_number)
                    VALUES ({_ph()}, {_ph()}, {_ph()}, {_ph()}, {_ph()}, {_ph()}, {_ph()})""",
                (game_id, player_id, target_id, action_id, role_id,
                 _get_camp(role_name), random.randint(1, 3))
            )
            behavior_count += 1

    return behavior_count


def _get_camp(role_name):
    """根据身份名获取阵营"""
    if role_name in ['预言家', '女巫', '猎人', '白痴', '守卫', '平民']:
        return '好人'
    elif role_name in ['狼人', '狼王', '白狼王']:
        return '狼人'
    else:
        return '第三方'


def confirm_game(game_id, assignments):
    """确认对局，填入所有玩家的真实身份

    这会触发算法自我优化（更新algorithm_weights）
    """
    # 更新game_players表中的真实身份
    for player_id, role_name, role_id in assignments:
        execute_write(
            f"UPDATE game_players SET actual_role_id = {_ph()} WHERE game_id = {_ph()} AND player_id = {_ph()}",
            (role_id, game_id, player_id)
        )

    # 标记对局为已确认
    execute_write(
        f"UPDATE games SET status = 'confirmed', confirmed_at = CURRENT_TIMESTAMP WHERE id = {_ph()}",
        (game_id,)
    )

    # 触发算法自我优化（根据真实身份更新权重）
    try:
        update_weights_from_game(game_id)
    except Exception as e:
        print(f"  警告: 对局 {game_id} 权重更新失败: {e}")


def generate_games(player_ids):
    """生成虚拟对局"""
    setups = get_setups()
    if not setups:
        print("错误：没有可用的版型，请先初始化数据库")
        return

    print(f"\n正在生成 {NUM_GAMES} 局虚拟对局...")
    print(f"可用版型: {[s['name'] for s in setups]}")

    total_behaviors = 0
    for i in range(1, NUM_GAMES + 1):
        # 随机选择版型
        setup = random.choice(setups)

        # 创建对局
        game_code = f"FAKE-{i:04d}"
        game_id = execute_write(
            f"""INSERT INTO games (setup_id, game_code, status, notes)
                VALUES ({_ph()}, {_ph()}, 'in_progress', {_ph()})""",
            (setup['id'], game_code, f"假数据对局 #{i} - {setup['name']}")
        )

        # 分配身份
        assignments = assign_roles(setup, player_ids)

        # 添加对局玩家
        for player_id, role_name, role_id in assignments:
            execute_write(
                f"INSERT INTO game_players (game_id, player_id) VALUES ({_ph()}, {_ph()})",
                (game_id, player_id)
            )

        # 生成行为记录
        behavior_count = generate_behaviors(game_id, assignments, player_ids)
        total_behaviors += behavior_count

        # 确认对局（触发算法自我优化）
        confirm_game(game_id, assignments)

        if i % 20 == 0:
            print(f"  已生成 {i}/{NUM_GAMES} 局，累计 {total_behaviors} 条行为记录")

    print(f"\n对局生成完成！")
    print(f"  总局数: {NUM_GAMES}")
    print(f"  总行为记录: {total_behaviors}")


def main():
    print("=" * 60)
    print("狼人杀身份预测 - 假数据生成脚本")
    print("=" * 60)
    print(f"配置: {NUM_PLAYERS} 玩家, {NUM_GAMES} 对局, 噪声率 {NOISE_RATE*100}%")
    print()

    # 1. 生成玩家
    player_ids = generate_players()

    # 2. 生成对局
    generate_games(player_ids)

    print("\n" + "=" * 60)
    print("假数据生成完成！")
    print("=" * 60)
    print("\n你现在可以:")
    print("  1. 启动本地服务: python app.py")
    print("  2. 访问 http://localhost:5000 查看假数据")
    print("  3. 进入任意对局查看预测结果")
    print("\n清空假数据时执行: clear_fake_data.sql")


if __name__ == "__main__":
    main()
