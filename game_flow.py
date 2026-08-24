"""
游戏流程阶段管理模块

功能：
1. 定义阶段顺序
2. 推进流程阶段（下一环节）
3. 狼人自爆（直接进入下一个黑夜，处理警上自爆特殊情况）
4. 平票处理（追加PK发言）

特殊规则：
- 正常情况下（没有狼人自爆）只有第一天有警上发言
- 如果在第一天警上发言环节，警徽没有落地（没有投警徽票）之前，狼人自爆：
  - 直接进入黑夜
  - 第二天白天先进入"退水自爆"环节
  - 警上玩家可以选择退水或不退水，狼人可以选择继续自爆或不自爆
  - 如果狼人不再自爆，则继续第一天没完成的警上发言环节，之后正常进行
  - 如果再次自爆，直接进入夜间阶段，再次白天之后就没有警上发言了
"""

from db import query_one, execute_write, ph


# ============================================================
# 阶段定义
# ============================================================
# 每一轮的标准阶段顺序（第一天，没有夜间行动）
PHASE_FLOW_DAY1 = [
    '警上发言',      # 白天：竞选警长发言
    '警徽投票',      # 白天：投票选警长
    '死讯公布',      # 白天：法官宣布昨夜死讯
    '白天发言',      # 白天：警下发言
    '放逐投票',      # 白天：投票放逐
    '遗言',          # 白天：被放逐玩家留遗言
]

# 第二天及以后的标准阶段顺序（没有警上发言、警徽投票和夜间行动）
PHASE_FLOW_NORMAL = [
    '死讯公布',
    '白天发言',
    '放逐投票',
    '遗言',
]

# 阶段显示名称映射
PHASE_DISPLAY = {
    '夜间行动': '🌙 夜间行动',
    '警上发言': '🎤 警上发言',
    '警徽投票': '🗳️ 警徽投票',
    '死讯公布': '💀 死讯公布',
    '白天发言': '💬 白天发言',
    'PK发言': '⚔️ PK发言',
    '放逐投票': '🚪 放逐投票',
    '遗言': '📝 遗言',
    '退水自爆': '🔄 退水/自爆',
}

# 阶段属于白天还是黑夜
PHASE_TIME = {
    '夜间行动': '黑夜',
    '警上发言': '白天',
    '警徽投票': '白天',
    '死讯公布': '白天',
    '白天发言': '白天',
    'PK发言': '白天',
    '放逐投票': '白天',
    '遗言': '白天',
    '退水自爆': '白天',
}


# ============================================================
# 辅助函数
# ============================================================
def _get_game_state(game_id):
    """获取对局的流程状态"""
    game = query_one(
        "SELECT current_phase, current_round, sheriff_interrupted FROM games WHERE id = " + ph(),
        (game_id,)
    )
    if not game:
        return None
    return {
        'phase': game['current_phase'] or '警上发言',
        'round': game['current_round'] or 1,
        'sheriff_interrupted': game['sheriff_interrupted'] or 0,
    }


def _update_game_state(game_id, phase, round_number, sheriff_interrupted=None):
    """更新对局的流程状态"""
    if sheriff_interrupted is not None:
        execute_write(
            f"UPDATE games SET current_phase = {ph()}, current_round = {ph()}, sheriff_interrupted = {ph()} WHERE id = {ph()}",
            (phase, round_number, sheriff_interrupted, game_id)
        )
    else:
        execute_write(
            f"UPDATE games SET current_phase = {ph()}, current_round = {ph()} WHERE id = {ph()}",
            (phase, round_number, game_id)
        )


# ============================================================
# 流程推进
# ============================================================
def get_current_phase(game_id):
    """获取对局当前阶段和轮次"""
    state = _get_game_state(game_id)
    if not state:
        return None
    return {
        'phase': state['phase'],
        'round': state['round'],
        'display': PHASE_DISPLAY.get(state['phase'], state['phase']),
        'time': PHASE_TIME.get(state['phase'], '白天'),
        'sheriff_interrupted': state['sheriff_interrupted'],
    }


def advance_phase(game_id, pk_round=False):
    """推进到下一阶段

    参数：
        game_id: 对局ID
        pk_round: 是否是PK发言轮次（平票后追加）

    返回：
        新的阶段信息
    """
    state = _get_game_state(game_id)
    if not state:
        return None

    current_phase = state['phase']
    current_round = state['round']
    sheriff_interrupted = state['sheriff_interrupted']

    # 特殊处理1：退水自爆阶段 → 继续第一天没完成的警上发言
    if current_phase == '退水自爆':
        # 狼人不再自爆，继续第一天的警上发言
        next_phase = '警上发言'
        next_round = current_round
        next_sheriff = 0  # 清除中断状态
        _update_game_state(game_id, next_phase, next_round, next_sheriff)
        return get_current_phase(game_id)

    # 特殊处理2：PK发言后回到放逐投票
    if current_phase == 'PK发言':
        next_phase = '放逐投票'
        next_round = current_round
        _update_game_state(game_id, next_phase, next_round)
        return get_current_phase(game_id)

    # 特殊处理3：遗言后进入下一轮（下一轮从死讯公布开始，因为第一天已经过了）
    if current_phase == '遗言':
        next_phase = '死讯公布'
        next_round = current_round + 1
        _update_game_state(game_id, next_phase, next_round)
        return get_current_phase(game_id)

    # 特殊处理4：放逐投票后，如果是PK轮次，进入PK发言；否则进入遗言
    if current_phase == '放逐投票':
        if pk_round:
            next_phase = 'PK发言'
            next_round = current_round
        else:
            next_phase = '遗言'
            next_round = current_round
        _update_game_state(game_id, next_phase, next_round)
        return get_current_phase(game_id)

    # 标准流程推进
    # 选择当前轮次对应的阶段流程
    if current_round == 1 and not sheriff_interrupted:
        phase_flow = PHASE_FLOW_DAY1
    else:
        phase_flow = PHASE_FLOW_NORMAL

    try:
        idx = phase_flow.index(current_phase)
        if idx < len(phase_flow) - 1:
            next_phase = phase_flow[idx + 1]
            next_round = current_round
        else:
            # 最后一个阶段（遗言），进入下一轮
            next_phase = '夜间行动'
            next_round = current_round + 1
    except ValueError:
        # 当前阶段不在标准流程中，回到白天发言
        next_phase = '白天发言'
        next_round = current_round

    _update_game_state(game_id, next_phase, next_round)
    return get_current_phase(game_id)


def wolf_self_explode(game_id):
    """狼人自爆

    规则：
    - 正常情况：直接进入下一个黑夜
    - 特殊情况（第一天警上发言阶段，警徽未落地）：
      - 直接进入黑夜，设置sheriff_interrupted=1
      - 第二天白天先进入"退水自爆"环节

    返回：
        新的阶段信息
    """
    state = _get_game_state(game_id)
    if not state:
        return None

    current_phase = state['phase']
    current_round = state['round']
    sheriff_interrupted = state['sheriff_interrupted']

    # 特殊情况1：第一天警上发言阶段，警徽未落地（还没到警徽投票）
    if current_round == 1 and current_phase == '警上发言' and not sheriff_interrupted:
        # 直接进入第二天的"退水自爆"环节（夜间行动不需要记录）
        next_phase = '退水自爆'
        next_round = current_round + 1
        next_sheriff = 1  # 标记警上中断
        _update_game_state(game_id, next_phase, next_round, next_sheriff)
        return get_current_phase(game_id)

    # 特殊情况2：处于"退水自爆"阶段，狼人再次自爆
    if current_phase == '退水自爆':
        # 直接进入第二天的"死讯公布"（夜间行动不需要记录，之后不再有警上发言）
        next_phase = '死讯公布'
        next_round = current_round
        next_sheriff = 0  # 清除中断标志，之后正常流程
        _update_game_state(game_id, next_phase, next_round, next_sheriff)
        return get_current_phase(game_id)

    # 正常情况：直接进入下一天的"死讯公布"（夜间行动不需要记录）
    next_phase = '死讯公布'
    next_round = current_round + 1
    _update_game_state(game_id, next_phase, next_round)
    return get_current_phase(game_id)


def set_phase(game_id, phase, round_number=None):
    """手动设置当前阶段（用于调整）

    参数：
        game_id: 对局ID
        phase: 阶段名称
        round_number: 轮次（可选，不填则保持当前轮次）

    返回：
        新的阶段信息
    """
    if round_number is None:
        state = _get_game_state(game_id)
        round_number = state['round'] if state else 1

    execute_write(
        f"UPDATE games SET current_phase = {ph()}, current_round = {ph()} WHERE id = {ph()}",
        (phase, round_number, game_id)
    )

    return get_current_phase(game_id)


def init_game_phase(game_id):
    """初始化新对局的阶段（第一天从警上发言开始，夜间行动不需要记录）"""
    execute_write(
        f"UPDATE games SET current_phase = {ph()}, current_round = 1, sheriff_interrupted = 0 WHERE id = {ph()}",
        ('警上发言', game_id)
    )
