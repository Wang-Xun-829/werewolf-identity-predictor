"""
行为结果状态自动推测模块

当玩家身份被确认后，自动推测相关行为的结果状态：
- unknown: 未知（默认）
- correct: 正确（投对/保对/踩对/站对）
- incorrect: 错误（投错/保错/踩错/站错）

核心逻辑：
1. 当某个玩家被确认为狼人时：
   - 所有保该玩家的行为 -> incorrect（保错人）
   - 所有踩该玩家的行为 -> correct（踩对人）
   - 所有站边该玩家（如果该玩家是悍跳狼）的行为 -> incorrect（站错边）
   - 所有投票投该玩家的行为 -> correct（投对）

2. 当某个玩家被确认为好人时：
   - 所有保该玩家的行为 -> correct（保对人）
   - 所有踩该玩家的行为 -> incorrect（踩错人）
   - 所有站边该玩家（如果该玩家是真预言家）的行为 -> correct（站对边）
   - 所有投票投该玩家的行为 -> incorrect（投错）

3. 当某个玩家被确认为具体身份时（如预言家、女巫等）：
   - 根据具体身份进行更精确的推测
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from db import query_all, query_one, execute_write, ph


# 行为类型关键词映射
# 用于识别行为是保人、踩人、站边还是投票
ACTION_KEYWORDS = {
    'defend': ['保', '保护', '站边', '认好', '金水'],  # 保人/站边类
    'attack': ['踩', '打', '攻击', '查杀', '质疑', '怀疑'],  # 踩人/攻击类
    'vote': ['投票', '投', '放逐', '警徽票'],  # 投票类
    'side': ['站边', '站', '支持'],  # 站边类
}


def get_action_category(action_name):
    """
    根据行为名称判断行为类别

    返回:
        str: 'defend'（保人/站边）、'attack'（踩人/攻击）、'vote'（投票）、'side'（站边）、'other'（其他）
    """
    name = action_name or ''

    # 检查是否是投票类
    for keyword in ACTION_KEYWORDS['vote']:
        if keyword in name:
            return 'vote'

    # 检查是否是站边类
    for keyword in ACTION_KEYWORDS['side']:
        if keyword in name:
            return 'side'

    # 检查是否是保人类
    for keyword in ACTION_KEYWORDS['defend']:
        if keyword in name:
            return 'defend'

    # 检查是否是踩人类
    for keyword in ACTION_KEYWORDS['attack']:
        if keyword in name:
            return 'attack'

    return 'other'


def auto_infer_result_status(game_id, confirmed_player_id, confirmed_camp=None, confirmed_role_id=None):
    """
    当玩家身份被确认后，自动推测相关行为的结果状态

    参数:
        game_id: 对局ID
        confirmed_player_id: 被确认身份的玩家ID
        confirmed_camp: 确认的阵营（'好人'/'狼人'/'第三方'），可选
        confirmed_role_id: 确认的具体身份ID，可选

    返回:
        dict: 推测结果统计
    """
    print(f"[行为结果推测] 开始推测对局 {game_id} 中玩家 {confirmed_player_id} 相关行为的结果状态")

    # 获取确认的玩家信息
    confirmed_player = query_one(
        "SELECT * FROM players WHERE id = " + ph(),
        (confirmed_player_id,)
    )
    if not confirmed_player:
        print(f"[行为结果推测] 玩家 {confirmed_player_id} 不存在")
        return {'updated': 0, 'details': []}

    # 获取确认的身份信息
    confirmed_role_name = None
    if confirmed_role_id:
        role = query_one(
            "SELECT * FROM roles WHERE id = " + ph(),
            (confirmed_role_id,)
        )
        if role:
            confirmed_role_name = role['name']
            if not confirmed_camp:
                confirmed_camp = role['camp']

    print(f"[行为结果推测] 玩家: {confirmed_player['name']}, 阵营: {confirmed_camp}, 身份: {confirmed_role_name}")

    if not confirmed_camp:
        print(f"[行为结果推测] 未确认阵营，无法推测结果状态")
        return {'updated': 0, 'details': []}

    # 获取所有与该玩家相关的行为记录（作为目标对象）
    related_behaviors = query_all(
        f"""SELECT b.*, a.name as action_name
            FROM behavior_records b
            JOIN actions a ON b.action_id = a.id
            WHERE b.game_id = {ph()} AND b.target_id = {ph()}
            ORDER BY b.id""",
        (game_id, confirmed_player_id)
    )

    print(f"[行为结果推测] 找到 {len(related_behaviors)} 条与该玩家相关的行为记录")

    updated_count = 0
    details = []

    for behavior in related_behaviors:
        action_name = behavior['action_name']
        action_category = get_action_category(action_name)
        current_status = behavior.get('result_status', 'unknown')

        # 如果已经有明确的结果状态，跳过
        if current_status in ('correct', 'incorrect'):
            continue

        # 根据行为类别和确认的阵营推测结果状态
        new_status = None
        reason = ''

        if action_category == 'defend':  # 保人/站边
            if confirmed_camp == '狼人':
                new_status = 'incorrect'
                reason = f"保了狼人 {confirmed_player['name']}"
            elif confirmed_camp == '好人':
                new_status = 'correct'
                reason = f"保了好人 {confirmed_player['name']}"

        elif action_category == 'attack':  # 踩人/攻击
            if confirmed_camp == '狼人':
                new_status = 'correct'
                reason = f"踩了狼人 {confirmed_player['name']}"
            elif confirmed_camp == '好人':
                new_status = 'incorrect'
                reason = f"踩了好人 {confirmed_player['name']}"

        elif action_category == 'vote':  # 投票
            if confirmed_camp == '狼人':
                new_status = 'correct'
                reason = f"投了狼人 {confirmed_player['name']}"
            elif confirmed_camp == '好人':
                new_status = 'incorrect'
                reason = f"投了好人 {confirmed_player['name']}"

        elif action_category == 'side':  # 站边
            # 站边的结果状态取决于被站边的玩家是否是真预言家
            # 这里需要特殊处理，如果确认的玩家是预言家，则站边他是对的
            if confirmed_role_name == '预言家':
                new_status = 'correct'
                reason = f"站边了真预言家 {confirmed_player['name']}"
            elif confirmed_camp == '狼人' and confirmed_role_name in ('狼人', '狼王', '白狼王', '狼美人', '机械狼'):
                # 如果确认的玩家是狼人且跳了预言家，则站边他是错的
                # 这里简化处理，如果是狼人阵营且有跳预言家的行为，则认为站边是错的
                has_prophet_claim = query_one(
                    f"""SELECT 1 FROM behavior_records b
                        JOIN actions a ON b.action_id = a.id
                        WHERE b.game_id = {ph()} AND b.actor_id = {ph()}
                        AND a.name LIKE {ph()} LIMIT 1""",
                    (game_id, confirmed_player_id, '%预言家%')
                )
                if has_prophet_claim:
                    new_status = 'incorrect'
                    reason = f"站边了悍跳狼 {confirmed_player['name']}"

        # 更新行为记录的结果状态
        if new_status:
            execute_write(
                f"UPDATE behavior_records SET result_status = {ph()} WHERE id = {ph()}",
                (new_status, behavior['id'])
            )
            updated_count += 1
            details.append({
                'behavior_id': behavior['id'],
                'action_name': action_name,
                'actor_id': behavior['actor_id'],
                'old_status': current_status,
                'new_status': new_status,
                'reason': reason
            })
            print(f"[行为结果推测] 更新行为 {behavior['id']} ({action_name}): {current_status} -> {new_status}, 原因: {reason}")

    # 特殊处理：如果确认的玩家是预言家，还需要处理站边他的行为
    if confirmed_role_name == '预言家':
        # 查找所有站边该玩家的行为
        side_behaviors = query_all(
            f"""SELECT b.*, a.name as action_name
                FROM behavior_records b
                JOIN actions a ON b.action_id = a.id
                WHERE b.game_id = {ph()} AND b.target_id = {ph()}
                AND (a.name LIKE {ph()} OR a.name LIKE {ph()})
                ORDER BY b.id""",
            (game_id, confirmed_player_id, '%站边%', '%站%')
        )
        for behavior in side_behaviors:
            current_status = behavior.get('result_status', 'unknown')
            if current_status in ('correct', 'incorrect'):
                continue
            execute_write(
                f"UPDATE behavior_records SET result_status = 'correct' WHERE id = {ph()}",
                (behavior['id'],)
            )
            updated_count += 1
            print(f"[行为结果推测] 更新站边行为 {behavior['id']}: {current_status} -> correct, 原因: 站边了真预言家")

    print(f"[行为结果推测] 完成，共更新 {updated_count} 条行为记录")
    return {'updated': updated_count, 'details': details}


def reset_result_status(game_id):
    """
    重置对局中所有行为记录的结果状态为unknown

    参数:
        game_id: 对局ID
    """
    print(f"[行为结果推测] 重置对局 {game_id} 的所有行为结果状态")
    execute_write(
        f"UPDATE behavior_records SET result_status = 'unknown' WHERE game_id = {ph()}",
        (game_id,)
    )
    print(f"[行为结果推测] 重置完成")


def re_infer_all_result_status(game_id):
    """
    根据对局中所有已确认的身份，重新推测所有行为记录的结果状态

    参数:
        game_id: 对局ID

    返回:
        dict: 推测结果统计
    """
    print(f"[行为结果推测] 重新推测对局 {game_id} 的所有行为结果状态")

    # 先重置所有行为记录的结果状态
    reset_result_status(game_id)

    # 获取所有已确认的身份
    confirmed_identities = query_all(
        f"""SELECT ci.*, r.name as role_name, r.camp as role_camp
            FROM game_confirmed_identities ci
            LEFT JOIN roles r ON ci.role_id = r.id
            WHERE ci.game_id = {ph()}
            ORDER BY ci.confirmed_at""",
        (game_id,)
    )

    print(f"[行为结果推测] 找到 {len(confirmed_identities)} 个已确认的身份")

    total_updated = 0
    for identity in confirmed_identities:
        player_id = identity['player_id']
        camp = identity.get('camp') or identity.get('role_camp')
        role_id = identity.get('role_id')

        result = auto_infer_result_status(game_id, player_id, camp, role_id)
        total_updated += result['updated']

    print(f"[行为结果推测] 重新推测完成，共更新 {total_updated} 条行为记录")
    return {'updated': total_updated}


if __name__ == "__main__":
    # 测试代码
    if len(sys.argv) > 1:
        game_id = int(sys.argv[1])
        re_infer_all_result_status(game_id)
    else:
        print("用法: python result_status_inference.py <game_id>")
