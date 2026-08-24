"""
玩家关系图与回溯推断模块

功能：
1. 从行为记录自动提取玩家间关系（踩、保、站边、投票、查杀、金水等）
2. 构建玩家关系网络
3. 回溯推断：身份确认后，回溯修正相关玩家概率
4. 关系传播：通过关系网络传播身份概率（标签传播算法）
"""

from db import query_all, query_one, execute_write, ph


# ============================================================
# 关系类型定义
# ============================================================
# 正向关系（保/站边/金水）：source认为target是好人
# 负向关系（踩/投票/查杀）：source认为target是狼人
RELATIONSHIP_TYPES = {
    'check':   {'name': '查杀', 'direction': -1, 'default_strength': 0.9},  # 查杀：极强负向
    'gold':    {'name': '金水', 'direction': 1,  'default_strength': 0.9},  # 金水：极强正向
    'side':    {'name': '站边', 'direction': 1,  'default_strength': 0.7},  # 站边：正向
    'vote':    {'name': '投票', 'direction': -1, 'default_strength': 0.6},  # 投票出：负向
    'attack':  {'name': '踩',   'direction': -1, 'default_strength': 0.5},  # 踩/质疑：负向
    'defend':  {'name': '保',   'direction': 1,  'default_strength': 0.5},  # 保：正向
}

# 行为ID到关系类型的映射
# 基于当前行为库：1跳预言家,2查杀,3发金水,4跳女巫,5跳猎人,6跳守卫,7认平民,
# 8投票,9弃票,10站边,11倒钩,12冲锋,13自爆,14开枪,15使用解药,16使用毒药,
# 17守护,18质疑,19划水
ACTION_TO_RELATIONSHIP = {
    2:  ('check', 0.9),   # 查杀
    3:  ('gold', 0.9),    # 发金水
    8:  ('vote', 0.6),    # 投票
    10: ('side', 0.7),    # 站边
    18: ('attack', 0.5),  # 质疑
    16: ('attack', 0.7),  # 使用毒药（毒某人=认为是狼）
    17: ('defend', 0.5),  # 守护（守某人=认为是好人）
    15: ('defend', 0.3),  # 使用解药（救某人=认为是好人）
}


# ============================================================
# 关系提取
# ============================================================
def extract_relationships(game_id):
    """从对局的行为记录中提取玩家间关系，保存到player_relationships表

    流程：
    1. 先删除该对局已有的关系（重新提取）
    2. 遍历所有行为记录
    3. 对有目标对象的行为，识别关系类型
    4. 保存到player_relationships表

    返回：提取的关系数量
    """
    # 先删除已有关系
    execute_write(f"DELETE FROM player_relationships WHERE game_id = {ph()}", (game_id,))

    # 获取所有行为记录（有目标对象的）
    behaviors = query_all(
        f"""SELECT br.*, a.name as action_name
            FROM behavior_records br
            JOIN actions a ON br.action_id = a.id
            WHERE br.game_id = {ph()} AND br.target_id IS NOT NULL
            ORDER BY br.round_number, br.id""",
        (game_id,)
    )

    if not behaviors:
        return 0

    count = 0
    for behavior in behaviors:
        action_id = behavior['action_id']
        source_id = behavior['actor_id']
        target_id = behavior['target_id']

        # 跳过自己对自己的关系
        if source_id == target_id:
            continue

        # 根据行为ID映射关系类型
        if action_id in ACTION_TO_RELATIONSHIP:
            rel_type, strength = ACTION_TO_RELATIONSHIP[action_id]
        else:
            # 根据行为名称判断是踩还是保
            action_name = behavior.get('action_name', '')
            if any(kw in action_name for kw in ['踩', '质疑', '打', '出', '毒']):
                rel_type, strength = 'attack', 0.5
            elif any(kw in action_name for kw in ['保', '认好', '站边', '金', '守', '救']):
                rel_type, strength = 'defend', 0.5
            else:
                continue  # 无法识别关系类型，跳过

        # 保存关系
        execute_write(
            f"""INSERT INTO player_relationships
                (game_id, source_player_id, target_player_id, relationship_type, strength,
                 round_number, phase, behavior_id)
                VALUES ({ph()}, {ph()}, {ph()}, {ph()}, {ph()}, {ph()}, {ph()}, {ph()})""",
            (game_id, source_id, target_id, rel_type, strength,
             behavior.get('round_number'), behavior.get('phase'), behavior['id'])
        )
        count += 1

    return count


def get_relationship_graph(game_id):
    """获取对局的玩家关系图

    返回：
    {
        'nodes': [{'player_id': int, 'player_name': str}, ...],
        'edges': [{'source': int, 'target': int, 'type': str, 'strength': float, 'direction': int}, ...]
    }
    """
    # 获取对局玩家
    players = query_all(
        f"""SELECT gp.player_id, p.name as player_name
            FROM game_players gp
            JOIN players p ON gp.player_id = p.id
            WHERE gp.game_id = {ph()}""",
        (game_id,)
    )

    # 获取关系
    relationships = query_all(
        f"SELECT * FROM player_relationships WHERE game_id = {ph()} ORDER BY id",
        (game_id,)
    )

    edges = []
    for rel in relationships:
        rel_type = rel['relationship_type']
        type_info = RELATIONSHIP_TYPES.get(rel_type, {'direction': 0, 'name': rel_type})
        edges.append({
            'id': rel['id'],
            'source': rel['source_player_id'],
            'target': rel['target_player_id'],
            'type': rel_type,
            'type_name': type_info['name'],
            'strength': rel['strength'],
            'direction': type_info['direction'],  # 1=正向(保), -1=负向(踩)
            'round_number': rel.get('round_number'),
            'phase': rel.get('phase'),
        })

    return {
        'nodes': [{'player_id': p['player_id'], 'player_name': p['player_name']} for p in players],
        'edges': edges,
    }


# ============================================================
# 回溯推断
# ============================================================
def backtrack_inference(game_id, confirmed_player_id, confirmed_camp, confirmed_role_id=None):
    """回溯推断：当某个玩家的身份被确认后，回溯修正相关玩家的概率

    逻辑：
    1. 如果A被确认是狼人：
       - A保过的人（正向关系）→ 是狼人的概率上升（狼保狼）
       - A踩过的人（负向关系）→ 是好人的概率上升（狼踩好人，做身份）
    2. 如果A被确认是好人：
       - A保过的人（正向关系）→ 是好人的概率上升（好人保好人）
       - A踩过的人（负向关系）→ 是狼人的概率上升（好人踩狼）

    参数：
        game_id: 对局ID
        confirmed_player_id: 被确认身份的玩家ID
        confirmed_camp: 确认的阵营（好人/狼人）
        confirmed_role_id: 确认的具体身份（可选）

    返回：
        修正建议列表 [{player_id, player_name, adjustment, reason}, ...]
    """
    # 获取该玩家作为发起者的所有关系
    relationships = query_all(
        f"""SELECT pr.*, p.name as target_name
            FROM player_relationships pr
            JOIN players p ON pr.target_player_id = p.id
            WHERE pr.game_id = {ph()} AND pr.source_player_id = {ph()}""",
        (game_id, confirmed_player_id)
    )

    if not relationships:
        return []

    adjustments = []
    for rel in relationships:
        target_id = rel['target_player_id']
        target_name = rel['target_name']
        rel_type = rel['relationship_type']
        strength = rel['strength']
        direction = RELATIONSHIP_TYPES.get(rel_type, {}).get('direction', 0)
        type_name = RELATIONSHIP_TYPES.get(rel_type, {}).get('name', rel_type)

        # 根据确认的阵营和关系方向，推断目标玩家的阵营倾向
        if confirmed_camp == '狼人':
            if direction > 0:  # 狼保了某人 → 大概率是狼（狼保狼）
                adjustment = 'wolf_up'
                reason = f'{confirmed_camp}玩家{type_name}了{target_name}，狼保狼概率高'
            elif direction < 0:  # 狼踩了某人 → 大概率是好人（狼踩好人做身份）
                adjustment = 'good_up'
                reason = f'{confirmed_camp}玩家{type_name}了{target_name}，狼踩好人做身份概率高'
            else:
                continue
        elif confirmed_camp == '好人':
            if direction > 0:  # 好人保了某人 → 大概率是好人
                adjustment = 'good_up'
                reason = f'{confirmed_camp}玩家{type_name}了{target_name}，好人保好人概率高'
            elif direction < 0:  # 好人踩了某人 → 大概率是狼
                adjustment = 'wolf_up'
                reason = f'{confirmed_camp}玩家{type_name}了{target_name}，好人踩狼概率高'
            else:
                continue
        else:
            continue

        adjustments.append({
            'player_id': target_id,
            'player_name': target_name,
            'adjustment': adjustment,
            'reason': reason,
            'strength': strength,
            'relationship_type': rel_type,
            'relationship_name': type_name,
        })

    return adjustments


# ============================================================
# 关系传播（标签传播算法）
# ============================================================
def propagate_probabilities(game_id, current_predictions, role_camps, iterations=3, alpha=0.1):
    """通过关系网络传播身份概率（标签传播算法）

    逻辑：
    每个玩家的概率会受到其关系网络中其他玩家的影响
    - 如果多个好人倾向的玩家都保了A，那么A是好人的概率上升
    - 如果多个狼人倾向的玩家都踩了A，那么A是好人的概率上升（狼踩好人）

    参数：
        game_id: 对局ID
        current_predictions: 当前预测结果 {player_id: {role_id: probability, ...}, ...}
        role_camps: 身份到阵营的映射 {role_id: '好人'/'狼人', ...}
        iterations: 传播迭代次数
        alpha: 传播强度（0-1，越大影响越大）

    返回：
        传播后的预测结果（格式同current_predictions）
    """
    if not current_predictions:
        return current_predictions

    # 获取关系图
    graph = get_relationship_graph(game_id)
    edges = graph['edges']

    if not edges:
        return current_predictions

    # 计算每个玩家的好人概率和狼人概率
    def get_camp_prob(player_id, camp):
        probs = current_predictions.get(player_id, {}).get('probabilities', {})
        total = 0
        for role_id, prob in probs.items():
            if role_camps.get(role_id) == camp:
                total += prob
        return total

    # 复制当前预测
    result = {}
    for player_id, data in current_predictions.items():
        result[player_id] = {
            'probabilities': dict(data.get('probabilities', {})),
        }

    # 迭代传播
    for _ in range(iterations):
        new_result = {}
        for player_id in result:
            probs = dict(result[player_id]['probabilities'])

            # 收集所有指向该玩家的关系（其他玩家对该玩家的态度）
            incoming_edges = [e for e in edges if e['target'] == player_id]

            if not incoming_edges:
                new_result[player_id] = {'probabilities': probs}
                continue

            # 计算影响因子
            good_influence = 0  # 好人对该玩家的正向影响总和
            wolf_influence = 0  # 狼人对该玩家的正向影响总和

            for edge in incoming_edges:
                source_id = edge['source']
                direction = edge['direction']  # 1=保, -1=踩
                strength = edge['strength']

                source_good_prob = get_camp_prob(source_id, '好人')
                source_wolf_prob = get_camp_prob(source_id, '狼人')

                # 好人保 → 该玩家是好人概率上升
                # 好人踩 → 该玩家是狼人概率上升
                # 狼人保 → 该玩家是狼人概率上升（狼保狼）
                # 狼人踩 → 该玩家是好人概率上升（狼踩好人）

                if direction > 0:  # 保
                    good_influence += source_good_prob * strength
                    wolf_influence += source_wolf_prob * strength
                elif direction < 0:  # 踩
                    wolf_influence += source_good_prob * strength
                    good_influence += source_wolf_prob * strength

            # 归一化影响
            total_influence = good_influence + wolf_influence
            if total_influence > 0:
                good_ratio = good_influence / total_influence
                wolf_ratio = wolf_influence / total_influence

                # 应用传播（alpha控制影响强度）
                for role_id in probs:
                    camp = role_camps.get(role_id)
                    if camp == '好人':
                        probs[role_id] = probs[role_id] * (1 - alpha) + probs[role_id] * alpha * good_ratio * 2
                    elif camp == '狼人':
                        probs[role_id] = probs[role_id] * (1 - alpha) + probs[role_id] * alpha * wolf_ratio * 2

            # 重新归一化
            total = sum(probs.values())
            if total > 0:
                for role_id in probs:
                    probs[role_id] = round(probs[role_id] / total, 6)

            new_result[player_id] = {'probabilities': probs}

        result = new_result

    return result
