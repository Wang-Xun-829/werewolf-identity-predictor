"""
逻辑一致性与视角分析模块

功能：
1. 立场矛盾检测：检测玩家的言行是否一致
2. 信息量溢出检测：开视角狼人识别（狼人有信息优势）
3. 逻辑链条分析：玩家之间的复杂关系分析
"""

from db import query_all, query_one, ph


# ============================================================
# 1. 立场矛盾检测
# ============================================================

def detect_contradictions(game_id):
    """检测玩家的立场矛盾

    检测规则：
    1. A认为B是狼（踩B），但投票时投了C（没有投B）→ 矛盾
    2. A认为B是好人（保B），但投票时投了B → 矛盾
    3. A跳预言家给B金水，但后来又说B是狼 → 矛盾
    4. A跳女巫给B银水，但后来又说B是狼 → 矛盾

    返回：
        list of dict: 矛盾列表
    """
    contradictions = []

    # 获取所有行为记录
    behaviors = query_all(
        f"SELECT * FROM behavior_records WHERE game_id = {ph()} ORDER BY round_number, phase, id",
        (game_id,)
    )

    if not behaviors:
        return contradictions

    # 按玩家分组
    player_behaviors = {}
    for b in behaviors:
        actor_id = b['actor_id']
        if actor_id not in player_behaviors:
            player_behaviors[actor_id] = []
        player_behaviors[actor_id].append(b)

    # 获取玩家名称
    players = query_all("SELECT id, name FROM players")
    player_names = {p['id']: p['name'] for p in players}

    # 检测每个玩家的矛盾
    for actor_id, actor_behaviors in player_behaviors.items():
        actor_name = player_names.get(actor_id, f'玩家{actor_id}')

        # 记录该玩家对其他玩家的立场（踩/保）
        # key: target_id, value: list of {'type': 'attack'/'defend', 'round': ..., 'phase': ...}
        stances = {}

        # 记录该玩家的投票行为
        votes = []

        for b in actor_behaviors:
            action_id = b['action_id']
            target_id = b['target_id']

            # 踩人行为（质疑、攻击）
            if action_id in [18, 16] and target_id:  # 质疑、使用毒药
                if target_id not in stances:
                    stances[target_id] = []
                stances[target_id].append({
                    'type': 'attack',
                    'round': b['round_number'],
                    'phase': b['phase'],
                    'behavior_id': b['id']
                })

            # 保人行为（使用解药、守护、站边）
            if action_id in [15, 17, 10] and target_id:  # 使用解药、守护、站边
                if target_id not in stances:
                    stances[target_id] = []
                stances[target_id].append({
                    'type': 'defend',
                    'round': b['round_number'],
                    'phase': b['phase'],
                    'behavior_id': b['id']
                })

            # 投票行为
            if action_id == 8 and target_id:  # 投票
                votes.append({
                    'target_id': target_id,
                    'round': b['round_number'],
                    'phase': b['phase'],
                    'behavior_id': b['id']
                })

        # 检测矛盾1：踩了B但投票投了C（没有投B）
        for target_id, target_stances in stances.items():
            attack_stances = [s for s in target_stances if s['type'] == 'attack']
            if not attack_stances:
                continue

            # 找到踩B之后的投票
            for attack in attack_stances:
                for vote in votes:
                    # 投票在踩之后
                    if (vote['round'] > attack['round']) or \
                       (vote['round'] == attack['round'] and vote['phase'] != attack['phase']):
                        # 投票没有投B
                        if vote['target_id'] != target_id:
                            target_name = player_names.get(target_id, f'玩家{target_id}')
                            vote_target_name = player_names.get(vote['target_id'], f'玩家{vote["target_id"]}')
                            contradictions.append({
                                'type': '言行不一',
                                'actor_id': actor_id,
                                'actor_name': actor_name,
                                'description': f'{actor_name}在第{attack["round"]}轮踩了{target_name}，但在第{vote["round"]}轮投票时投了{vote_target_name}（没有投{target_name}）',
                                'severity': 'medium',
                                'round': vote['round'],
                                'phase': vote['phase']
                            })
                            break  # 只记录一次

        # 检测矛盾2：保了B但投票投了B
        for target_id, target_stances in stances.items():
            defend_stances = [s for s in target_stances if s['type'] == 'defend']
            if not defend_stances:
                continue

            for defend in defend_stances:
                for vote in votes:
                    if (vote['round'] > defend['round']) or \
                       (vote['round'] == defend['round'] and vote['phase'] != defend['phase']):
                        if vote['target_id'] == target_id:
                            target_name = player_names.get(target_id, f'玩家{target_id}')
                            contradictions.append({
                                'type': '言行不一',
                                'actor_id': actor_id,
                                'actor_name': actor_name,
                                'description': f'{actor_name}在第{defend["round"]}轮保了{target_name}，但在第{vote["round"]}轮投票时投了{target_name}',
                                'severity': 'high',
                                'round': vote['round'],
                                'phase': vote['phase']
                            })
                            break

    return contradictions


# ============================================================
# 2. 信息量溢出检测（开视角狼人识别）
# ============================================================

def detect_information_leak(game_id):
    """检测信息量溢出（开视角狼人识别）

    检测规则：
    1. 过早认定某个玩家是倒钩狼（第一天警下发言就认定D是倒钩狼）
    2. 对某个玩家的身份判断过于确定（没有足够依据就100%认定）
    3. 站边心目中的预言家，但同时认定站边同一预言家的另一个玩家是倒钩狼

    逻辑依据：
    - 好人没有信息优势，不会过早对其他玩家的身份下死判断
    - 狼人有信息优势（知道谁是狼谁是好人），所以发言可能会暴露这种信息差
    - 正常好人可以怀疑某个人是狼，但不会那么早就认定另一个站边同一预言家的人是倒钩狼

    返回：
        list of dict: 信息量溢出检测结果
    """
    leaks = []

    # 获取所有行为记录
    behaviors = query_all(
        f"SELECT * FROM behavior_records WHERE game_id = {ph()} ORDER BY round_number, phase, id",
        (game_id,)
    )

    if not behaviors:
        return leaks

    # 获取玩家名称
    players = query_all("SELECT id, name FROM players")
    player_names = {p['id']: p['name'] for p in players}

    # 按玩家分组
    player_behaviors = {}
    for b in behaviors:
        actor_id = b['actor_id']
        if actor_id not in player_behaviors:
            player_behaviors[actor_id] = []
        player_behaviors[actor_id].append(b)

    # 检测每个玩家的信息量溢出
    for actor_id, actor_behaviors in player_behaviors.items():
        actor_name = player_names.get(actor_id, f'玩家{actor_id}')

        # 记录该玩家站边的预言家
        sided_prophets = []
        # 记录该玩家踩的人
        attacked_players = []

        for b in actor_behaviors:
            action_id = b['action_id']
            target_id = b['target_id']

            # 站边行为
            if action_id == 10 and target_id:  # 站边
                sided_prophets.append({
                    'target_id': target_id,
                    'round': b['round_number'],
                    'phase': b['phase']
                })

            # 踩人行为（质疑）
            if action_id == 18 and target_id:  # 质疑
                attacked_players.append({
                    'target_id': target_id,
                    'round': b['round_number'],
                    'phase': b['phase']
                })

        # 检测规则1：站边预言家A，但同时在第一天就认定站边A的另一个玩家B是倒钩狼
        # 逻辑：正常好人可以怀疑某个人是狼，但不会那么早就认定另一个站边同一预言家的人是倒钩狼
        for sided in sided_prophets:
            if sided['round'] > 1:
                continue  # 只检测第一天

            prophet_id = sided['target_id']

            # 找到其他站边同一预言家的玩家
            other_siders = []
            for other_actor_id, other_behaviors in player_behaviors.items():
                if other_actor_id == actor_id:
                    continue
                for ob in other_behaviors:
                    if ob['action_id'] == 10 and ob['target_id'] == prophet_id:
                        other_siders.append({
                            'player_id': other_actor_id,
                            'round': ob['round_number'],
                            'phase': ob['phase']
                        })
                        break

            # 检测该玩家是否在第一天就踩了这些站边同一预言家的玩家
            for sider in other_siders:
                for attacked in attacked_players:
                    if attacked['target_id'] == sider['player_id'] and attacked['round'] == 1:
                        sider_name = player_names.get(sider['player_id'], f'玩家{sider["player_id"]}')
                        prophet_name = player_names.get(prophet_id, f'玩家{prophet_id}')
                        leaks.append({
                            'type': '信息量溢出',
                            'actor_id': actor_id,
                            'actor_name': actor_name,
                            'description': f'{actor_name}站边{prophet_name}，但在第一天就认定同样站边{prophet_name}的{sider_name}是倒钩狼。正常好人不会那么早认定站边同一预言家的人是倒钩狼，{actor_name}可能开了视角（有多余信息）',
                            'severity': 'high',
                            'round': attacked['round'],
                            'phase': attacked['phase']
                        })
                        break

    return leaks


# ============================================================
# 3. 逻辑链条分析
# ============================================================

def analyze_logic_chains(game_id):
    """分析玩家之间的逻辑链条

    分析规则：
    1. A踩B，保C，D踩C保A → D的嫌疑很大（认为保狼人的人是好人）
    2. 回溯推断：后面确定了某个玩家是狼，那么在一开始不知道他是狼的时候就开始踩他的人里面，大概率是好人多一些

    返回：
        list of dict: 逻辑链条分析结果
    """
    chains = []

    # 获取所有行为记录
    behaviors = query_all(
        f"SELECT * FROM behavior_records WHERE game_id = {ph()} ORDER BY round_number, phase, id",
        (game_id,)
    )

    if not behaviors:
        return chains

    # 获取玩家名称
    players = query_all("SELECT id, name FROM players")
    player_names = {p['id']: p['name'] for p in players}

    # 构建玩家关系图
    # key: (source_id, target_id), value: {'attack': count, 'defend': count}
    relationships = {}

    for b in behaviors:
        action_id = b['action_id']
        source_id = b['actor_id']
        target_id = b['target_id']

        if not target_id:
            continue

        key = (source_id, target_id)
        if key not in relationships:
            relationships[key] = {'attack': 0, 'defend': 0}

        # 踩人行为
        if action_id in [18, 16, 2]:  # 质疑、使用毒药、查杀
            relationships[key]['attack'] += 1

        # 保人行为
        if action_id in [15, 17, 10, 3]:  # 使用解药、守护、站边、发金水
            relationships[key]['defend'] += 1

    # 获取所有玩家ID
    all_player_ids = set()
    for (source_id, target_id) in relationships.keys():
        all_player_ids.add(source_id)
        all_player_ids.add(target_id)

    # 分析逻辑链条：A踩B，保C，D踩C保A → D的嫌疑很大
    for a_id in all_player_ids:
        # 找到A踩的人（B）和A保的人（C）
        a_attacks = []
        a_defends = []
        for (source_id, target_id), rel in relationships.items():
            if source_id == a_id:
                if rel['attack'] > rel['defend']:
                    a_attacks.append(target_id)
                elif rel['defend'] > rel['attack']:
                    a_defends.append(target_id)

        if not a_attacks or not a_defends:
            continue

        for b_id in a_attacks:
            for c_id in a_defends:
                # 找到D：D踩C，D保A
                for d_id in all_player_ids:
                    if d_id == a_id or d_id == b_id or d_id == c_id:
                        continue

                    # D踩C
                    d_c_key = (d_id, c_id)
                    d_c_rel = relationships.get(d_c_key, {'attack': 0, 'defend': 0})
                    if d_c_rel['attack'] <= d_c_rel['defend']:
                        continue

                    # D保A
                    d_a_key = (d_id, a_id)
                    d_a_rel = relationships.get(d_a_key, {'attack': 0, 'defend': 0})
                    if d_a_rel['defend'] <= d_a_rel['attack']:
                        continue

                    # 找到逻辑链条
                    a_name = player_names.get(a_id, f'玩家{a_id}')
                    b_name = player_names.get(b_id, f'玩家{b_id}')
                    c_name = player_names.get(c_id, f'玩家{c_id}')
                    d_name = player_names.get(d_id, f'玩家{d_id}')

                    chains.append({
                        'type': '可疑逻辑链条',
                        'description': f'{a_name}踩{b_name}、保{c_name}；{d_name}踩{c_name}、保{a_name}。{d_name}认为保{c_name}的{a_name}是好人，但又认为{c_name}是狼，除非{d_name}有合理解释，否则{d_name}嫌疑很大',
                        'players': [a_id, b_id, c_id, d_id],
                        'suspect_id': d_id,
                        'suspect_name': d_name,
                        'severity': 'medium'
                    })

    return chains


# ============================================================
# 综合分析入口
# ============================================================

def analyze_game_logic(game_id):
    """综合分析对局的逻辑一致性和视角

    返回：
        dict: {
            'contradictions': 立场矛盾列表,
            'information_leaks': 信息量溢出列表,
            'logic_chains': 逻辑链条列表,
            'summary': 分析总结
        }
    """
    contradictions = detect_contradictions(game_id)
    information_leaks = detect_information_leak(game_id)
    logic_chains = analyze_logic_chains(game_id)

    # 生成分析总结
    total_issues = len(contradictions) + len(information_leaks) + len(logic_chains)
    high_severity = len([c for c in contradictions if c['severity'] == 'high']) + \
                    len([l for l in information_leaks if l['severity'] == 'high']) + \
                    len([c for c in logic_chains if c['severity'] == 'high'])

    summary = {
        'total_issues': total_issues,
        'high_severity': high_severity,
        'contradiction_count': len(contradictions),
        'information_leak_count': len(information_leaks),
        'logic_chain_count': len(logic_chains)
    }

    return {
        'contradictions': contradictions,
        'information_leaks': information_leaks,
        'logic_chains': logic_chains,
        'summary': summary
    }
