"""
狼人杀身份预测程序 - 逻辑推理引擎
根据已确认的事实，自动推导出其他事实，并更新行为记录的状态
"""

from db import query_one, query_all, execute_write, ph


# ============================================================
# 逻辑推理引擎主入口
# ============================================================
def run_logic_inference(game_id, confirmed_identity_id=None):
    """
    运行逻辑推理引擎
    :param game_id: 对局ID
    :param confirmed_identity_id: 新确认的身份记录ID（可选，用于触发增量推导）
    :return: 推导结果摘要
    """
    results = {
        'confirmed_identities': [],  # 新确认的身份
        'updated_behaviors': [],     # 更新的行为记录
        'derived_facts': []          # 推导的事实
    }
    
    # 获取所有已确认的身份
    confirmed = query_all(
        f"SELECT * FROM game_confirmed_identities WHERE game_id = {ph()}",
        (game_id,)
    )
    
    # 规则1：自爆 = 100%狼人
    results = apply_self_explode_rule(game_id, confirmed, results)
    
    # 规则2：查验链推导（真预言家的金水=好人，查杀=狼人）
    results = apply_check_chain_rule(game_id, confirmed, results)
    
    # 规则3：对跳身份推导
    results = apply_counter_claim_rule(game_id, confirmed, results)
    
    # 规则4：保人/踩人自动修正
    results = apply_stance_correction_rule(game_id, confirmed, results)
    
    # 规则5：站边自动修正
    results = apply_side_correction_rule(game_id, confirmed, results)
    
    # 规则6：投票自动修正
    results = apply_vote_correction_rule(game_id, confirmed, results)
    
    # 规则7-12：行为序列推理
    results = apply_behavior_sequence_rules(game_id, confirmed, results)
    
    return results


# ============================================================
# 规则1：自爆 = 100%狼人
# ============================================================
def apply_self_explode_rule(game_id, confirmed, results):
    """
    如果玩家有自爆行为，则该玩家是100%狼人
    """
    # 获取所有自爆行为
    explode_actions = query_all(
        "SELECT id FROM actions WHERE action_type = 'identity_confirm' AND determine_content = 'actor_werewolf'"
    )
    if not explode_actions:
        # 尝试按名称查找（使用参数化查询避免中文编码问题）
        explode_actions = query_all(
            "SELECT id FROM actions WHERE name LIKE " + ph(),
            ('%自爆%',)
        )
    
    if not explode_actions:
        return results
    
    action_ids = [a['id'] for a in explode_actions]
    placeholders = ','.join([ph()] * len(action_ids))
    
    # 获取有自爆行为的玩家
    explode_records = query_all(
        f"SELECT DISTINCT actor_id FROM behavior_records WHERE game_id = {ph()} AND action_id IN ({placeholders})",
        (game_id, *action_ids)
    )
    
    for record in explode_records:
        player_id = record['actor_id']
        # 检查是否已经确认该玩家是狼人
        already_confirmed = any(
            c['player_id'] == player_id and c['role_id'] == 7  # 7=狼人
            for c in confirmed
        )
        if not already_confirmed:
            # 自动确认该玩家是狼人
            execute_write(
                f"""INSERT INTO game_confirmed_identities 
                   (game_id, player_id, role_id, camp, confidence, reason, source)
                   VALUES ({ph()}, {ph()}, 7, '狼人', 1.0, '自爆行为自动确认', 'system')""",
                (game_id, player_id)
            )
            results['confirmed_identities'].append({
                'player_id': player_id,
                'role_id': 7,
                'role_name': '狼人',
                'reason': '自爆行为自动确认'
            })
            results['derived_facts'].append(f'玩家{player_id}自爆 → 100%狼人')
    
    return results


# ============================================================
# 规则2：查验链推导
# ============================================================
def apply_check_chain_rule(game_id, confirmed, results):
    """
    如果A被确认为预言家，A给B金水 → B=100%好人
    如果A被确认为预言家，A给B查杀 → B=100%狼人
    """
    # 获取所有被确认为预言家的玩家
    prophets = [
        c for c in confirmed 
        if c.get('role_id') == 1  # 1=预言家
    ]
    
    for prophet in prophets:
        prophet_id = prophet['player_id']
        
        # 获取该预言家的所有查验行为（金水/查杀）
        check_actions = query_all(
            "SELECT id, determine_content FROM actions WHERE action_type = 'check_result'"
        )
        if not check_actions:
            # 使用参数化查询避免中文编码问题，分别查询金水和查杀
            gold_water_actions = query_all(
                "SELECT id FROM actions WHERE name LIKE " + ph(),
                ('%金水%',)
            )
            kill_check_actions = query_all(
                "SELECT id FROM actions WHERE name LIKE " + ph(),
                ('%查杀%',)
            )
            check_actions = []
            for a in gold_water_actions:
                check_actions.append({'id': a['id'], 'determine_content': 'target_good'})
            for a in kill_check_actions:
                check_actions.append({'id': a['id'], 'determine_content': 'target_werewolf'})
        
        for action in check_actions:
            action_id = action['id']
            determine_content = action['determine_content']
            
            # 获取该预言家的查验记录
            check_records = query_all(
                f"SELECT * FROM behavior_records WHERE game_id = {ph()} AND actor_id = {ph()} AND action_id = {ph()} AND target_id IS NOT NULL",
                (game_id, prophet_id, action_id)
            )
            
            for record in check_records:
                target_id = record['target_id']
                
                if determine_content == 'target_good':
                    # 金水 → 目标是好人
                    role_id = 6  # 6=平民（先确认是好人阵营，具体身份待定）
                    camp = '好人'
                    role_name = '好人(金水)'
                else:
                    # 查杀 → 目标是狼人
                    role_id = 7  # 7=狼人
                    camp = '狼人'
                    role_name = '狼人(查杀)'
                
                # 检查是否已经确认
                already_confirmed = any(
                    c['player_id'] == target_id 
                    for c in confirmed
                )
                if not already_confirmed:
                    execute_write(
                        f"""INSERT INTO game_confirmed_identities 
                           (game_id, player_id, role_id, camp, confidence, reason, source)
                           VALUES ({ph()}, {ph()}, {ph()}, {ph()}, 1.0, {ph()}, 'system')""",
                        (game_id, target_id, role_id, camp, f'预言家{prophet_id}的{role_name}')
                    )
                    results['confirmed_identities'].append({
                        'player_id': target_id,
                        'role_id': role_id,
                        'role_name': role_name,
                        'reason': f'预言家{prophet_id}的查验'
                    })
                    results['derived_facts'].append(f'预言家{prophet_id}给玩家{target_id}{role_name} → 100%{camp}')
    
    return results


# ============================================================
# 规则3：对跳身份推导
# ============================================================
def apply_counter_claim_rule(game_id, confirmed, results):
    """
    如果A对跳女巫B，且A被确认为真女巫 → B大概率是狼
    （暂时只记录事实，不自动确认，因为可能有好人乱跳）
    """
    # 这个规则比较复杂，暂时先不自动确认，只在推导事实中记录
    # 未来可以根据置信度来决定是否自动确认
    
    # 获取所有对跳行为
    counter_actions = query_all(
        "SELECT id, name FROM actions WHERE action_type = 'identity_conflict'"
    )
    if not counter_actions:
        # 使用参数化查询避免中文编码问题
        counter_actions = query_all(
            "SELECT id, name FROM actions WHERE name LIKE " + ph(),
            ('%对跳%',)
        )
    
    for action in counter_actions:
        action_id = action['id']
        action_name = action['name']
        
        # 获取对跳记录
        counter_records = query_all(
            f"SELECT * FROM behavior_records WHERE game_id = {ph()} AND action_id = {ph()} AND target_id IS NOT NULL",
            (game_id, action_id)
        )
        
        for record in counter_records:
            actor_id = record['actor_id']
            target_id = record['target_id']
            
            # 检查是否有一方被确认
            actor_confirmed = next((c for c in confirmed if c['player_id'] == actor_id), None)
            target_confirmed = next((c for c in confirmed if c['player_id'] == target_id), None)
            
            if actor_confirmed and actor_confirmed.get('camp') == '好人':
                # A被确认为好人 → B大概率是狼
                results['derived_facts'].append(f'玩家{actor_id}被确认为好人，且对跳{action_name}玩家{target_id} → 玩家{target_id}大概率是狼')
            elif target_confirmed and target_confirmed.get('camp') == '好人':
                # B被确认为好人 → A大概率是狼
                results['derived_facts'].append(f'玩家{target_id}被确认为好人，且被玩家{actor_id}对跳{action_name} → 玩家{actor_id}大概率是狼')
    
    return results


# ============================================================
# 规则4：保人/踩人自动修正
# ============================================================
def apply_stance_correction_rule(game_id, confirmed, results):
    """
    如果A保B，B被确认为狼人 → A的保人=保错人
    如果A保B，B被确认为好人 → A的保人=保对人
    如果A踩B，B被确认为狼人 → A的踩人=踩对人
    如果A踩B，B被确认为好人 → A的踩人=踩错人
    """
    # 获取所有保人/踩人行为
    stance_actions = query_all(
        "SELECT id, name, determine_content FROM actions WHERE action_type = 'stance_expression' AND has_result_status = TRUE"
    )
    if not stance_actions:
        # 使用参数化查询避免中文编码问题，在Python中过滤
        all_actions = query_all(
            "SELECT id, name FROM actions WHERE parent_id IS NOT NULL"
        )
        stance_actions = []
        for a in all_actions:
            name = a['name']
            if '保' in name:
                stance_actions.append({'id': a['id'], 'name': name, 'determine_content': 'defend'})
            elif '踩' in name:
                stance_actions.append({'id': a['id'], 'name': name, 'determine_content': 'attack'})
    
    for action in stance_actions:
        action_id = action['id']
        action_name = action['name']
        determine_content = action.get('determine_content', '')
        
        # 判断是保人还是踩人
        is_defend = '保' in action_name or determine_content == 'defend'
        is_attack = '踩' in action_name or determine_content == 'attack'
        
        if not is_defend and not is_attack:
            continue
        
        # 获取该行为的所有记录（有目标的）
        records = query_all(
            f"SELECT * FROM behavior_records WHERE game_id = {ph()} AND action_id = {ph()} AND target_id IS NOT NULL AND result_status = 'unknown'",
            (game_id, action_id)
        )
        
        for record in records:
            record_id = record['id']
            actor_id = record['actor_id']
            target_id = record['target_id']
            
            # 检查目标是否被确认身份
            target_confirmed = next((c for c in confirmed if c['player_id'] == target_id), None)
            
            if target_confirmed:
                target_camp = target_confirmed.get('camp', '')
                
                if is_defend:
                    # 保人
                    if target_camp == '好人':
                        new_status = 'correct'  # 保对人
                        fact = f'玩家{actor_id}保玩家{target_id}，玩家{target_id}是好人 → 保对人'
                    else:
                        new_status = 'incorrect'  # 保错人
                        fact = f'玩家{actor_id}保玩家{target_id}，玩家{target_id}是狼人 → 保错人'
                else:
                    # 踩人
                    if target_camp == '狼人':
                        new_status = 'correct'  # 踩对人
                        fact = f'玩家{actor_id}踩玩家{target_id}，玩家{target_id}是狼人 → 踩对人'
                    else:
                        new_status = 'incorrect'  # 踩错人
                        fact = f'玩家{actor_id}踩玩家{target_id}，玩家{target_id}是好人 → 踩错人'
                
                # 更新行为记录状态
                execute_write(
                    f"UPDATE behavior_records SET result_status = {ph()} WHERE id = {ph()}",
                    (new_status, record_id)
                )
                results['updated_behaviors'].append({
                    'record_id': record_id,
                    'action_name': action_name,
                    'old_status': 'unknown',
                    'new_status': new_status
                })
                results['derived_facts'].append(fact)
    
    return results


# ============================================================
# 规则5：站边自动修正
# ============================================================
def apply_side_correction_rule(game_id, confirmed, results):
    """
    如果A站边B（预言家），B被确认为真预言家 → A站对边
    如果A站边B（预言家），B被确认为狼人 → A站错边
    """
    # 获取所有站边行为（使用参数化查询避免中文编码问题）
    side_actions = query_all(
        "SELECT id, name FROM actions WHERE name LIKE " + ph() + " AND has_result_status = TRUE",
        ('%站边%',)
    )
    if not side_actions:
        # 使用参数化查询避免中文编码问题
        side_actions = query_all(
            "SELECT id, name FROM actions WHERE name LIKE " + ph(),
            ('%站边%',)
        )
    
    for action in side_actions:
        action_id = action['id']
        action_name = action['name']
        
        # 获取站边记录（有目标的，且目标是跳预言家的）
        records = query_all(
            f"""SELECT br.* FROM behavior_records br
               WHERE br.game_id = {ph()} AND br.action_id = {ph()} AND br.target_id IS NOT NULL AND br.result_status = 'unknown'""",
            (game_id, action_id)
        )
        
        for record in records:
            record_id = record['id']
            actor_id = record['actor_id']
            target_id = record['target_id']
            
            # 检查目标是否被确认身份（预言家或狼人）
            target_confirmed = next((c for c in confirmed if c['player_id'] == target_id), None)
            
            if target_confirmed:
                target_role_id = target_confirmed.get('role_id')
                
                if target_role_id == 1:  # 预言家
                    new_status = 'correct'  # 站对边
                    fact = f'玩家{actor_id}站边玩家{target_id}，玩家{target_id}是真预言家 → 站对边'
                elif target_confirmed.get('camp') == '狼人':
                    new_status = 'incorrect'  # 站错边
                    fact = f'玩家{actor_id}站边玩家{target_id}，玩家{target_id}是狼人 → 站错边'
                else:
                    continue
                
                # 更新行为记录状态
                execute_write(
                    f"UPDATE behavior_records SET result_status = {ph()} WHERE id = {ph()}",
                    (new_status, record_id)
                )
                results['updated_behaviors'].append({
                    'record_id': record_id,
                    'action_name': action_name,
                    'old_status': 'unknown',
                    'new_status': new_status
                })
                results['derived_facts'].append(fact)
    
    return results


# ============================================================
# 规则6：投票自动修正
# ============================================================
def apply_vote_correction_rule(game_id, confirmed, results):
    """
    如果A投给B（放逐票），B被确认为狼人 → 投对放逐票
    如果A投给B（放逐票），B被确认为好人 → 投错放逐票
    如果A投给B（警徽票），B被确认为真预言家 → 投对警徽票
    如果A投给B（警徽票），B被确认为狼人 → 投错警徽票
    """
    # 获取所有投票行为
    vote_actions = query_all(
        "SELECT id, name FROM actions WHERE action_type = 'vote_action' AND has_result_status = TRUE"
    )
    if not vote_actions:
        # 使用参数化查询避免中文编码问题
        vote_actions = query_all(
            "SELECT id, name FROM actions WHERE name LIKE " + ph() + " AND parent_id IS NOT NULL",
            ('%票%',)
        )
    
    for action in vote_actions:
        action_id = action['id']
        action_name = action['name']
        
        # 获取投票记录
        records = query_all(
            f"SELECT * FROM behavior_records WHERE game_id = {ph()} AND action_id = {ph()} AND target_id IS NOT NULL AND result_status = 'unknown'",
            (game_id, action_id)
        )
        
        for record in records:
            record_id = record['id']
            actor_id = record['actor_id']
            target_id = record['target_id']
            
            # 检查目标是否被确认身份
            target_confirmed = next((c for c in confirmed if c['player_id'] == target_id), None)
            
            if target_confirmed:
                target_camp = target_confirmed.get('camp', '')
                target_role_id = target_confirmed.get('role_id')
                
                # 判断是警徽票还是放逐票
                is_sheriff_vote = '警徽' in action_name
                is_exile_vote = '放逐' in action_name
                
                if is_sheriff_vote:
                    # 警徽票
                    if target_role_id == 1:  # 真预言家
                        new_status = 'correct'
                        fact = f'玩家{actor_id}投警徽票给玩家{target_id}，玩家{target_id}是真预言家 → 投对警徽票'
                    elif target_camp == '狼人':
                        new_status = 'incorrect'
                        fact = f'玩家{actor_id}投警徽票给玩家{target_id}，玩家{target_id}是狼人 → 投错警徽票'
                    else:
                        continue
                elif is_exile_vote:
                    # 放逐票
                    if target_camp == '狼人':
                        new_status = 'correct'
                        fact = f'玩家{actor_id}投放逐票给玩家{target_id}，玩家{target_id}是狼人 → 投对放逐票'
                    elif target_camp == '好人':
                        new_status = 'incorrect'
                        fact = f'玩家{actor_id}投放逐票给玩家{target_id}，玩家{target_id}是好人 → 投错放逐票'
                    else:
                        continue
                else:
                    continue
                
                # 更新行为记录状态
                execute_write(
                    f"UPDATE behavior_records SET result_status = {ph()} WHERE id = {ph()}",
                    (new_status, record_id)
                )
                results['updated_behaviors'].append({
                    'record_id': record_id,
                    'action_name': action_name,
                    'old_status': 'unknown',
                    'new_status': new_status
                })
                results['derived_facts'].append(fact)
    
    return results


# ============================================================
# 获取推导事实摘要（用于前端展示）
# ============================================================
def get_inference_summary(game_id):
    """
    获取对局的推导事实摘要
    """
    # 获取所有已确认的身份
    confirmed = query_all(
        f"""SELECT gi.*, p.name as player_name, r.name as role_name
           FROM game_confirmed_identities gi
           JOIN players p ON gi.player_id = p.id
           LEFT JOIN roles r ON gi.role_id = r.id
           WHERE gi.game_id = {ph()}
           ORDER BY gi.confirmed_at""",
        (game_id,)
    )
    
    # 获取所有已更新的行为记录（非unknown状态）
    updated_behaviors = query_all(
        f"""SELECT br.*, p1.name as actor_name, p2.name as target_name, a.name as action_name
           FROM behavior_records br
           JOIN players p1 ON br.actor_id = p1.id
           LEFT JOIN players p2 ON br.target_id = p2.id
           JOIN actions a ON br.action_id = a.id
           WHERE br.game_id = {ph()} AND br.result_status != 'unknown'
           ORDER BY br.created_at""",
        (game_id,)
    )
    
    return {
        'confirmed_identities': confirmed,
        'updated_behaviors': updated_behaviors
    }


# ============================================================
# 规则7-12：行为序列推理（按时间顺序分析行为模式）
# ============================================================
def apply_behavior_sequence_rules(game_id, confirmed, results):
    """
    行为序列推理：按时间顺序分析每个玩家的行为模式
    这些规则不是100%确认，而是调整概率权重
    """
    # 获取所有行为记录，按玩家分组，按时间排序
    all_behaviors = query_all(
        f"""SELECT br.*, a.name as action_name, a.action_type, a.determine_content
           FROM behavior_records br
           JOIN actions a ON br.action_id = a.id
           WHERE br.game_id = {ph()}
           ORDER BY br.actor_id, br.created_at, br.id""",
        (game_id,)
    )
    
    # 按玩家分组
    behaviors_by_player = {}
    for b in all_behaviors:
        actor = b['actor_id']
        if actor not in behaviors_by_player:
            behaviors_by_player[actor] = []
        behaviors_by_player[actor].append(b)
    
    for player_id, behaviors in behaviors_by_player.items():
        # 规则7：身份声明变更（跳身份A → 跳身份B，B≠A）
        results = detect_identity_change(player_id, behaviors, results)
        
        # 规则8：跳预言家 → 退水
        results = detect_prophet_retreat(player_id, behaviors, results)
        
        # 规则9：跳身份 → 脱衣服
        results = detect_undress(player_id, behaviors, results)
        
        # 规则10：保人 → 后来踩同一个人（立场摇摆）
        results = detect_stance_swing(player_id, behaviors, results)
        
        # 规则11：站边A → 后来站边B（晃边）
        results = detect_side_switch(player_id, behaviors, results)
        
        # 规则12：投票A → 后来投票B（变票）
        results = detect_vote_change(player_id, behaviors, results)
    
    return results


def detect_identity_change(player_id, behaviors, results):
    """
    规则7：身份声明变更
    如果玩家先跳身份A，后来又跳身份B（B≠A）→ 大概率不是A
    """
    identity_claims = []
    for b in behaviors:
        if b['action_type'] == 'identity_claim':
            # 从行为名称中提取身份
            action_name = b['action_name']
            identity = None
            if '预言家' in action_name:
                identity = '预言家'
            elif '女巫' in action_name:
                identity = '女巫'
            elif '猎人' in action_name:
                identity = '猎人'
            elif '守卫' in action_name:
                identity = '守卫'
            elif '平民' in action_name or '拍平民' in action_name:
                identity = '平民'
            elif '骑士' in action_name:
                identity = '骑士'
            elif '混子' in action_name:
                identity = '混子'
            
            if identity:
                identity_claims.append({
                    'identity': identity,
                    'time': b['created_at'],
                    'action_name': action_name
                })
    
    # 检测身份变更
    if len(identity_claims) >= 2:
        first_identity = identity_claims[0]['identity']
        for claim in identity_claims[1:]:
            if claim['identity'] != first_identity:
                results['derived_facts'].append(
                    f'玩家{player_id}先跳{first_identity}，后跳{claim["identity"]} → 大概率不是{first_identity}'
                )
                break
    
    return results


def detect_prophet_retreat(player_id, behaviors, results):
    """
    规则8：跳预言家 → 退水
    如果玩家跳预言家，然后退水 → 大概率不是预言家（除了滴滴代跳）
    """
    jumped_prophet = False
    retreated = False
    
    for b in behaviors:
        action_name = b['action_name']
        if '跳预言家' in action_name or (b['action_type'] == 'identity_claim' and '预言家' in action_name):
            jumped_prophet = True
        elif '退水' in action_name:
            if jumped_prophet:
                retreated = True
                break
    
    if jumped_prophet and retreated:
        results['derived_facts'].append(
            f'玩家{player_id}跳预言家后退水 → 大概率不是预言家（除滴滴代跳等特殊情况）'
        )
    
    return results


def detect_undress(player_id, behaviors, results):
    """
    规则9：跳身份 → 脱衣服
    如果玩家跳身份A，然后脱衣服 → 大概率不是A
    """
    identity_claimed = None
    undressed = False
    
    for b in behaviors:
        action_name = b['action_name']
        if b['action_type'] == 'identity_claim' and '脱' not in action_name:
            if '预言家' in action_name:
                identity_claimed = '预言家'
            elif '女巫' in action_name:
                identity_claimed = '女巫'
            elif '猎人' in action_name:
                identity_claimed = '猎人'
            elif '守卫' in action_name:
                identity_claimed = '守卫'
        elif '脱衣服' in action_name or '脱预言家' in action_name:
            if identity_claimed:
                undressed = True
                break
    
    if identity_claimed and undressed:
        results['derived_facts'].append(
            f'玩家{player_id}跳{identity_claimed}后脱衣服 → 大概率不是{identity_claimed}'
        )
    
    return results


def detect_stance_swing(player_id, behaviors, results):
    """
    规则10：保人 → 后来踩同一个人（立场摇摆）
    """
    # 记录对每个目标的立场变化
    stance_history = {}  # target_id -> [('保', time), ('踩', time), ...]
    
    for b in behaviors:
        action_name = b['action_name']
        target_id = b['target_id']
        if not target_id:
            continue
        
        if '保' in action_name and b['action_type'] == 'stance_expression':
            if target_id not in stance_history:
                stance_history[target_id] = []
            stance_history[target_id].append(('保', b['created_at']))
        elif '踩' in action_name and b['action_type'] == 'stance_expression':
            if target_id not in stance_history:
                stance_history[target_id] = []
            stance_history[target_id].append(('踩', b['created_at']))
    
    # 检测立场摇摆（先保后踩，或先踩后保）
    for target_id, history in stance_history.items():
        if len(history) >= 2:
            first_stance = history[0][0]
            for stance in history[1:]:
                if stance[0] != first_stance:
                    results['derived_facts'].append(
                        f'玩家{player_id}对玩家{target_id}先{first_stance}后{stance[0]} → 立场摇摆，嫌疑增加'
                    )
                    break
    
    return results


def detect_side_switch(player_id, behaviors, results):
    """
    规则11：站边A → 后来站边B（晃边）
    """
    side_history = []  # [target_id, ...]
    
    for b in behaviors:
        action_name = b['action_name']
        target_id = b['target_id']
        if not target_id:
            continue
        if '站边' in action_name and b['action_type'] == 'stance_expression':
            side_history.append(target_id)
    
    # 检测晃边
    if len(side_history) >= 2:
        first_side = side_history[0]
        for side in side_history[1:]:
            if side != first_side:
                results['derived_facts'].append(
                    f'玩家{player_id}先站边玩家{first_side}，后站边玩家{side} → 晃边'
                )
                break
    
    return results


def detect_vote_change(player_id, behaviors, results):
    """
    规则12：投票A → 后来投票B（变票）
    """
    vote_history = []  # [(target_id, round_number), ...]
    
    for b in behaviors:
        action_name = b['action_name']
        target_id = b['target_id']
        if not target_id:
            continue
        if '票' in action_name and b['action_type'] == 'vote_action':
            vote_history.append((target_id, b.get('round_number')))
    
    # 检测变票（同一轮次投票给不同的人）
    if len(vote_history) >= 2:
        rounds = {}
        for target_id, round_num in vote_history:
            if round_num not in rounds:
                rounds[round_num] = []
            rounds[round_num].append(target_id)
        
        for round_num, targets in rounds.items():
            if len(set(targets)) >= 2:
                results['derived_facts'].append(
                    f'玩家{player_id}在第{round_num}轮投票给不同玩家 → 变票'
                )
    
    return results
