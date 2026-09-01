# -*- coding: utf-8 -*-
"""
狼人杀对局记录导出脚本
导出所有对局的详细信息，包括：
- 对局基本信息
- 对局玩家列表
- 行为记录
- 确认身份
- 预测结果
"""

import json
import os
import sys
from datetime import datetime

# 添加项目目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import query_all, query_one, ph, DB_TYPE, init_db


def export_game(game_id):
    """导出单个对局的详细信息"""
    # 对局基本信息
    game = query_one("SELECT * FROM games WHERE id = " + ph(), (game_id,))
    if not game:
        return None
    
    # 对局玩家列表
    players = query_all("""
        SELECT gp.*, p.name as player_name, r.name as actual_role_name, r.camp as actual_camp
        FROM game_players gp
        JOIN players p ON gp.player_id = p.id
        LEFT JOIN roles r ON gp.actual_role_id = r.id
        WHERE gp.game_id = """ + ph() + " ORDER BY gp.seat_number", (game_id,))
    
    # 行为记录
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
    
    # 确认身份
    confirmed_identities = query_all("""
        SELECT ci.*, p.name as player_name, r.name as role_name, r.camp as role_camp
        FROM game_confirmed_identities ci
        JOIN players p ON ci.player_id = p.id
        LEFT JOIN roles r ON ci.role_id = r.id
        WHERE ci.game_id = """ + ph() + " ORDER BY ci.confirmed_at", (game_id,))
    
    # 预测结果（最新的）
    predictions = query_all("""
        SELECT pr.*, p.name as player_name, r.name as role_name, r.camp as role_camp
        FROM predictions pr
        JOIN players p ON pr.player_id = p.id
        JOIN roles r ON pr.role_id = r.id
        WHERE pr.game_id = """ + ph() + " ORDER BY pr.player_id, pr.probability DESC", (game_id,))
    
    # 系统推导事实（表可能不存在，增加错误处理）
    derived_facts = []
    try:
        derived_facts = query_all("""
            SELECT * FROM game_derived_facts WHERE game_id = """ + ph() + " ORDER BY id", (game_id,))
    except Exception as e:
        print(f"  警告: 无法读取推导事实表: {e}")
    
    return {
        'game_info': game,
        'players': players,
        'behaviors': behaviors,
        'confirmed_identities': confirmed_identities,
        'predictions': predictions,
        'derived_facts': derived_facts
    }


def export_all_games():
    """导出所有对局"""
    # 初始化数据库
    init_db()
    
    # 获取所有对局
    games = query_all("SELECT * FROM games ORDER BY id")
    
    if not games:
        print("数据库中没有对局记录")
        return None
    
    print(f"找到 {len(games)} 个对局")
    
    all_games_data = []
    for game in games:
        print(f"正在导出对局 {game['id']}: {game.get('name', '未命名')}")
        game_data = export_game(game['id'])
        if game_data:
            all_games_data.append(game_data)
    
    return {
        'export_time': datetime.now().isoformat(),
        'database_type': DB_TYPE,
        'total_games': len(all_games_data),
        'games': all_games_data
    }


def save_to_json(data, filename):
    """保存为JSON文件"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print(f"已保存到 {filename}")


def save_to_csv(data, filename):
    """保存为CSV文件（行为记录）"""
    import csv
    
    with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        
        # 写入表头
        writer.writerow([
            '对局ID', '对局名称', '玩家座位', '行为发起者', '行为目标',
            '行为名称', '行为类型', '发起者声明身份', '轮次', '阶段',
            '结果状态', '备注', '创建时间'
        ])
        
        # 写入数据
        for game_data in data['games']:
            game_info = game_data['game_info']
            for behavior in game_data['behaviors']:
                # 获取发起者座位号
                actor_seat = ''
                for p in game_data['players']:
                    if p['player_id'] == behavior['actor_id']:
                        actor_seat = p.get('seat_number', '')
                        break
                
                writer.writerow([
                    game_info['id'],
                    game_info.get('name', ''),
                    actor_seat,
                    behavior.get('actor_name', ''),
                    behavior.get('target_name', ''),
                    behavior.get('action_name', ''),
                    behavior.get('action_type', ''),
                    behavior.get('actor_role_name', ''),
                    behavior.get('round_number', ''),
                    behavior.get('phase', ''),
                    behavior.get('result_status', ''),
                    behavior.get('notes', ''),
                    behavior.get('created_at', '')
                ])
    
    print(f"行为记录已保存到 {filename}")


if __name__ == '__main__':
    print("=" * 60)
    print("狼人杀对局记录导出工具")
    print("=" * 60)
    
    # 导出所有对局
    data = export_all_games()
    
    if data:
        # 创建输出目录
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'exports')
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # 保存为JSON
        json_filename = os.path.join(output_dir, f'werewolf_games_{timestamp}.json')
        save_to_json(data, json_filename)
        
        # 保存为CSV（行为记录）
        csv_filename = os.path.join(output_dir, f'werewolf_behaviors_{timestamp}.csv')
        save_to_csv(data, csv_filename)
        
        print("\n" + "=" * 60)
        print("导出完成！")
        print(f"JSON文件: {json_filename}")
        print(f"CSV文件: {csv_filename}")
        print("=" * 60)
