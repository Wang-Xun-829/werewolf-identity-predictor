"""
预测结果可解释性模块

功能：
1. 行为贡献分析：哪些行为导致了某个身份概率升高/降低
2. 权重影响分析：每个行为的权重如何影响概率
3. 个性化系数分析：玩家历史行为倾向如何影响预测
4. 关系传播分析：其他玩家的关系如何影响该玩家的概率
5. 逻辑分析：立场矛盾、信息量溢出等如何影响判断
6. 教学建议：给出学习建议，帮助用户独立分析
"""

from db import query_all, query_one, ph


# 身份特征行为定义（使用行为ID，用于教学解释）
# 行为ID映射：1=跳预言家, 2=查杀, 3=发金水, 4=跳女巫, 5=跳猎人,
# 6=跳守卫, 7=认平民, 8=投票, 9=弃票, 10=站边, 11=倒钩, 12=冲锋,
# 13=自爆, 14=开枪, 15=使用解药, 16=使用毒药, 17=守护, 18=质疑, 19=划水
ROLE_FEATURE_BEHAVIORS = {
    1: {  # 预言家
        'name': '预言家',
        'positive_behaviors': [1, 3, 2],  # 跳预言家、发金水、查杀
        'negative_behaviors': [19, 9],  # 划水、弃票
        'description': '预言家应该主动起跳，报出查验信息，积极带队。'
    },
    2: {  # 女巫
        'name': '女巫',
        'positive_behaviors': [4, 15, 16],  # 跳女巫、使用解药、使用毒药
        'negative_behaviors': [19],  # 划水
        'description': '女巫有解药和毒药，应该在关键时刻跳明身份，使用技能。'
    },
    3: {  # 猎人
        'name': '猎人',
        'positive_behaviors': [5, 10],  # 跳猎人、站边
        'negative_behaviors': [19, 9],  # 划水、弃票
        'description': '猎人可以开枪带人，应该态度强硬，不怕被投。'
    },
    4: {  # 守卫
        'name': '守卫',
        'positive_behaviors': [6, 17],  # 跳守卫、守护
        'negative_behaviors': [1],  # 跳预言家
        'description': '守卫每晚可以守护一个人，应该隐藏身份，关键时刻跳明。'
    },
    6: {  # 平民
        'name': '平民',
        'positive_behaviors': [7, 19],  # 认平民、划水
        'negative_behaviors': [1, 4, 5, 6],  # 跳预言家、跳女巫、跳猎人、跳守卫
        'description': '平民没有特殊技能，应该认真分析，跟随预言家投票。'
    },
    7: {  # 狼人
        'name': '狼人',
        'positive_behaviors': [2, 16, 13],  # 查杀、使用毒药、自爆
        'negative_behaviors': [7],  # 认平民
        'description': '狼人需要隐藏身份，可能会悍跳预言家，或者倒钩站边真预言家。'
    },
    8: {  # 狼王
        'name': '狼王',
        'positive_behaviors': [5, 10, 13],  # 跳猎人、站边、自爆
        'negative_behaviors': [19],  # 划水
        'description': '狼王出局可以开枪带人，类似猎人，但属于狼人阵营。'
    },
    9: {  # 白狼王
        'name': '白狼王',
        'positive_behaviors': [13, 1],  # 自爆、跳预言家
        'negative_behaviors': [19],  # 划水
        'description': '白狼王可以自爆带走一人，通常会主动起跳或找机会自爆。'
    }
}


def get_player_prediction_explanation(game_id, player_id):
    """获取某个玩家预测结果的详细解释

    参数：
        game_id: 对局ID
        player_id: 玩家ID

    返回：
        dict: 详细解释
    """
    explanation = {
        'player_id': player_id,
        'player_name': '',
        'behaviors': [],
        'behavior_analysis': [],
        'role_analysis': {},
        'logic_analysis': [],
        'teaching_suggestions': []
    }

    # 获取玩家名称
    player = query_one("SELECT name FROM players WHERE id = " + ph(), (player_id,))
    if player:
        explanation['player_name'] = player['name']

    # 获取该玩家的所有行为记录
    behaviors = query_all(
        f"""SELECT b.*, a.name as action_name, a.default_weight, a.parent_id,
                   p.name as target_name, r.name as actor_role_name
            FROM behavior_records b
            JOIN actions a ON b.action_id = a.id
            LEFT JOIN players p ON b.target_id = p.id
            LEFT JOIN roles r ON b.actor_role_id = r.id
            WHERE b.game_id = {ph()} AND b.actor_id = {ph()}
            ORDER BY b.round_number, b.phase, b.id""",
        (game_id, player_id)
    )

    explanation['behaviors'] = behaviors

    # 分析每个行为对身份预测的影响
    for b in behaviors:
        action_name = b['action_name']
        weight = b['default_weight'] or 1.0

        # 分析这个行为对各个身份的影响
        affected_roles = []
        for role_id, role_info in ROLE_FEATURE_BEHAVIORS.items():
            if action_name in role_info['positive_behaviors']:
                affected_roles.append({
                    'role_id': role_id,
                    'role_name': role_info['name'],
                    'effect': 'positive',
                    'weight': weight
                })
            elif action_name in role_info['negative_behaviors']:
                affected_roles.append({
                    'role_id': role_id,
                    'role_name': role_info['name'],
                    'effect': 'negative',
                    'weight': weight
                })

        explanation['behavior_analysis'].append({
            'behavior_id': b['id'],
            'action_name': action_name,
            'target_name': b.get('target_name'),
            'round': b['round_number'],
            'phase': b['phase'],
            'weight': weight,
            'affected_roles': affected_roles,
            'notes': b.get('notes')
        })

    # 获取该玩家的个性化统计数据
    personalized_stats = query_all(
        f"SELECT * FROM player_behavior_stats WHERE player_id = {ph()}",
        (player_id,)
    )

    if personalized_stats:
        explanation['personalized_stats'] = personalized_stats

    # 获取该玩家相关的逻辑分析结果
    # 立场矛盾
    contradictions = query_all(
        f"""SELECT * FROM behavior_records
            WHERE game_id = {ph()} AND actor_id = {ph()}
            AND action_id IN (8, 18)""",
        (game_id, player_id)
    )

    # 生成教学建议
    teaching_suggestions = generate_teaching_suggestions(behaviors, personalized_stats)
    explanation['teaching_suggestions'] = teaching_suggestions

    return explanation


def generate_teaching_suggestions(behaviors, personalized_stats):
    """生成教学建议

    参数：
        behaviors: 玩家行为列表
        personalized_stats: 个性化统计数据

    返回：
        list: 教学建议列表
    """
    suggestions = []

    if not behaviors:
        suggestions.append({
            'type': 'info',
            'title': '暂无行为数据',
            'content': '该玩家目前还没有录入任何行为，无法进行详细分析。建议继续观察并录入行为。'
        })
        return suggestions

    # 分析行为数量
    behavior_count = len(behaviors)
    if behavior_count < 3:
        suggestions.append({
            'type': 'warning',
            'title': '行为数据较少',
            'content': f'该玩家目前只有{behavior_count}条行为记录，预测结果可能不够准确。建议继续观察更多行为。'
        })

    # 分析是否有跳身份行为
    jump_actions = [b for b in behaviors if b['action_id'] in [1, 4, 5, 6]]
    if jump_actions:
        jump_names = [b['action_name'] for b in jump_actions]
        suggestions.append({
            'type': 'info',
            'title': '跳身份行为',
            'content': f'该玩家有跳身份行为：{"、".join(jump_names)}。跳身份是重要的身份线索，但要注意狼人也可能悍跳。需要结合后续行为和投票来判断真假。'
        })

    # 分析投票行为
    vote_actions = [b for b in behaviors if b['action_id'] == 8]
    if vote_actions:
        suggestions.append({
            'type': 'info',
            'title': '投票行为',
            'content': f'该玩家有{len(vote_actions)}次投票记录。投票是非常重要的身份线索，狼人的投票往往会有团队性。建议分析该玩家的投票是否与其他玩家一致，是否有跟风或反常投票。'
        })

    # 分析站边行为
    side_actions = [b for b in behaviors if b['action_id'] == 10]
    if side_actions:
        suggestions.append({
            'type': 'info',
            'title': '站边行为',
            'content': f'该玩家有站边行为。站边是重要的身份线索，但要注意倒钩狼的存在。建议结合该玩家的发言和投票来判断是真站边还是倒钩。'
        })

    # 分析划水行为
    idle_actions = [b for b in behaviors if b['action_id'] == 19]
    if idle_actions:
        suggestions.append({
            'type': 'warning',
            'title': '划水行为',
            'content': f'该玩家有{len(idle_actions)}次划水记录。划水可能是平民不知道说什么，也可能是狼人刻意隐藏身份。需要结合其他行为综合判断。'
        })

    # 个性化统计建议
    if personalized_stats:
        # 使用count字段（数据库中的字段名），而不是sample_count
        total_samples = sum(s.get('count', 0) for s in personalized_stats)
        total_games = sum(s.get('game_count', 0) for s in personalized_stats)
        if total_samples >= 10:
            suggestions.append({
                'type': 'success',
                'title': '个性化数据充足',
                'content': f'该玩家已有{total_samples}条历史行为记录，涉及{total_games}局对局，系统可以根据该玩家的个人行为倾向进行更准确的预测。建议继续积累数据，预测会越来越准确。'
            })
        else:
            suggestions.append({
                'type': 'info',
                'title': '个性化数据积累中',
                'content': f'该玩家目前只有{total_samples}条历史行为记录，涉及{total_games}局对局，个性化预测还不够准确。建议在更多对局中观察该玩家，积累数据后预测会更准确。'
            })

    # 通用学习建议
    suggestions.append({
        'type': 'tip',
        'title': '分析技巧',
        'content': '分析玩家身份时，建议综合考虑：1) 跳身份行为（真假需要验证）；2) 投票行为（最诚实的线索）；3) 站边行为（注意倒钩）；4) 发言内容（逻辑是否一致）；5) 行为变化（前后是否矛盾）。不要仅凭单一行为下结论，要综合多个行为和全局视角。'
    })

    return suggestions


def get_role_teaching_content(role_id):
    """获取某个身份的教学内容

    参数：
        role_id: 身份ID

    返回：
        dict: 教学内容
    """
    if role_id in ROLE_FEATURE_BEHAVIORS:
        return ROLE_FEATURE_BEHAVIORS[role_id]
    return None
