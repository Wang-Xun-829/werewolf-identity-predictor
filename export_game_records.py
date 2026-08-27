"""
读取线上对局记录，并用文字形式输出
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# 设置线上数据库连接
os.environ['DATABASE_URL'] = "postgresql://neondb_owner:npg_u1rFnCVX7NTx@ep-restless-feather-azyo5mej-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

from db import query_all, query_one, ph


def list_games():
    """列出所有对局"""
    games = query_all("""
        SELECT g.*, s.name as setup_name
        FROM games g
        LEFT JOIN setups s ON g.setup_id = s.id
        ORDER BY g.id DESC
    """)
    return games


def get_game_detail(game_id):
    """获取对局详细信息"""
    # 对局基本信息
    game = query_one("""
        SELECT g.*, s.name as setup_name, s.role_config
        FROM games g
        LEFT JOIN setups s ON g.setup_id = s.id
        WHERE g.id = """ + ph(), (game_id,))

    if not game:
        return None

    # 对局玩家
    players = query_all("""
        SELECT gp.*, p.name as player_name, r.name as role_name, r.camp as role_camp
        FROM game_players gp
        JOIN players p ON gp.player_id = p.id
        LEFT JOIN roles r ON gp.actual_role_id = r.id
        WHERE gp.game_id = """ + ph() + " ORDER BY gp.seat_number NULLS LAST, gp.id", (game_id,))

    # 行为记录
    behaviors = query_all("""
        SELECT b.*,
               pa.name as actor_name,
               pt.name as target_name,
               a.name as action_name,
               r.name as actor_role_name
        FROM behavior_records b
        JOIN players pa ON b.actor_id = pa.id
        LEFT JOIN players pt ON b.target_id = pt.id
        JOIN actions a ON b.action_id = a.id
        LEFT JOIN roles r ON b.actor_role_id = r.id
        WHERE b.game_id = """ + ph() + " ORDER BY b.round_number NULLS LAST, b.id", (game_id,))

    # 确认身份
    confirmed = query_all("""
        SELECT ci.*, p.name as player_name, r.name as role_name, r.camp as role_camp
        FROM game_confirmed_identities ci
        JOIN players p ON ci.player_id = p.id
        LEFT JOIN roles r ON ci.role_id = r.id
        WHERE ci.game_id = """ + ph() + " ORDER BY ci.confirmed_at", (game_id,))

    return {
        'game': game,
        'players': players,
        'behaviors': behaviors,
        'confirmed': confirmed
    }


def format_game_detail(detail):
    """格式化对局详细信息为文字"""
    game = detail['game']
    players = detail['players']
    behaviors = detail['behaviors']
    confirmed = detail['confirmed']

    output = []
    output.append("=" * 70)
    output.append(f"对局 #{game['id']} - {game.get('game_code', '未命名')}")
    output.append("=" * 70)

    # 基本信息
    output.append("\n【基本信息】")
    output.append(f"  对局编号: {game.get('game_code', '未命名')}")
    output.append(f"  版型: {game.get('setup_name', '未指定')}")
    output.append(f"  玩家数: {game.get('player_count', len(players))}")
    output.append(f"  状态: {game.get('status', '未知')}")
    output.append(f"  创建时间: {game.get('created_at', '未知')}")
    if game.get('finished_at'):
        output.append(f"  结束时间: {game['finished_at']}")
    if game.get('confirmed_at'):
        output.append(f"  确认时间: {game['confirmed_at']}")

    # 玩家列表
    output.append("\n【玩家列表】")
    for i, p in enumerate(players, 1):
        seat = p.get('seat_number')
        seat_str = f"座位{seat}" if seat else "无座位"
        role_str = f" -> {p['role_name']} ({p['role_camp']})" if p.get('role_name') else ""
        output.append(f"  {i}. {p['player_name']} ({seat_str}){role_str}")

    # 确认身份
    if confirmed:
        output.append("\n【确认身份】")
        for c in confirmed:
            role_str = c['role_name'] if c.get('role_name') else c.get('camp', '未知')
            reason_str = f"（原因: {c['reason']}）" if c.get('reason') else ""
            output.append(f"  - {c['player_name']} -> {role_str}{reason_str}")

    # 行为记录
    output.append(f"\n【行为记录】（共 {len(behaviors)} 条）")
    current_round = None
    for i, b in enumerate(behaviors, 1):
        round_num = b.get('round_number')
        if round_num != current_round:
            if round_num:
                output.append(f"\n  --- 第 {round_num} 天 ---")
            else:
                output.append(f"\n  --- 未指定轮次 ---")
            current_round = round_num

        # 行为信息
        actor = b['actor_name']
        action = b['action_name']
        target = f" -> {b['target_name']}" if b.get('target_name') else ""
        phase = f"[{b['phase']}]" if b.get('phase') else ""
        role_declare = f"（声明: {b['actor_role_name']}）" if b.get('actor_role_name') else ""
        camp_declare = f"（声明阵营: {b['actor_camp']}）" if b.get('actor_camp') else ""
        notes = f"（备注: {b['notes']}）" if b.get('notes') else ""

        # 结果状态
        result_status = b.get('result_status', 'unknown')
        if result_status == 'correct':
            status_str = " ✓正确"
        elif result_status == 'incorrect':
            status_str = " ✕错误"
        else:
            status_str = ""

        output.append(f"  {i}. {phase} {actor} {action}{target}{role_declare}{camp_declare}{notes}{status_str}")

    output.append("\n" + "=" * 70)
    return "\n".join(output)


def main():
    print("正在连接线上数据库...")

    # 列出所有对局
    games = list_games()
    print(f"\n找到 {len(games)} 个对局:\n")

    for i, g in enumerate(games, 1):
        status = g.get('status', '未知')
        setup = g.get('setup_name', '未指定版型')
        code = g.get('game_code', '未命名')
        print(f"  {i}. 对局 #{g['id']} - {code} ({setup}) - 状态: {status}")

    # 让用户选择对局
    print("\n" + "=" * 70)
    print("请输入要查看的对局编号（ID），或输入 'all' 查看所有对局:")
    choice = input("> ").strip()

    if choice.lower() == 'all':
        # 查看所有对局
        for g in games:
            detail = get_game_detail(g['id'])
            if detail:
                print("\n" + format_game_detail(detail))
    else:
        try:
            game_id = int(choice)
            detail = get_game_detail(game_id)
            if detail:
                print("\n" + format_game_detail(detail))

                # 保存到文件
                filename = f"game_{game_id}_record.txt"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(format_game_detail(detail))
                print(f"\n对局记录已保存到文件: {filename}")
            else:
                print(f"未找到对局 #{game_id}")
        except ValueError:
            print("输入无效，请输入有效的对局编号")


if __name__ == "__main__":
    main()
