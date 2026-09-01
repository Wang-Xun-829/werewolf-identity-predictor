# -*- coding: utf-8 -*-
"""
狼人杀对局记录导出脚本（AI分析格式）
导出所有对局的详细信息，并整理成适合AI分析的Markdown格式
"""

import json
import os
import sys
from datetime import datetime

# 添加项目目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import query_all, query_one, ph, DB_TYPE, init_db


def get_field(row, field, default=None):
    """安全获取字段值，兼容字典、sqlite3.Row和元组"""
    if isinstance(row, dict):
        return row.get(field, default)
    elif hasattr(row, 'keys'):
        # sqlite3.Row对象
        try:
            return row[field]
        except (KeyError, IndexError):
            return default
    elif isinstance(row, tuple):
        # 元组，需要根据字段名查找索引
        # 由于无法直接获取字段名，返回default
        return default
    else:
        return default


def normalize_rows(rows, field_names):
    """将元组列表转换为字典列表"""
    if not rows:
        return []
    if isinstance(rows[0], dict):
        return rows
    if hasattr(rows[0], 'keys'):
        # sqlite3.Row，转换为字典
        return [dict(row) for row in rows]
    if isinstance(rows[0], tuple):
        # 元组，根据字段名转换为字典
        result = []
        for row in rows:
            d = {}
            for i, name in enumerate(field_names):
                if i < len(row):
                    d[name] = row[i]
            result.append(d)
        return result
    return rows


def export_game_for_ai(game_id):
    """导出单个对局的详细信息，整理成AI分析格式"""
    # 对局基本信息
    game = query_one("SELECT * FROM games WHERE id = " + ph(), (game_id,))
    if not game:
        return None
    
    # 对局玩家列表（增加错误处理，兼容旧版本数据库）
    players = []
    player_fields = ['id', 'game_id', 'player_id', 'seat_number', 'actual_role_id', 
                     'is_on_police', 'is_retired', 'is_alive', 'death_type', 
                     'player_name', 'actual_role_name', 'actual_camp']
    try:
        players = query_all("""
            SELECT gp.*, p.name as player_name, r.name as actual_role_name, r.camp as actual_camp
            FROM game_players gp
            JOIN players p ON gp.player_id = p.id
            LEFT JOIN roles r ON gp.actual_role_id = r.id
            WHERE gp.game_id = """ + ph() + " ORDER BY gp.seat_number", (game_id,))
        players = normalize_rows(players, player_fields)
    except Exception as e:
        print(f"  警告: 使用简化版玩家查询（actual_role_id字段不存在）: {e}")
        simple_fields = ['id', 'game_id', 'player_id', 'seat_number', 
                         'is_on_police', 'is_retired', 'is_alive', 'death_type', 'player_name']
        players = query_all("""
            SELECT gp.*, p.name as player_name
            FROM game_players gp
            JOIN players p ON gp.player_id = p.id
            WHERE gp.game_id = """ + ph() + " ORDER BY gp.seat_number", (game_id,))
        players = normalize_rows(players, simple_fields)
        # 为每个玩家添加空的真实身份字段
        for p in players:
            p['actual_role_name'] = '未知'
            p['actual_camp'] = '未知'
    
    # 行为记录
    behavior_fields = ['id', 'game_id', 'actor_id', 'target_id', 'action_id', 
                       'actor_role_id', 'actor_camp', 'round_number', 'phase',
                       'result_status', 'notes', 'created_at',
                       'actor_name', 'target_name', 'action_name', 'action_type', 'actor_role_name']
    behaviors = query_all("""
        SELECT b.*,
               pa.name as actor_name,
               pt.name as target_name,
               a.name as action_name,
               a.action_type,
               r.name as actor_role_name
        FROM behavior_records b
        JOIN players pa ON b.actor_id = pa.id
        LEFT JOIN players pt ON b.target_id = pt.id
        JOIN actions a ON b.action_id = a.id
        LEFT JOIN roles r ON b.actor_role_id = r.id
        WHERE b.game_id = """ + ph() + " ORDER BY b.id", (game_id,))
    behaviors = normalize_rows(behaviors, behavior_fields)
    
    # 确认身份
    confirmed_identities = []
    confirmed_fields = ['id', 'game_id', 'player_id', 'role_id', 'camp', 
                        'reason', 'confirmed_at', 'player_name', 'role_name', 'role_camp']
    try:
        confirmed_identities = query_all("""
            SELECT ci.*, p.name as player_name, r.name as role_name, r.camp as role_camp
            FROM game_confirmed_identities ci
            JOIN players p ON ci.player_id = p.id
            LEFT JOIN roles r ON ci.role_id = r.id
            WHERE ci.game_id = """ + ph() + " ORDER BY ci.confirmed_at", (game_id,))
        confirmed_identities = normalize_rows(confirmed_identities, confirmed_fields)
    except Exception as e:
        print(f"  警告: 无法读取确认身份表: {e}")
    
    # 生成Markdown格式
    md = []
    md.append(f"## 对局 {game['id']}: {get_field(game, 'name', '未命名')}")
    md.append("")
    md.append(f"- **对局ID**: {game['id']}")
    md.append(f"- **对局名称**: {get_field(game, 'name', '未命名')}")
    md.append(f"- **版型**: {get_field(game, 'setup_id', '未知')}")
    md.append(f"- **玩家数量**: {get_field(game, 'player_count', len(players))}")
    md.append(f"- **状态**: {get_field(game, 'status', '未知')}")
    md.append(f"- **创建时间**: {get_field(game, 'created_at', '未知')}")
    md.append("")
    
    # 玩家列表
    md.append("### 玩家列表")
    md.append("")
    md.append("| 座位号 | 玩家ID | 玩家名称 | 真实身份 | 阵营 | 状态 |")
    md.append("|--------|--------|----------|----------|------|------|")
    for p in players:
        seat = get_field(p, 'seat_number', '-')
        player_id = p['player_id']
        name = p.get('player_name', '未知')
        role = get_field(p, 'actual_role_name', '未知')
        camp = get_field(p, 'actual_camp', '未知')
        is_alive = get_field(p, 'is_alive', True)
        death_type = get_field(p, 'death_type', '')
        status = '存活' if is_alive else f'已出局({death_type})'
        md.append(f"| {seat} | {player_id} | {name} | {role} | {camp} | {status} |")
    md.append("")
    
    # 确认身份
    if confirmed_identities:
        md.append("### 确认身份（逻辑基点）")
        md.append("")
        for ci in confirmed_identities:
            player_name = get_field(ci, 'player_name', '未知')
            role_name = get_field(ci, 'role_name', get_field(ci, 'camp', '未知'))
            reason = get_field(ci, 'reason', '')
            md.append(f"- **{player_name}** 确认为 **{role_name}**" + (f"（原因: {reason}）" if reason else ""))
        md.append("")
    
    # 行为记录
    md.append("### 行为记录（按时间顺序）")
    md.append("")
    md.append("| 序号 | 轮次 | 阶段 | 行为发起者 | 行为目标 | 行为名称 | 行为类型 | 发起者声明身份 | 结果状态 | 备注 |")
    md.append("|------|------|------|------------|----------|----------|----------|----------------|----------|------|")
    for i, b in enumerate(behaviors, 1):
        round_num = get_field(b, 'round_number', '-')
        phase = get_field(b, 'phase', '-')
        actor = get_field(b, 'actor_name', '未知')
        target = get_field(b, 'target_name', '无')
        action = get_field(b, 'action_name', '未知')
        action_type = get_field(b, 'action_type', '-')
        actor_role = get_field(b, 'actor_role_name', '-')
        result_status = get_field(b, 'result_status', 'unknown')
        notes = get_field(b, 'notes', '') or ''
        # 截断过长的备注
        if len(notes) > 50:
            notes = notes[:50] + '...'
        md.append(f"| {i} | {round_num} | {phase} | {actor} | {target} | {action} | {action_type} | {actor_role} | {result_status} | {notes} |")
    md.append("")
    
    # 行为统计
    md.append("### 行为统计")
    md.append("")
    # 按玩家统计行为数量
    player_behavior_count = {}
    for b in behaviors:
        actor = get_field(b, 'actor_name', '未知')
        player_behavior_count[actor] = player_behavior_count.get(actor, 0) + 1
    md.append("**各玩家行为数量**:")
    for player, count in sorted(player_behavior_count.items(), key=lambda x: -x[1]):
        md.append(f"- {player}: {count} 条")
    md.append("")
    
    # 按行为类型统计
    action_type_count = {}
    for b in behaviors:
        atype = b.get('action_type', 'unknown')
        action_type_count[atype] = action_type_count.get(atype, 0) + 1
    md.append("**行为类型统计**:")
    for atype, count in sorted(action_type_count.items(), key=lambda x: -x[1]):
        md.append(f"- {atype}: {count} 条")
    md.append("")
    
    return '\n'.join(md)


def export_all_games_for_ai():
    """导出所有对局，整理成AI分析格式"""
    # 初始化数据库
    init_db()
    
    # 获取所有对局
    game_fields = ['id', 'name', 'setup_id', 'player_count', 'status', 
                   'notes', 'created_at', 'updated_at']
    games = query_all("SELECT * FROM games ORDER BY id")
    games = normalize_rows(games, game_fields)
    
    if not games:
        print("数据库中没有对局记录")
        return None
    
    print(f"找到 {len(games)} 个对局")
    
    all_games_md = []
    all_games_md.append("# 狼人杀对局记录汇总（AI分析格式）")
    all_games_md.append("")
    all_games_md.append(f"**导出时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    all_games_md.append(f"**数据库类型**: {DB_TYPE}")
    all_games_md.append(f"**对局总数**: {len(games)}")
    all_games_md.append("")
    all_games_md.append("---")
    all_games_md.append("")
    
    for game in games:
        print(f"正在导出对局 {game['id']}: {get_field(game, 'name', '未命名')}")
        game_md = export_game_for_ai(game['id'])
        if game_md:
            all_games_md.append(game_md)
            all_games_md.append("")
            all_games_md.append("---")
            all_games_md.append("")
    
    return '\n'.join(all_games_md)


if __name__ == '__main__':
    print("=" * 60)
    print("狼人杀对局记录导出工具（AI分析格式）")
    print("=" * 60)
    
    # 检查是否设置了线上数据库连接
    database_url = os.getenv("DATABASE_URL", "")
    if database_url:
        print(f"检测到线上数据库连接: {database_url[:50]}...")
    else:
        print("警告: 未设置DATABASE_URL环境变量，将使用本地SQLite数据库")
        print("如果需要导出线上数据，请先设置DATABASE_URL环境变量")
    
    print()
    
    # 导出所有对局
    md_content = export_all_games_for_ai()
    
    if md_content:
        # 创建输出目录
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'exports')
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        md_filename = os.path.join(output_dir, f'werewolf_games_ai_analysis_{timestamp}.md')
        
        # 保存为Markdown文件
        with open(md_filename, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print()
        print("=" * 60)
        print("导出完成！")
        print(f"文件路径: {md_filename}")
        print()
        print("使用方法:")
        print("1. 打开上面的Markdown文件")
        print("2. 全选并复制内容")
        print("3. 粘贴给其他AI进行分析")
        print("=" * 60)
