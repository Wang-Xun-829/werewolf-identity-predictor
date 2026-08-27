"""
逻辑一致性与视角分析模块（第二阶段高级推理）

功能：
1. 立场矛盾检测：检测玩家的言行是否一致
2. 信息量溢出检测：开视角狼人识别（狼人有信息优势）
3. 逻辑链条分析：玩家之间的复杂关系分析
4. 预测依据分析：每个玩家的预测结果由哪些行为影响

使用行为语义属性（action_type）判断行为类型，支持用户自定义行为。
"""

from db import query_all, query_one, ph


# ============================================================
# 辅助函数：获取行为语义属性
# ============================================================

def get_action_semantics():
    """获取所有行为的语义属性"""
    actions = query_all("SELECT id, name, action_type, determine_content, has_result_status FROM actions")
    return {a['id']: a for a in actions}


def is_attack_action(action_id, action_semantics):
    """判断是否是踩人/攻击行为"""
    action = action_semantics.get(action_id)
    if not action:
        return False
    name = action['name']
    return '踩' in name or '质疑' in name or action['action_type'] == 'stance_expression' and '踩' in name


def is_defend_action(action_id, action_semantics):
    """判断是否是保人/防守行为"""
    action = action_semantics.get(action_id)
    if not action:
        return False
    name = action['name']
    return '保' in name or '守护' in name or '解药' in name


def is_side_action(action_id, action_semantics):
    """判断是否是站边行为"""
    action = action_semantics.get(action_id)
    if not action:
        return False
    name = action['name']
    return '站边' in name


def is_vote_action(action_id, action_semantics):
    """判断是否是投票行为"""
    action = action_semantics.get(action_id)
    if not action:
        return False
    return action['action_type'] == 'vote_action' or '票' in action['name']


def is_prophet_claim_action(action_id, action_semantics):
    """判断是否是跳预言家行为"""
    action = action_semantics.get(action_id)
    if not action:
        return False
    name = action['name']
    return '跳预言家' in name or (action['action_type'] == 'identity_claim' and '预言家' in name)


# ============================================================
# 1. 立场矛盾检测
# ============================================================

def detect_contradictions(game_id):
    """检测玩家的立场矛盾

    检测规则：
    1. A认为B是狼（踩B），但投票时投了C（没有投B）→ 矛盾
    2. A认为B是好人（保B），但投票时投了B → 矛盾
    3. A跳预言家给B金水，但后来又说B是狼 → 矛盾

    返回：
        list of dict: 矛盾列表
    """
    contradictions = []
    action_semantics = get_action_semantics()

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
        stances = {}
        # 记录该玩家的投票行为
        votes = []

        for b in actor_behaviors:
            action_id = b['action_id']
            target_id = b['target_id']

            # 踩人行为
            if is_attack_action(action_id, action_semantics) and target_id:
                if target_id not in stances:
                    stances[target_id] = []
                stances[target_id].append({
                    'type': 'attack',
                    'round': b['round_number'],
                    'phase': b['phase'],
                    'behavior_id': b['id']
                })

            # 保人行为
            if is_defend_action(action_id, action_semantics) and target_id:
                if target_id not in stances:
                    stances[target_id] = []
                stances[target_id].append({
                    'type': 'defend',
                    'round': b['round_number'],
                    'phase': b['phase'],
                    'behavior_id': b['id']
                })

            # 投票行为
            if is_vote_action(action_id, action_semantics) and target_id:
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

            for attack in attack_stances:
                for vote in votes:
                    if (vote['round'] > attack['round']) or \
                       (vote['round'] == attack['round'] and vote['phase'] != attack['phase']):
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
                            break

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
    2. 站边心目中的预言家，但同时认定站边同一预言家的另一个玩家是倒钩狼
    3. 对未发言玩家做出确定性判断
    4. 没有合理逻辑就做出高度确定性的判断

    逻辑依据：
    - 好人没有信息优势，不会过早对其他玩家的身份下死判断
    - 狼人有信息优势（知道谁是狼谁是好人），所以发言可能会暴露这种信息差

    返回：
        list of dict: 信息量溢出检测结果
    """
    leaks = []
    action_semantics = get_action_semantics()

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
            if is_side_action(action_id, action_semantics) and target_id:
                sided_prophets.append({
                    'target_id': target_id,
                    'round': b['round_number'],
                    'phase': b['phase']
                })

            # 踩人行为
            if is_attack_action(action_id, action_semantics) and target_id:
                attacked_players.append({
                    'target_id': target_id,
                    'round': b['round_number'],
                    'phase': b['phase']
                })

        # 检测规则1：站边预言家A，但同时在第一天就认定站边A的另一个玩家B是倒钩狼
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
                    if is_side_action(ob['action_id'], action_semantics) and ob['target_id'] == prophet_id:
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
    action_semantics = get_action_semantics()

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

    # 构建玩家关系网络
    # relationships[actor_id][target_id] = list of {'type': 'attack'/'defend'/'side', 'round': ...}
    relationships = {}

    for b in behaviors:
        actor_id = b['actor_id']
        target_id = b['target_id']
        action_id = b['action_id']

        if not target_id:
            continue

        if actor_id not in relationships:
            relationships[actor_id] = {}
        if target_id not in relationships[actor_id]:
            relationships[actor_id][target_id] = []

        rel_type = None
        if is_attack_action(action_id, action_semantics):
            rel_type = 'attack'
        elif is_defend_action(action_id, action_semantics):
            rel_type = 'defend'
        elif is_side_action(action_id, action_semantics):
            rel_type = 'side'

        if rel_type:
            relationships[actor_id][target_id].append({
                'type': rel_type,
                'round': b['round_number'],
                'phase': b['phase']
            })

    # 检测规则1：A踩B，保C，D踩C保A → D的嫌疑很大
    # 逻辑：D认为保狼人的人（A）是好人，说明D可能开了视角
    for a_id, a_rels in relationships.items():
        # A踩的人
        a_attacks = [t for t, rels in a_rels.items() if any(r['type'] == 'attack' for r in rels)]
        # A保的人
        a_defends = [t for t, rels in a_rels.items() if any(r['type'] == 'defend' for r in rels)]

        if not a_attacks or not a_defends:
            continue

        for c_id in a_defends:
            # 找踩C的人D
            for d_id, d_rels in relationships.items():
                if d_id == a_id:
                    continue
                # D踩C
                d_attacks_c = c_id in d_rels and any(r['type'] == 'attack' for r in d_rels[c_id])
                # D保A
                d_defends_a = a_id in d_rels and any(r['type'] == 'defend' for r in d_rels[a_id])

                if d_attacks_c and d_defends_a:
                    a_name = player_names.get(a_id, f'玩家{a_id}')
                    c_name = player_names.get(c_id, f'玩家{c_id}')
                    d_name = player_names.get(d_id, f'玩家{d_id}')
                    chains.append({
                        'type': '逻辑链条异常',
                        'description': f'{d_name}踩了{c_name}，但同时保了{a_name}，而{a_name}保了{c_name}。除非{d_name}能解释为什么认为{c_name}是{a_name}保错的狼，并且还能认为{a_name}是好人，否则{d_name}的嫌疑很大（认为保狼人的人是好人，可能开了视角）',
                        'severity': 'high',
                        'players': [a_id, c_id, d_id]
                    })

    return chains


# ============================================================
# 4. 综合分析入口
# ============================================================

def analyze_game_logic(game_id):
    """综合分析对局的逻辑一致性和视角

    返回：
        dict: 包含矛盾、信息量溢出、逻辑链条的综合分析结果
    """
    contradictions = detect_contradictions(game_id)
    information_leaks = detect_information_leak(game_id)
    logic_chains = analyze_logic_chains(game_id)

    # 计算每个玩家的嫌疑分数
    player_suspicion = {}
    for c in contradictions:
        actor_id = c['actor_id']
        if actor_id not in player_suspicion:
            player_suspicion[actor_id] = 0
        player_suspicion[actor_id] += 2 if c['severity'] == 'high' else 1

    for leak in information_leaks:
        actor_id = leak['actor_id']
        if actor_id not in player_suspicion:
            player_suspicion[actor_id] = 0
        player_suspicion[actor_id] += 3 if leak['severity'] == 'high' else 2

    return {
        'contradictions': contradictions,
        'information_leaks': information_leaks,
        'logic_chains': logic_chains,
        'player_suspicion': player_suspicion,
        'total_issues': len(contradictions) + len(information_leaks) + len(logic_chains)
    }


# ============================================================
# 5. 预测依据分析
# ============================================================

def get_prediction_evidence(game_id, player_id):
    """获取某个玩家的预测依据

    分析哪些行为和推导影响了该玩家的身份预测。

    返回：
        dict: 预测依据分析结果
    """
    action_semantics = get_action_semantics()

    # 获取该玩家的所有行为
    behaviors = query_all(
        f"""SELECT br.*, a.name as action_name, a.action_type, a.default_weight
           FROM behavior_records br
           JOIN actions a ON br.action_id = a.id
           WHERE br.game_id = {ph()} AND br.actor_id = {ph()}
           ORDER BY br.round_number, br.phase, br.id""",
        (game_id, player_id)
    )

    # 获取以该玩家为目标的行为
    target_behaviors = query_all(
        f"""SELECT br.*, a.name as action_name, a.action_type, p.name as actor_name
           FROM behavior_records br
           JOIN actions a ON br.action_id = a.id
           JOIN players p ON br.actor_id = p.id
           WHERE br.game_id = {ph()} AND br.target_id = {ph()}
           ORDER BY br.round_number, br.phase, br.id""",
        (game_id, player_id)
    )

    # 获取逻辑分析结果
    logic_result = analyze_game_logic(game_id)

    # 筛选与该玩家相关的逻辑问题
    player_issues = []
    for c in logic_result['contradictions']:
        if c['actor_id'] == player_id:
            player_issues.append(c)
    for leak in logic_result['information_leaks']:
        if leak['actor_id'] == player_id:
            player_issues.append(leak)
    for chain in logic_result['logic_chains']:
        if player_id in chain.get('players', []):
            player_issues.append(chain)

    # 分析行为对预测的影响
    behavior_evidence = []
    for b in behaviors:
        action_name = b['action_name']
        action_type = b['action_type']
        weight = b['default_weight']
        result_status = b.get('result_status', 'unknown')

        # 分析这个行为对身份预测的影响
        influence = 'neutral'
        influence_desc = ''

        if action_type == 'identity_confirm':
            if '自爆' in action_name:
                influence = 'werewolf'
                influence_desc = '自爆行为直接确认为狼人'
        elif action_type == 'identity_claim':
            if '预言家' in action_name:
                influence = 'prophet_candidate'
                influence_desc = '跳预言家，成为预言家候选人'
            elif '女巫' in action_name:
                influence = 'witch_candidate'
                influence_desc = '跳女巫，成为女巫候选人'
        elif action_type == 'stance_expression':
            if result_status == 'correct':
                influence = 'good'
                influence_desc = f'{action_name}（正确），增加好人概率'
            elif result_status == 'incorrect':
                influence = 'werewolf'
                influence_desc = f'{action_name}（错误），增加狼人概率'
            else:
                influence_desc = f'{action_name}，待确认'

        behavior_evidence.append({
            'behavior_id': b['id'],
            'action_name': action_name,
            'action_type': action_type,
            'weight': weight,
            'result_status': result_status,
            'round': b['round_number'],
            'phase': b['phase'],
            'influence': influence,
            'influence_desc': influence_desc
        })

    return {
        'player_id': player_id,
        'behaviors': behavior_evidence,
        'target_behaviors': target_behaviors,
        'logic_issues': player_issues,
        'suspicion_score': logic_result['player_suspicion'].get(player_id, 0)
    }
