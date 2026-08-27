"""
预言家查验推导模块（完整版）

功能：
1. 识别跳预言家的玩家及其查验信息
2. 唯一性约束：一局游戏中只有一个真预言家
3. 查验链概率传递：起跳玩家的预言家概率相互影响
4. 矛盾检测：检测查验链中的矛盾
5. 基于预言家概率，推导被查验玩家的身份概率
6. 如果起跳玩家被确认为预言家（100%），则查验结果100%确定
   - 查杀目标 = 铁狼人（100%）
   - 金水目标 = 铁好人（100%）

核心逻辑：
- 唯一性约束：一局游戏中只有一个真预言家，起跳玩家的预言家概率互斥
- 查验链：A给B金水/查杀，会影响B的身份概率，进而影响B的预言家概率
- 矛盾检测：A给B金水，B给A查杀等矛盾情况
- 全概率公式：根据起跳玩家的预言家概率，推导被查验玩家的身份概率
"""

from db import query_all, query_one, ph


# 行为ID定义
ACTION_JUMP_PROPHET = 1   # 跳预言家
ACTION_CHECK = 2           # 查杀
ACTION_GOLD = 3            # 发金水

# 预言家身份ID
ROLE_PROPHET = 1

# 神职身份定义（除了平民外，身份唯一）
# key: 身份ID, value: {'name': 身份名称, 'jump_action_id': 跳身份的行为ID}
CLERGY_ROLES = {
    1: {'name': '预言家', 'jump_action_id': 1},
    2: {'name': '女巫', 'jump_action_id': 4},
    3: {'name': '猎人', 'jump_action_id': 5},
    4: {'name': '守卫', 'jump_action_id': 6},
}


def get_prophet_claims(game_id):
    """获取对局中所有跳预言家的玩家及其查验信息

    返回：
        list of dict: [
            {
                'player_id': 起跳玩家ID,
                'player_name': 起跳玩家名称,
                'prophet_probability': 预言家概率,
                'is_confirmed': 是否被确认为预言家,
                'checks': [
                    {
                        'target_id': 目标玩家ID,
                        'target_name': 目标玩家名称,
                        'check_type': '查杀' or '金水',
                        'round_number': 轮次,
                        'phase': 阶段
                    }
                ]
            }
        ]
    """
    # 获取所有跳预言家的行为
    jump_behaviors = query_all(
        f"""SELECT b.*, p.name as actor_name
            FROM behavior_records b
            JOIN players p ON b.actor_id = p.id
            WHERE b.game_id = {ph()} AND b.action_id = {ph()}
            ORDER BY b.id""",
        (game_id, ACTION_JUMP_PROPHET)
    )

    if not jump_behaviors:
        return []

    # 获取所有查验行为（查杀/金水）
    check_behaviors = query_all(
        f"""SELECT b.*, p.name as actor_name, t.name as target_name
            FROM behavior_records b
            JOIN players p ON b.actor_id = p.id
            LEFT JOIN players t ON b.target_id = t.id
            WHERE b.game_id = {ph()} AND b.action_id IN ({ph()}, {ph()}) AND b.target_id IS NOT NULL
            ORDER BY b.id""",
        (game_id, ACTION_CHECK, ACTION_GOLD)
    )

    # 按起跳玩家分组查验
    checks_by_actor = {}
    for cb in check_behaviors:
        actor_id = cb['actor_id']
        if actor_id not in checks_by_actor:
            checks_by_actor[actor_id] = []
        checks_by_actor[actor_id].append({
            'target_id': cb['target_id'],
            'target_name': cb['target_name'],
            'check_type': '查杀' if cb['action_id'] == ACTION_CHECK else '金水',
            'round_number': cb.get('round_number'),
            'phase': cb.get('phase')
        })

    # 获取确认身份列表
    confirmed_identities = query_all(
        f"SELECT * FROM game_confirmed_identities WHERE game_id = {ph()}",
        (game_id,)
    )
    confirmed_prophets = set()
    for ci in confirmed_identities:
        if ci.get('role_id') == ROLE_PROPHET:
            confirmed_prophets.add(ci['player_id'])

    # 构建结果
    result = []
    for jb in jump_behaviors:
        actor_id = jb['actor_id']
        result.append({
            'player_id': actor_id,
            'player_name': jb['actor_name'],
            'prophet_probability': 0,  # 后续由预测结果填充
            'is_confirmed': actor_id in confirmed_prophets,
            'checks': checks_by_actor.get(actor_id, [])
        })

    return result


def apply_uniqueness_constraint(prophet_claims):
    """应用唯一性约束：一局游戏中只有一个真预言家

    逻辑：
    - 所有起跳玩家的预言家概率之和不应超过1
    - 如果超过1，按比例缩放
    - 如果有玩家被确认为预言家（100%），其他玩家的预言家概率=0

    参数：
        prophet_claims: 预言家起跳列表

    返回：
        修改后的prophet_claims
        adjustment_log: 调整日志
    """
    adjustment_log = []

    if not prophet_claims:
        return prophet_claims, adjustment_log

    # 检查是否有被确认为预言家的玩家
    confirmed_prophets = [c for c in prophet_claims if c['is_confirmed']]
    if confirmed_prophets:
        # 有被确认为预言家的玩家，其他玩家的预言家概率=0
        for claim in prophet_claims:
            if claim['is_confirmed']:
                if claim['prophet_probability'] < 1.0:
                    adjustment_log.append({
                        'type': '确认预言家',
                        'player_id': claim['player_id'],
                        'player_name': claim['player_name'],
                        'old_prob': round(claim['prophet_probability'] * 100, 1),
                        'new_prob': 100.0,
                        'description': f"{claim['player_name']}被确认为预言家，预言家概率设为100%"
                    })
                    claim['prophet_probability'] = 1.0
            else:
                if claim['prophet_probability'] > 0:
                    adjustment_log.append({
                        'type': '唯一性约束',
                        'player_id': claim['player_id'],
                        'player_name': claim['player_name'],
                        'old_prob': round(claim['prophet_probability'] * 100, 1),
                        'new_prob': 0.0,
                        'description': f"{confirmed_prophets[0]['player_name']}已确认为预言家，{claim['player_name']}不可能是真预言家，预言家概率设为0%"
                    })
                    claim['prophet_probability'] = 0.0
        return prophet_claims, adjustment_log

    # 没有被确认为预言家的玩家，应用唯一性约束
    total_prob = sum(c['prophet_probability'] for c in prophet_claims)
    if total_prob > 1.0:
        # 概率之和超过1，按比例缩放
        scale = 1.0 / total_prob
        for claim in prophet_claims:
            old_prob = claim['prophet_probability']
            claim['prophet_probability'] = old_prob * scale
            adjustment_log.append({
                'type': '唯一性约束',
                'player_id': claim['player_id'],
                'player_name': claim['player_name'],
                'old_prob': round(old_prob * 100, 1),
                'new_prob': round(claim['prophet_probability'] * 100, 1),
                'description': f"所有起跳玩家预言家概率之和为{round(total_prob*100,1)}%，超过100%，按比例缩放至{round(claim['prophet_probability']*100,1)}%"
            })

    return prophet_claims, adjustment_log


def detect_contradictions(prophet_claims):
    """检测查验链中的矛盾

    检测类型：
    1. 互查矛盾：A给B金水，B给A查杀
    2. 查验冲突：两个预言家对同一个玩家给出不同的查验
    3. 自证矛盾：A给B查杀，B又给A金水（类似互查矛盾）

    参数：
        prophet_claims: 预言家起跳列表

    返回：
        contradictions: 矛盾列表
    """
    contradictions = []

    if not prophet_claims or len(prophet_claims) < 2:
        return contradictions

    # 构建查验映射：(actor_id, target_id) -> check_type
    check_map = {}
    for claim in prophet_claims:
        for check in claim['checks']:
            key = (claim['player_id'], check['target_id'])
            check_map[key] = check['check_type']

    # 检测互查矛盾：A给B金水，B给A查杀
    for claim in prophet_claims:
        for check in claim['checks']:
            a_id = claim['player_id']
            b_id = check['target_id']
            a_to_b = check['check_type']

            # 检查B是否也跳预言家，并给A查验
            b_claim = next((c for c in prophet_claims if c['player_id'] == b_id), None)
            if b_claim:
                b_to_a_check = next((c for c in b_claim['checks'] if c['target_id'] == a_id), None)
                if b_to_a_check:
                    b_to_a = b_to_a_check['check_type']
                    # 检测矛盾：一个金水一个查杀
                    if a_to_b != b_to_a:
                        contradictions.append({
                            'type': '互查矛盾',
                            'player_a': claim['player_name'],
                            'player_b': b_claim['player_name'],
                            'a_to_b': a_to_b,
                            'b_to_a': b_to_a,
                            'description': f"{claim['player_name']}给{b_claim['player_name']}{a_to_b}，但{b_claim['player_name']}给{claim['player_name']}{b_to_a}，两者矛盾"
                        })

    # 检测查验冲突：两个预言家对同一个玩家给出不同的查验
    target_checks = {}
    for claim in prophet_claims:
        for check in claim['checks']:
            target_id = check['target_id']
            if target_id not in target_checks:
                target_checks[target_id] = []
            target_checks[target_id].append({
                'prophet_id': claim['player_id'],
                'prophet_name': claim['player_name'],
                'check_type': check['check_type']
            })

    for target_id, checks in target_checks.items():
        if len(checks) >= 2:
            check_types = set(c['check_type'] for c in checks)
            if len(check_types) > 1:
                # 同一个玩家被不同的预言家给出不同的查验
                target_name = checks[0].get('target_name', '')
                # 从prophet_claims中查找目标玩家名称
                for claim in prophet_claims:
                    for check in claim['checks']:
                        if check['target_id'] == target_id:
                            target_name = check['target_name']
                            break
                contradictions.append({
                    'type': '查验冲突',
                    'target_id': target_id,
                    'target_name': target_name,
                    'checks': checks,
                    'description': f"{target_name}被多个预言家给出不同查验：" + "，".join([f"{c['prophet_name']}给{c['check_type']}" for c in checks])
                })

    return contradictions


def analyze_check_chains(prophet_claims):
    """分析查验链

    识别关键逻辑链条：
    - A给B金水，B又跳预言家 → 查验链
    - A给B查杀，B又跳预言家 → B是悍跳狼（如果A是真预言家）

    参数：
        prophet_claims: 预言家起跳列表

    返回：
        chains: 查验链列表
    """
    chains = []

    if not prophet_claims:
        return chains

    # 构建起跳玩家ID集合
    jumper_ids = set(c['player_id'] for c in prophet_claims)

    # 识别查验链：A给B金水/查杀，B又跳预言家
    for claim in prophet_claims:
        for check in claim['checks']:
            target_id = check['target_id']
            if target_id in jumper_ids:
                # B也跳预言家，形成查验链
                target_claim = next(c for c in prophet_claims if c['player_id'] == target_id)
                chain_type = '金水链' if check['check_type'] == '金水' else '查杀链'
                chains.append({
                    'type': chain_type,
                    'prophet_a': claim['player_name'],
                    'prophet_a_prob': round(claim['prophet_probability'] * 100, 1),
                    'prophet_b': target_claim['player_name'],
                    'prophet_b_prob': round(target_claim['prophet_probability'] * 100, 1),
                    'check_type': check['check_type'],
                    'description': f"{claim['player_name']}（预言家概率{round(claim['prophet_probability']*100,1)}%）给{target_claim['player_name']}（预言家概率{round(target_claim['prophet_probability']*100,1)}%）{check['check_type']}，形成查验链",
                    'logic': _get_chain_logic(claim, target_claim, check['check_type'])
                })

    return chains


def _get_chain_logic(claim_a, claim_b, check_type):
    """获取查验链的逻辑分析

    参数：
        claim_a: 起跳玩家A
        claim_b: 起跳玩家B
        check_type: A给B的查验类型（金水/查杀）

    返回：
        logic: 逻辑分析字符串
    """
    prob_a = claim_a['prophet_probability']
    prob_b = claim_b['prophet_probability']

    if check_type == '金水':
        if prob_a > 0.5:
            return f"如果{claim_a['player_name']}是真预言家，则{claim_b['player_name']}是好人，但{claim_b['player_name']}跳预言家可能是好人乱跳（因为一局只有一个真预言家）"
        else:
            return f"{claim_a['player_name']}预言家概率较低，给{claim_b['player_name']}金水的可信度不高"
    else:  # 查杀
        if prob_a > 0.5:
            return f"如果{claim_a['player_name']}是真预言家，则{claim_b['player_name']}是狼人，{claim_b['player_name']}跳预言家一定是悍跳狼，其查验不可信"
        else:
            return f"{claim_a['player_name']}预言家概率较低，给{claim_b['player_name']}查杀的可信度不高"


def apply_prophet_inference(predictions, role_camps, role_ids, prophet_claims):
    """应用预言家查验推导，调整被查验玩家的身份概率

    完整流程：
    1. 填充每个起跳玩家的预言家概率
    2. 应用唯一性约束
    3. 检测矛盾
    4. 分析查验链
    5. 根据预言家概率，推导被查验玩家的身份概率

    参数：
        predictions: 预测结果字典
        role_camps: 身份阵营映射
        role_ids: 所有身份ID列表
        prophet_claims: 预言家起跳列表

    返回：
        修改后的predictions
        inference_result: 推导结果（包含日志、矛盾、查验链等）
    """
    inference_log = []
    contradictions = []
    chains = []

    if not prophet_claims:
        return predictions, {
            'prophet_claims': [],
            'inference_log': [],
            'contradictions': [],
            'chains': []
        }

    # 1. 填充每个起跳玩家的预言家概率
    for claim in prophet_claims:
        player_id = claim['player_id']
        if player_id in predictions:
            probs = predictions[player_id]['probabilities']
            claim['prophet_probability'] = probs.get(ROLE_PROPHET, 0)

    # 2. 应用唯一性约束
    prophet_claims, uniqueness_log = apply_uniqueness_constraint(prophet_claims)
    inference_log.extend(uniqueness_log)

    # 2.5 身份唯一性推导：如果有玩家被确认为预言家，其他跳预言家的玩家大概率是狼
    # 逻辑：预言家身份唯一，对跳者不可能是真预言家；正常情况下对跳预言家的是悍跳狼
    # 保留10%的可能性是好人乱跳（平民跳预言家）
    confirmed_prophets = [c for c in prophet_claims if c['is_confirmed']]
    if confirmed_prophets:
        for claim in prophet_claims:
            if claim['is_confirmed']:
                continue  # 跳过已确认的预言家
            player_id = claim['player_id']
            if player_id not in predictions:
                continue
            probs = predictions[player_id]['probabilities']
            good_role_ids = [rid for rid in role_ids if role_camps.get(rid) == '好人']
            wolf_role_ids = [rid for rid in role_ids if role_camps.get(rid) == '狼人']

            current_good_prob = sum(probs.get(rid, 0) for rid in good_role_ids)
            current_wolf_prob = sum(probs.get(rid, 0) for rid in wolf_role_ids)

            # 对跳预言家的玩家大概率是狼（90%），保留10%好人乱跳的可能性
            new_wolf_prob = 0.9
            new_good_prob = 0.1

            # 按原比例分配狼人阵营内各身份的概率
            if current_wolf_prob > 0:
                wolf_scale = new_wolf_prob / current_wolf_prob
                for rid in wolf_role_ids:
                    probs[rid] = round(probs.get(rid, 0) * wolf_scale, 6)
            else:
                count = len(wolf_role_ids)
                if count > 0:
                    for rid in wolf_role_ids:
                        probs[rid] = round(new_wolf_prob / count, 6)

            # 按原比例分配好人阵营内各身份的概率（预言家概率设为0，因为身份唯一）
            # 先将预言家概率设为0
            probs[ROLE_PROPHET] = 0.0
            current_good_prob_no_prophet = sum(probs.get(rid, 0) for rid in good_role_ids if rid != ROLE_PROPHET)
            if current_good_prob_no_prophet > 0:
                good_scale = new_good_prob / current_good_prob_no_prophet
                for rid in good_role_ids:
                    if rid != ROLE_PROPHET:
                        probs[rid] = round(probs.get(rid, 0) * good_scale, 6)
            else:
                count = len([rid for rid in good_role_ids if rid != ROLE_PROPHET])
                if count > 0:
                    for rid in good_role_ids:
                        if rid != ROLE_PROPHET:
                            probs[rid] = round(new_good_prob / count, 6)

            # 重新找出最高概率身份
            top_role_id = max(probs, key=probs.get)
            predictions[player_id]['top_role_id'] = top_role_id
            predictions[player_id]['top_probability'] = round(probs[top_role_id], 6)
            predictions[player_id]['probabilities'] = probs

            inference_log.append({
                'type': '身份唯一性推导',
                'prophet_id': confirmed_prophets[0]['player_id'],
                'prophet_name': confirmed_prophets[0]['player_name'],
                'target_id': player_id,
                'target_name': claim['player_name'],
                'old_wolf_prob': round(current_wolf_prob * 100, 1),
                'new_wolf_prob': 90.0,
                'description': f"{confirmed_prophets[0]['player_name']}已确认为预言家，{claim['player_name']}对跳预言家，根据身份唯一性，{claim['player_name']}大概率是悍跳狼（狼人概率从{round(current_wolf_prob*100,1)}%调整为90%）"
            })

    # 3. 检测矛盾
    contradictions = detect_contradictions(prophet_claims)

    # 4. 分析查验链
    chains = analyze_check_chains(prophet_claims)

    # 5. 根据预言家概率，推导被查验玩家的身份概率
    for claim in prophet_claims:
        prophet_prob = claim['prophet_probability']
        is_confirmed = claim['is_confirmed']

        # 如果被确认为预言家，预言家概率=100%
        if is_confirmed:
            prophet_prob = 1.0

        if prophet_prob <= 0:
            continue

        for check in claim['checks']:
            target_id = check['target_id']
            check_type = check['check_type']

            if target_id not in predictions:
                continue

            probs = predictions[target_id]['probabilities']

            if check_type == '金水':
                # 金水：如果A是真预言家，B一定是好人
                good_role_ids = [rid for rid in role_ids if role_camps.get(rid) == '好人']
                wolf_role_ids = [rid for rid in role_ids if role_camps.get(rid) == '狼人']

                current_good_prob = sum(probs.get(rid, 0) for rid in good_role_ids)
                current_wolf_prob = sum(probs.get(rid, 0) for rid in wolf_role_ids)

                # 新的好人概率 = prophet_prob * 1 + (1 - prophet_prob) * current_good_prob
                new_good_prob = prophet_prob * 1.0 + (1 - prophet_prob) * current_good_prob
                new_wolf_prob = 1.0 - new_good_prob

                # 按原比例分配好人阵营内各身份的概率
                if current_good_prob > 0:
                    good_scale = new_good_prob / current_good_prob
                    for rid in good_role_ids:
                        probs[rid] = round(probs.get(rid, 0) * good_scale, 6)
                else:
                    count = len(good_role_ids)
                    if count > 0:
                        for rid in good_role_ids:
                            probs[rid] = round(new_good_prob / count, 6)

                # 按原比例分配狼人阵营内各身份的概率
                if current_wolf_prob > 0:
                    wolf_scale = new_wolf_prob / current_wolf_prob
                    for rid in wolf_role_ids:
                        probs[rid] = round(probs.get(rid, 0) * wolf_scale, 6)
                else:
                    count = len(wolf_role_ids)
                    if count > 0:
                        for rid in wolf_role_ids:
                            probs[rid] = round(new_wolf_prob / count, 6)

                # 记录推导日志
                inference_log.append({
                    'type': '金水推导',
                    'prophet_id': claim['player_id'],
                    'prophet_name': claim['player_name'],
                    'prophet_probability': round(prophet_prob * 100, 1),
                    'is_confirmed': is_confirmed,
                    'target_id': target_id,
                    'target_name': check['target_name'],
                    'old_good_prob': round(current_good_prob * 100, 1),
                    'new_good_prob': round(new_good_prob * 100, 1),
                    'description': f"{claim['player_name']}（预言家概率{round(prophet_prob*100,1)}%）给{check['target_name']}发金水，好人概率从{round(current_good_prob*100,1)}%调整为{round(new_good_prob*100,1)}%"
                })

            elif check_type == '查杀':
                # 查杀：如果A是真预言家，B一定是狼人
                good_role_ids = [rid for rid in role_ids if role_camps.get(rid) == '好人']
                wolf_role_ids = [rid for rid in role_ids if role_camps.get(rid) == '狼人']

                current_good_prob = sum(probs.get(rid, 0) for rid in good_role_ids)
                current_wolf_prob = sum(probs.get(rid, 0) for rid in wolf_role_ids)

                # 新的狼人概率 = prophet_prob * 1 + (1 - prophet_prob) * current_wolf_prob
                new_wolf_prob = prophet_prob * 1.0 + (1 - prophet_prob) * current_wolf_prob
                new_good_prob = 1.0 - new_wolf_prob

                # 按原比例分配好人阵营内各身份的概率
                if current_good_prob > 0:
                    good_scale = new_good_prob / current_good_prob
                    for rid in good_role_ids:
                        probs[rid] = round(probs.get(rid, 0) * good_scale, 6)
                else:
                    count = len(good_role_ids)
                    if count > 0:
                        for rid in good_role_ids:
                            probs[rid] = round(new_good_prob / count, 6)

                # 按原比例分配狼人阵营内各身份的概率
                if current_wolf_prob > 0:
                    wolf_scale = new_wolf_prob / current_wolf_prob
                    for rid in wolf_role_ids:
                        probs[rid] = round(probs.get(rid, 0) * wolf_scale, 6)
                else:
                    count = len(wolf_role_ids)
                    if count > 0:
                        for rid in wolf_role_ids:
                            probs[rid] = round(new_wolf_prob / count, 6)

                # 记录推导日志
                inference_log.append({
                    'type': '查杀推导',
                    'prophet_id': claim['player_id'],
                    'prophet_name': claim['player_name'],
                    'prophet_probability': round(prophet_prob * 100, 1),
                    'is_confirmed': is_confirmed,
                    'target_id': target_id,
                    'target_name': check['target_name'],
                    'old_wolf_prob': round(current_wolf_prob * 100, 1),
                    'new_wolf_prob': round(new_wolf_prob * 100, 1),
                    'description': f"{claim['player_name']}（预言家概率{round(prophet_prob*100,1)}%）给{check['target_name']}发查杀，狼人概率从{round(current_wolf_prob*100,1)}%调整为{round(new_wolf_prob*100,1)}%"
                })

            # 重新找出最高概率身份
            top_role_id = max(probs, key=probs.get)
            predictions[target_id]['top_role_id'] = top_role_id
            predictions[target_id]['top_probability'] = round(probs[top_role_id], 6)
            predictions[target_id]['probabilities'] = probs

    inference_result = {
        'prophet_claims': prophet_claims,
        'inference_log': inference_log,
        'contradictions': contradictions,
        'chains': chains
    }

    return predictions, inference_result


# ============================================================
# 通用身份唯一性推导（适用于所有神职身份）
# ============================================================

def get_clergy_jumpers(game_id):
    """获取所有跳神职身份的玩家

    返回：
        dict: {role_id: [{'player_id': ..., 'player_name': ...}, ...]}
    """
    jumpers = {}
    for role_id, role_info in CLERGY_ROLES.items():
        jump_action_id = role_info['jump_action_id']
        behaviors = query_all(
            f"""SELECT DISTINCT b.actor_id, p.name as player_name
                FROM behavior_records b
                JOIN players p ON b.actor_id = p.id
                WHERE b.game_id = {ph()} AND b.action_id = {ph()}""",
            (game_id, jump_action_id)
        )
        if behaviors:
            jumpers[role_id] = behaviors
    return jumpers


def get_confirmed_clergy(game_id):
    """获取被确认为神职身份的玩家

    返回：
        dict: {role_id: [{'player_id': ..., 'player_name': ...}, ...]}
    """
    confirmed = {}
    confirmed_identities = query_all(
        f"SELECT * FROM game_confirmed_identities WHERE game_id = {ph()}",
        (game_id,)
    )
    for ci in confirmed_identities:
        role_id = ci.get('role_id')
        if role_id and role_id in CLERGY_ROLES:
            if role_id not in confirmed:
                confirmed[role_id] = []
            player = query_one("SELECT name FROM players WHERE id = " + ph(), (ci['player_id'],))
            confirmed[role_id].append({
                'player_id': ci['player_id'],
                'player_name': player['name'] if player else '未知'
            })
    return confirmed


def apply_role_uniqueness(predictions, role_camps, role_ids, game_id):
    """应用通用身份唯一性推导

    逻辑：
    - 对于每个神职身份（预言家、女巫、猎人、守卫），身份唯一
    - 如果有玩家被确认为某个神职身份，其他跳这个身份的玩家大概率是狼
    - 保留10%的可能性是好人配合/乱跳

    参数：
        predictions: 预测结果字典
        role_camps: 身份阵营映射
        role_ids: 所有身份ID列表
        game_id: 对局ID

    返回：
        修改后的predictions
        uniqueness_log: 推导日志列表
    """
    uniqueness_log = []

    jumpers = get_clergy_jumpers(game_id)
    confirmed = get_confirmed_clergy(game_id)

    if not confirmed:
        return predictions, uniqueness_log

    for role_id, confirmed_players in confirmed.items():
        if not confirmed_players:
            continue
        role_name = CLERGY_ROLES[role_id]['name']
        role_jumpers = jumpers.get(role_id, [])
        if not role_jumpers:
            continue

        confirmed_ids = set(p['player_id'] for p in confirmed_players)

        for jumper in role_jumpers:
            player_id = jumper['player_id']
            if player_id in confirmed_ids:
                continue
            if player_id not in predictions:
                continue

            probs = predictions[player_id]['probabilities']
            good_role_ids = [rid for rid in role_ids if role_camps.get(rid) == '好人']
            wolf_role_ids = [rid for rid in role_ids if role_camps.get(rid) == '狼人']

            current_good_prob = sum(probs.get(rid, 0) for rid in good_role_ids)
            current_wolf_prob = sum(probs.get(rid, 0) for rid in wolf_role_ids)

            new_wolf_prob = 0.9
            new_good_prob = 0.1

            if current_wolf_prob > 0:
                wolf_scale = new_wolf_prob / current_wolf_prob
                for rid in wolf_role_ids:
                    probs[rid] = round(probs.get(rid, 0) * wolf_scale, 6)
            else:
                count = len(wolf_role_ids)
                if count > 0:
                    for rid in wolf_role_ids:
                        probs[rid] = round(new_wolf_prob / count, 6)

            probs[role_id] = 0.0
            current_good_prob_no_role = sum(probs.get(rid, 0) for rid in good_role_ids if rid != role_id)
            if current_good_prob_no_role > 0:
                good_scale = new_good_prob / current_good_prob_no_role
                for rid in good_role_ids:
                    if rid != role_id:
                        probs[rid] = round(probs.get(rid, 0) * good_scale, 6)
            else:
                count = len([rid for rid in good_role_ids if rid != role_id])
                if count > 0:
                    for rid in good_role_ids:
                        if rid != role_id:
                            probs[rid] = round(new_good_prob / count, 6)

            top_role_id = max(probs, key=probs.get)
            predictions[player_id]['top_role_id'] = top_role_id
            predictions[player_id]['top_camp'] = role_camps.get(top_role_id, "未知")
            predictions[player_id]['top_probability'] = round(probs[top_role_id], 6)
            predictions[player_id]['probabilities'] = probs

            confirmed_name = confirmed_players[0]['player_name']
            uniqueness_log.append({
                'type': '身份唯一性推导',
                'confirmed_role_id': role_id,
                'confirmed_role_name': role_name,
                'confirmed_player_id': confirmed_players[0]['player_id'],
                'confirmed_player_name': confirmed_name,
                'target_id': player_id,
                'target_name': jumper['player_name'],
                'old_wolf_prob': round(current_wolf_prob * 100, 1),
                'new_wolf_prob': 90.0,
                'description': f"{confirmed_name}已确认为{role_name}，{jumper['player_name']}对跳{role_name}，根据身份唯一性，{jumper['player_name']}大概率是狼（狼人概率从{round(current_wolf_prob*100,1)}%调整为90%）"
            })

    return predictions, uniqueness_log


