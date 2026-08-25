"""
重新学习所有已确认对局的个性化行为统计

遍历所有状态为"已确认"的对局，对每个对局调用update_personalized_stats_after_game，
把之前的历史对局数据也学习到player_behavior_stats表中。

使用方法：
    python backfill_personalized_stats.py
"""

import sys
import os

# 确保能导入项目模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db import query_all, ph
from prediction import update_personalized_stats


def main():
    print("=" * 60)
    print("重新学习所有已确认对局的个性化行为统计")
    print("=" * 60)
    
    # 1. 查询所有状态为"已确认"的对局（只查询id，不依赖其他字段，确保跨环境兼容）
    confirmed_games = query_all(
        "SELECT id FROM games WHERE status = " + ph() + " ORDER BY id",
        ('已确认',)
    )
    
    if not confirmed_games:
        print("没有找到已确认的对局")
        return
    
    print(f"\n找到 {len(confirmed_games)} 个已确认的对局")
    print("-" * 60)
    
    # 2. 清空现有的个性化行为统计（避免重复计算）
    print("\n清空现有的个性化行为统计...")
    from db import execute_write
    execute_write("DELETE FROM player_behavior_stats")
    print("已清空 player_behavior_stats 表")
    
    # 3. 对每个对局调用update_personalized_stats_after_game
    total_updated = 0
    success_count = 0
    fail_count = 0
    
    for game in confirmed_games:
        game_id = game['id']
        game_name = f'对局{game_id}'
        
        print(f"\n处理对局 {game_id}: {game_name}")
        
        try:
            updated_count = update_personalized_stats(game_id)
            if updated_count > 0:
                print(f"  ✓ 成功更新 {updated_count} 个玩家的统计")
                total_updated += updated_count
                success_count += 1
            else:
                print(f"  - 没有玩家有真实身份或行为记录（跳过）")
                success_count += 1
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            fail_count += 1
    
    # 4. 统计结果
    print("\n" + "=" * 60)
    print("处理完成！")
    print("=" * 60)
    print(f"总对局数: {len(confirmed_games)}")
    print(f"成功: {success_count}")
    print(f"失败: {fail_count}")
    print(f"更新的玩家统计总数: {total_updated}")
    
    # 5. 查询当前的统计数据量
    stats_count = query_all("SELECT COUNT(*) as cnt FROM player_behavior_stats")
    if stats_count:
        print(f"\n当前 player_behavior_stats 表中有 {stats_count[0]['cnt']} 条记录")
    
    # 6. 查询有多少个玩家有统计数据
    player_stats = query_all("SELECT COUNT(DISTINCT player_id) as cnt FROM player_behavior_stats")
    if player_stats:
        print(f"涉及 {player_stats[0]['cnt']} 个玩家")
    
    print("\n" + "=" * 60)
    print("所有历史对局的个性化行为统计已重新学习完成！")
    print("以后新确认的对局会自动学习。")
    print("=" * 60)


if __name__ == '__main__':
    main()
