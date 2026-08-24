"""
API 路由模块 - 所有后端接口
分组：玩家、身份库、行为库、版型库、对局、行为记录、预测
"""
from flask import Blueprint, request, jsonify
from db import DB_TYPE, ph, query_all, query_one, execute_write
from prediction import predict_game, get_predictions, update_weights_from_game, score_predictions
from relationship import extract_relationships, get_relationship_graph, backtrack_inference, propagate_probabilities
from game_flow import get_current_phase, advance_phase, wolf_self_explode, set_phase, init_game_phase
from prophet_inference import get_prophet_claims

api = Blueprint('api', __name__, url_prefix='/api')


# ============================================================
# 响应辅助函数
# ============================================================
def ok(data=None, message="成功"):
    """成功响应"""
    resp = {"success": True, "message": message}
    if data is not None:
        resp["data"] = data
    return jsonify(resp)


def fail(message, status=400):
    """失败响应"""
    return jsonify({"success": False, "message": message}), status


# ============================================================
# 1. 玩家管理
# ============================================================
@api.route('/players', methods=['GET'])
def list_players():
    """获取所有玩家"""
    players = query_all("SELECT * FROM players ORDER BY id")
    return ok(players)


@api.route('/players', methods=['POST'])
def create_player():
    """新增玩家"""
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return fail("玩家名称不能为空")
    # 检查名字唯一性
    existing = query_one("SELECT id FROM players WHERE name = " + ph(), (name,))
    if existing:
        return fail(f"玩家名称 '{name}' 已存在，请使用其他名称")
    new_id = execute_write(
        f"INSERT INTO players (name) VALUES ({ph()})",
        (name,)
    )
    player = query_one("SELECT * FROM players WHERE id = " + ph(), (new_id,))
    return ok(player, "玩家创建成功")


@api.route('/players/<int:player_id>', methods=['PUT'])
def update_player(player_id):
    """修改玩家"""
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return fail("玩家名称不能为空")
    player = query_one("SELECT * FROM players WHERE id = " + ph(), (player_id,))
    if not player:
        return fail("玩家不存在", 404)
    # 检查名字唯一性（排除当前玩家）
    existing = query_one(
        "SELECT id FROM players WHERE name = " + ph() + " AND id != " + ph(),
        (name, player_id)
    )
    if existing:
        return fail(f"玩家名称 '{name}' 已存在，请使用其他名称")
    execute_write(
        f"UPDATE players SET name = {ph()} WHERE id = {ph()}",
        (name, player_id)
    )
    player = query_one("SELECT * FROM players WHERE id = " + ph(), (player_id,))
    return ok(player, "玩家更新成功")


@api.route('/players/<int:player_id>', methods=['DELETE'])
def delete_player(player_id):
    """删除玩家（先检查关联记录）"""
    player = query_one("SELECT * FROM players WHERE id = " + ph(), (player_id,))
    if not player:
        return fail("玩家不存在", 404)
    # 检查是否有关联的行为记录（作为发起者或目标）
    used_as_actor = query_one(
        "SELECT COUNT(*) as cnt FROM behavior_records WHERE actor_id = " + ph(),
        (player_id,)
    )
    used_as_target = query_one(
        "SELECT COUNT(*) as cnt FROM behavior_records WHERE target_id = " + ph(),
        (player_id,)
    )
    used_in_games = query_one(
        "SELECT COUNT(*) as cnt FROM game_players WHERE player_id = " + ph(),
        (player_id,)
    )
    used_in_predictions = query_one(
        "SELECT COUNT(*) as cnt FROM predictions WHERE player_id = " + ph(),
        (player_id,)
    )
    used_in_scores = query_one(
        "SELECT COUNT(*) as cnt FROM prediction_scores WHERE player_id = " + ph(),
        (player_id,)
    )

    total_used = (
        (used_as_actor["cnt"] if used_as_actor else 0) +
        (used_as_target["cnt"] if used_as_target else 0) +
        (used_in_games["cnt"] if used_in_games else 0) +
        (used_in_predictions["cnt"] if used_in_predictions else 0) +
        (used_in_scores["cnt"] if used_in_scores else 0)
    )

    if total_used > 0:
        detail = []
        if used_as_actor and used_as_actor["cnt"] > 0:
            detail.append(f"行为发起者 {used_as_actor['cnt']} 条")
        if used_as_target and used_as_target["cnt"] > 0:
            detail.append(f"行为目标 {used_as_target['cnt']} 条")
        if used_in_games and used_in_games["cnt"] > 0:
            detail.append(f"对局参与 {used_in_games['cnt']} 次")
        return fail(f"该玩家有关联记录无法删除：{', '.join(detail)}。请先删除相关对局记录。")

    execute_write(f"DELETE FROM players WHERE id = {ph()}", (player_id,))
    return ok(message="玩家删除成功")


# ============================================================
# 2. 身份库 CRUD
# ============================================================
@api.route('/roles', methods=['GET'])
def list_roles():
    """获取所有身份"""
    roles = query_all("SELECT * FROM roles ORDER BY camp, id")
    return ok(roles)


@api.route('/roles', methods=['POST'])
def create_role():
    """新增身份"""
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    camp = data.get('camp', '').strip()
    description = data.get('description', '')
    if not name or not camp:
        return fail("身份名称和阵营不能为空")
    new_id = execute_write(
        f"INSERT INTO roles (name, camp, description) VALUES ({ph()}, {ph()}, {ph()})",
        (name, camp, description)
    )
    role = query_one("SELECT * FROM roles WHERE id = " + ph(), (new_id,))
    return ok(role, "身份创建成功")


@api.route('/roles/<int:role_id>', methods=['PUT'])
def update_role(role_id):
    """修改身份"""
    data = request.get_json() or {}
    role = query_one("SELECT * FROM roles WHERE id = " + ph(), (role_id,))
    if not role:
        return fail("身份不存在", 404)
    name = data.get('name', role['name'])
    camp = data.get('camp', role['camp'])
    description = data.get('description', role['description'])
    is_active = data.get('is_active', role['is_active'])
    execute_write(
        f"UPDATE roles SET name={ph()}, camp={ph()}, description={ph()}, is_active={ph()} WHERE id={ph()}",
        (name, camp, description, is_active, role_id)
    )
    role = query_one("SELECT * FROM roles WHERE id = " + ph(), (role_id,))
    return ok(role, "身份更新成功")


@api.route('/roles/<int:role_id>', methods=['DELETE'])
def delete_role(role_id):
    """删除身份（先清理外键引用）"""
    role = query_one("SELECT * FROM roles WHERE id = " + ph(), (role_id,))
    if not role:
        return fail("身份不存在", 404)
    # 检查是否有对局玩家使用了该身份作为真实身份
    used_players = query_one(
        "SELECT COUNT(*) as cnt FROM game_players WHERE actual_role_id = " + ph(),
        (role_id,)
    )
    if used_players and used_players["cnt"] > 0:
        return fail(f"该身份已有 {used_players['cnt']} 名对局玩家使用，无法删除。")
    # 检查是否有行为记录声明了该身份
    used_behaviors = query_one(
        "SELECT COUNT(*) as cnt FROM behavior_records WHERE actor_role_id = " + ph(),
        (role_id,)
    )
    if used_behaviors and used_behaviors["cnt"] > 0:
        return fail(f"该身份已有 {used_behaviors['cnt']} 条行为记录声明，无法删除。")
    # 删除算法权重表中引用该身份的记录
    execute_write(f"DELETE FROM algorithm_weights WHERE role_id = {ph()}", (role_id,))
    # 删除身份本身
    execute_write(f"DELETE FROM roles WHERE id = {ph()}", (role_id,))
    return ok(message="身份删除成功")


# ============================================================
# 3. 行为库 CRUD
# ============================================================
@api.route('/actions', methods=['GET'])
def list_actions():
    """获取所有行为"""
    actions = query_all("SELECT * FROM actions ORDER BY id")
    return ok(actions)


@api.route('/actions', methods=['POST'])
def create_action():
    """新增行为（支持指定父行为，实现分级）"""
    import sys
    print("[DEBUG] create_action 被调用", flush=True)
    data = request.get_json() or {}
    print(f"[DEBUG] 请求数据: {data}", flush=True)
    name = data.get('name', '').strip()
    description = data.get('description', '')
    default_weight = data.get('default_weight', 1.0)
    parent_id = data.get('parent_id')
    if not name:
        return fail("行为名称不能为空")
    if parent_id:
        parent_id = int(parent_id)
    print(f"[DEBUG] 准备插入: name={name}, parent_id={parent_id}", flush=True)
    try:
        new_id = execute_write(
            f"INSERT INTO actions (name, description, default_weight, parent_id) VALUES ({ph()}, {ph()}, {ph()}, {ph()})",
            (name, description, default_weight, parent_id)
        )
        print(f"[DEBUG] 插入成功, new_id={new_id}", flush=True)
        action = query_one("SELECT * FROM actions WHERE id = " + ph(), (new_id,))
        return ok(action, "行为创建成功")
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print(f"[创建行为错误] {error_detail}", flush=True)
        return fail(f"创建行为失败: {str(e)}")


@api.route('/actions/<int:action_id>', methods=['PUT'])
def update_action(action_id):
    """修改行为（支持修改父行为）"""
    data = request.get_json() or {}
    action = query_one("SELECT * FROM actions WHERE id = " + ph(), (action_id,))
    if not action:
        return fail("行为不存在", 404)
    name = data.get('name', action['name'])
    description = data.get('description', action['description'])
    default_weight = data.get('default_weight', action['default_weight'])
    is_active = data.get('is_active', action['is_active'])
    parent_id = data.get('parent_id', action.get('parent_id'))
    if parent_id:
        parent_id = int(parent_id)
    execute_write(
        f"UPDATE actions SET name={ph()}, description={ph()}, default_weight={ph()}, is_active={ph()}, parent_id={ph()} WHERE id={ph()}",
        (name, description, default_weight, is_active, parent_id, action_id)
    )
    action = query_one("SELECT * FROM actions WHERE id = " + ph(), (action_id,))
    return ok(action, "行为更新成功")


@api.route('/actions/<int:action_id>', methods=['DELETE'])
def delete_action(action_id):
    """删除行为（先清理外键引用）"""
    action = query_one("SELECT * FROM actions WHERE id = " + ph(), (action_id,))
    if not action:
        return fail("行为不存在", 404)
    # 检查是否有行为记录使用了该行为
    used = query_one(
        "SELECT COUNT(*) as cnt FROM behavior_records WHERE action_id = " + ph(),
        (action_id,)
    )
    if used and used["cnt"] > 0:
        return fail(f"该行为已有 {used['cnt']} 条行为记录使用，无法删除。请先删除相关行为记录。")
    # 删除算法权重表中引用该行为的记录
    execute_write(f"DELETE FROM algorithm_weights WHERE action_id = {ph()}", (action_id,))
    # 删除行为本身
    execute_write(f"DELETE FROM actions WHERE id = {ph()}", (action_id,))
    return ok(message="行为删除成功")


# ============================================================
# 4. 版型库 CRUD
# ============================================================
@api.route('/setups', methods=['GET'])
def list_setups():
    """获取所有版型"""
    setups = query_all("SELECT * FROM setups ORDER BY id")
    return ok(setups)


@api.route('/setups', methods=['POST'])
def create_setup():
    """新增版型"""
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    role_config = data.get('role_config', '{}')
    description = data.get('description', '')
    if not name:
        return fail("版型名称不能为空")
    new_id = execute_write(
        f"INSERT INTO setups (name, role_config, description) VALUES ({ph()}, {ph()}, {ph()})",
        (name, role_config, description)
    )
    setup = query_one("SELECT * FROM setups WHERE id = " + ph(), (new_id,))
    return ok(setup, "版型创建成功")


@api.route('/setups/<int:setup_id>', methods=['PUT'])
def update_setup(setup_id):
    """修改版型"""
    data = request.get_json() or {}
    setup = query_one("SELECT * FROM setups WHERE id = " + ph(), (setup_id,))
    if not setup:
        return fail("版型不存在", 404)
    name = data.get('name', setup['name'])
    role_config = data.get('role_config', setup['role_config'])
    description = data.get('description', setup['description'])
    is_active = data.get('is_active', setup['is_active'])
    execute_write(
        f"UPDATE setups SET name={ph()}, role_config={ph()}, description={ph()}, is_active={ph()} WHERE id={ph()}",
        (name, role_config, description, is_active, setup_id)
    )
    setup = query_one("SELECT * FROM setups WHERE id = " + ph(), (setup_id,))
    return ok(setup, "版型更新成功")


@api.route('/setups/<int:setup_id>', methods=['DELETE'])
def delete_setup(setup_id):
    """删除版型（先检查外键引用）"""
    setup = query_one("SELECT * FROM setups WHERE id = " + ph(), (setup_id,))
    if not setup:
        return fail("版型不存在", 404)
    # 检查是否有对局使用了该版型
    used = query_one(
        "SELECT COUNT(*) as cnt FROM games WHERE setup_id = " + ph(),
        (setup_id,)
    )
    if used and used["cnt"] > 0:
        return fail(f"该版型已有 {used['cnt']} 局对局使用，无法删除。请先删除相关对局。")
    # 删除版型本身
    execute_write(f"DELETE FROM setups WHERE id = {ph()}", (setup_id,))
    return ok(message="版型删除成功")


# ============================================================
# 5. 对局管理
# ============================================================
@api.route('/games', methods=['GET'])
def list_games():
    """获取所有对局"""
    games = query_all("""
        SELECT g.*, s.name as setup_name
        FROM games g
        LEFT JOIN setups s ON g.setup_id = s.id
        ORDER BY g.id DESC
    """)
    return ok(games)


@api.route('/games', methods=['POST'])
def create_game():
    """创建对局"""
    data = request.get_json() or {}
    game_code = data.get('game_code', '').strip()
    setup_id = data.get('setup_id')
    player_count = data.get('player_count')
    notes = data.get('notes', '')
    if not game_code:
        return fail("对局编号不能为空")
    new_id = execute_write(
        f"INSERT INTO games (game_code, setup_id, player_count, notes) VALUES ({ph()}, {ph()}, {ph()}, {ph()})",
        (game_code, setup_id, player_count, notes)
    )
    game = query_one("SELECT * FROM games WHERE id = " + ph(), (new_id,))
    return ok(game, "对局创建成功")


@api.route('/games/<int:game_id>', methods=['GET'])
def get_game(game_id):
    """获取对局详情（含玩家列表和行为记录）"""
    game = query_one("""
        SELECT g.*, s.name as setup_name, s.role_config
        FROM games g
        LEFT JOIN setups s ON g.setup_id = s.id
        WHERE g.id = """ + ph(), (game_id,))
    if not game:
        return fail("对局不存在", 404)
    # 对局玩家
    players = query_all("""
        SELECT gp.*, p.name as player_name, r.name as actual_role_name, r.camp as actual_camp
        FROM game_players gp
        JOIN players p ON gp.player_id = p.id
        LEFT JOIN roles r ON gp.actual_role_id = r.id
        WHERE gp.game_id = """ + ph() + " ORDER BY gp.seat_number", (game_id,))
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
        WHERE b.game_id = """ + ph() + " ORDER BY b.id", (game_id,))
    game['players'] = players
    game['behaviors'] = behaviors
    return ok(game)


@api.route('/games/<int:game_id>', methods=['PUT'])
def update_game(game_id):
    """修改对局信息"""
    data = request.get_json() or {}
    game = query_one("SELECT * FROM games WHERE id = " + ph(), (game_id,))
    if not game:
        return fail("对局不存在", 404)
    game_code = data.get('game_code', game['game_code'])
    setup_id = data.get('setup_id', game['setup_id'])
    player_count = data.get('player_count', game['player_count'])
    notes = data.get('notes', game['notes'])
    status = data.get('status', game['status'])
    execute_write(
        f"UPDATE games SET game_code={ph()}, setup_id={ph()}, player_count={ph()}, notes={ph()}, status={ph()} WHERE id={ph()}",
        (game_code, setup_id, player_count, notes, status, game_id)
    )
    game = query_one("SELECT * FROM games WHERE id = " + ph(), (game_id,))
    return ok(game, "对局更新成功")


@api.route('/games/<int:game_id>', methods=['DELETE'])
def delete_game(game_id):
    """删除对局（级联删除玩家和行为记录）"""
    game = query_one("SELECT * FROM games WHERE id = " + ph(), (game_id,))
    if not game:
        return fail("对局不存在", 404)
    execute_write(f"DELETE FROM games WHERE id = {ph()}", (game_id,))
    return ok(message="对局删除成功")


# ---- 对局玩家管理 ----
@api.route('/games/<int:game_id>/players', methods=['POST'])
def add_game_player(game_id):
    """向对局添加玩家"""
    data = request.get_json() or {}
    player_id = data.get('player_id')
    seat_number = data.get('seat_number')
    if not player_id:
        return fail("玩家ID不能为空")
    # 检查是否已添加
    existing = query_one(
        f"SELECT * FROM game_players WHERE game_id={ph()} AND player_id={ph()}",
        (game_id, player_id)
    )
    if existing:
        return fail("该玩家已在此对局中")
    execute_write(
        f"INSERT INTO game_players (game_id, player_id, seat_number) VALUES ({ph()}, {ph()}, {ph()})",
        (game_id, player_id, seat_number)
    )
    return ok(message="玩家添加成功")


@api.route('/games/<int:game_id>/players/<int:player_id>', methods=['DELETE'])
def remove_game_player(game_id, player_id):
    """从对局移除玩家（级联删除该玩家的行为记录）"""
    # 删除该玩家作为发起者或目标的行为记录
    execute_write(
        f"DELETE FROM behavior_records WHERE game_id={ph()} AND (actor_id={ph()} OR target_id={ph()})",
        (game_id, player_id, player_id)
    )
    # 从对局玩家列表中移除
    execute_write(
        f"DELETE FROM game_players WHERE game_id={ph()} AND player_id={ph()}",
        (game_id, player_id)
    )
    return ok(message="玩家移除成功")


@api.route('/games/<int:game_id>/players/<int:player_id>/seat', methods=['PUT'])
def update_player_seat(game_id, player_id):
    """更新玩家座位号"""
    data = request.get_json() or {}
    seat_number = data.get('seat_number')
    if seat_number is None or seat_number == '':
        return fail("座位号不能为空")
    # 检查玩家是否在对局中
    existing = query_one(
        f"SELECT * FROM game_players WHERE game_id={ph()} AND player_id={ph()}",
        (game_id, player_id)
    )
    if not existing:
        return fail("该玩家不在此对局中")
    execute_write(
        f"UPDATE game_players SET seat_number={ph()} WHERE game_id={ph()} AND player_id={ph()}",
        (seat_number, game_id, player_id)
    )
    return ok(message="座位号更新成功")


@api.route('/games/<int:game_id>/players/<int:player_id>/role', methods=['PUT'])
def set_player_actual_role(game_id, player_id):
    """设置玩家真实身份（对局结束确认时用）"""
    data = request.get_json() or {}
    actual_role_id = data.get('actual_role_id')
    if not actual_role_id:
        return fail("身份ID不能为空")
    execute_write(
        f"UPDATE game_players SET actual_role_id={ph()} WHERE game_id={ph()} AND player_id={ph()}",
        (actual_role_id, game_id, player_id)
    )
    return ok(message="真实身份设置成功")


# ---- 对局状态流转 ----
@api.route('/games/<int:game_id>/finish', methods=['POST'])
def finish_game(game_id):
    """结束对局"""
    game = query_one("SELECT * FROM games WHERE id = " + ph(), (game_id,))
    if not game:
        return fail("对局不存在", 404)
    execute_write(
        f"UPDATE games SET status='已结束', finished_at=CURRENT_TIMESTAMP WHERE id={ph()}",
        (game_id,)
    )
    return ok(message="对局已结束")


@api.route('/games/<int:game_id>/confirm', methods=['POST'])
def confirm_game(game_id):
    """确认对局结果（补全所有玩家真实身份后调用）
    1. 检查所有玩家是否都设置了真实身份
    2. 生成最终预测结果
    3. 对比预测与真实身份进行打分
    4. 根据真实身份更新算法权重（自我优化）
    5. 确认所有行为记录，更新对局状态
    """
    game = query_one("SELECT * FROM games WHERE id = " + ph(), (game_id,))
    if not game:
        return fail("对局不存在", 404)
    # 检查所有玩家是否都设置了真实身份
    players = query_all(
        "SELECT * FROM game_players WHERE game_id = " + ph(), (game_id,)
    )
    no_role = [p for p in players if not p.get('actual_role_id')]
    if no_role:
        return fail(f"还有 {len(no_role)} 名玩家未设置真实身份，请先补全")
    # 生成最终预测
    predict_game(game_id)
    # 预测打分
    score_result = score_predictions(game_id)
    # 算法自我优化：更新权重
    updated_count = update_weights_from_game(game_id)
    # 确认所有行为记录
    execute_write(
        f"UPDATE behavior_records SET is_verified=TRUE WHERE game_id={ph()}",
        (game_id,)
    )
    # 更新对局状态
    execute_write(
        f"UPDATE games SET status='已确认', confirmed_at=CURRENT_TIMESTAMP WHERE id={ph()}",
        (game_id,)
    )
    return ok({
        "score": score_result,
        "weights_updated": updated_count
    }, "对局结果已确认，预测已打分，算法权重已更新")


# ============================================================
# 6. 行为记录
# ============================================================
@api.route('/games/<int:game_id>/behaviors', methods=['GET'])
def list_behaviors(game_id):
    """获取某局所有行为记录"""
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
        WHERE b.game_id = """ + ph() + " ORDER BY b.id", (game_id,))
    return ok(behaviors)


@api.route('/games/<int:game_id>/behaviors', methods=['POST'])
def create_behavior(game_id):
    """新增行为记录（核心功能）
    必填：actor_id, action_id
    可空：target_id, actor_role_id, actor_camp, round_number, phase, notes
    """
    data = request.get_json() or {}
    actor_id = data.get('actor_id')
    action_id = data.get('action_id')
    target_id = data.get('target_id')
    actor_role_id = data.get('actor_role_id')
    actor_camp = data.get('actor_camp')
    round_number = data.get('round_number')
    phase = data.get('phase')
    notes = data.get('notes', '')

    if not actor_id:
        return fail("行为发起者ID不能为空")
    if not action_id:
        return fail("具体行为ID不能为空")

    # 检查对局是否存在
    game = query_one("SELECT * FROM games WHERE id = " + ph(), (game_id,))
    if not game:
        return fail("对局不存在", 404)

    new_id = execute_write(
        f"""INSERT INTO behavior_records
            (game_id, actor_id, target_id, action_id, actor_role_id, actor_camp, round_number, phase, notes)
            VALUES ({ph()}, {ph()}, {ph()}, {ph()}, {ph()}, {ph()}, {ph()}, {ph()}, {ph()})""",
        (game_id, actor_id, target_id, action_id, actor_role_id, actor_camp, round_number, phase, notes)
    )
    behavior = query_one("SELECT * FROM behavior_records WHERE id = " + ph(), (new_id,))
    return ok(behavior, "行为记录创建成功")


@api.route('/games/<int:game_id>/behaviors/batch', methods=['POST'])
def create_behaviors_batch(game_id):
    """批量新增行为记录（同一发起者/目标/声明，多个不同行为）
    必填：actor_id, action_ids（数组）
    可空：target_id, actor_role_id, actor_camp, round_number, phase, notes
    """
    data = request.get_json() or {}
    actor_id = data.get('actor_id')
    action_ids = data.get('action_ids', [])
    target_id = data.get('target_id')
    actor_role_id = data.get('actor_role_id')
    actor_camp = data.get('actor_camp')
    round_number = data.get('round_number')
    phase = data.get('phase')
    notes = data.get('notes', '')

    if not actor_id:
        return fail("行为发起者ID不能为空")
    if not action_ids or len(action_ids) == 0:
        return fail("请至少选择一个行为")

    # 检查对局是否存在
    game = query_one("SELECT * FROM games WHERE id = " + ph(), (game_id,))
    if not game:
        return fail("对局不存在", 404)

    created_ids = []
    for action_id in action_ids:
        new_id = execute_write(
            f"""INSERT INTO behavior_records
                (game_id, actor_id, target_id, action_id, actor_role_id, actor_camp, round_number, phase, notes)
                VALUES ({ph()}, {ph()}, {ph()}, {ph()}, {ph()}, {ph()}, {ph()}, {ph()}, {ph()})""",
            (game_id, actor_id, target_id, action_id, actor_role_id, actor_camp, round_number, phase, notes)
        )
        created_ids.append(new_id)

    return ok({"created_count": len(created_ids), "created_ids": created_ids}, f"成功创建 {len(created_ids)} 条行为记录")


@api.route('/behaviors/<int:behavior_id>', methods=['PUT'])
def update_behavior(behavior_id):
    """修改行为记录"""
    data = request.get_json() or {}
    behavior = query_one("SELECT * FROM behavior_records WHERE id = " + ph(), (behavior_id,))
    if not behavior:
        return fail("行为记录不存在", 404)

    actor_id = data.get('actor_id', behavior['actor_id'])
    target_id = data.get('target_id', behavior['target_id'])
    action_id = data.get('action_id', behavior['action_id'])
    actor_role_id = data.get('actor_role_id', behavior['actor_role_id'])
    actor_camp = data.get('actor_camp', behavior['actor_camp'])
    round_number = data.get('round_number', behavior['round_number'])
    phase = data.get('phase', behavior['phase'])
    notes = data.get('notes', behavior['notes'])

    execute_write(
        f"""UPDATE behavior_records
            SET actor_id={ph()}, target_id={ph()}, action_id={ph()},
                actor_role_id={ph()}, actor_camp={ph()}, round_number={ph()},
                phase={ph()}, notes={ph()}
            WHERE id={ph()}""",
        (actor_id, target_id, action_id, actor_role_id, actor_camp, round_number, phase, notes, behavior_id)
    )
    behavior = query_one("SELECT * FROM behavior_records WHERE id = " + ph(), (behavior_id,))
    return ok(behavior, "行为记录更新成功")


@api.route('/behaviors/<int:behavior_id>', methods=['DELETE'])
def delete_behavior(behavior_id):
    """删除行为记录"""
    behavior = query_one("SELECT * FROM behavior_records WHERE id = " + ph(), (behavior_id,))
    if not behavior:
        return fail("行为记录不存在", 404)
    execute_write(f"DELETE FROM behavior_records WHERE id = {ph()}", (behavior_id,))
    return ok(message="行为记录删除成功")


# ============================================================
# 6.5 多情景假设推理
# ============================================================
@api.route('/games/<int:game_id>/scenarios', methods=['GET'])
def list_scenarios(game_id):
    """获取对局的所有假设情景"""
    scenarios = query_all(
        f"SELECT * FROM game_scenarios WHERE game_id = {ph()} ORDER BY sort_order, id",
        (game_id,)
    )
    # 为每个情景加载假设身份
    for s in scenarios:
        assignments = query_all(
            f"""SELECT sa.*, p.name as player_name, r.name as role_name, r.camp as role_camp
                FROM scenario_assignments sa
                JOIN players p ON sa.player_id = p.id
                LEFT JOIN roles r ON sa.role_id = r.id
                WHERE sa.scenario_id = {ph()}""",
            (s['id'],)
        )
        s['assignments'] = assignments
    return ok(scenarios)


@api.route('/games/<int:game_id>/scenarios', methods=['POST'])
def create_scenario(game_id):
    """创建假设情景"""
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return fail("情景名称不能为空")
    description = data.get('description', '')
    sort_order = data.get('sort_order', 0)
    new_id = execute_write(
        f"INSERT INTO game_scenarios (game_id, name, description, sort_order) VALUES ({ph()}, {ph()}, {ph()}, {ph()})",
        (game_id, name, description, sort_order)
    )
    scenario = query_one("SELECT * FROM game_scenarios WHERE id = " + ph(), (new_id,))
    scenario['assignments'] = []
    return ok(scenario, "情景创建成功")


@api.route('/scenarios/<int:scenario_id>', methods=['PUT'])
def update_scenario(scenario_id):
    """更新假设情景"""
    scenario = query_one("SELECT * FROM game_scenarios WHERE id = " + ph(), (scenario_id,))
    if not scenario:
        return fail("情景不存在", 404)
    data = request.get_json() or {}
    name = data.get('name', scenario['name'])
    description = data.get('description', scenario['description'])
    is_active = data.get('is_active', scenario['is_active'])
    sort_order = data.get('sort_order', scenario['sort_order'])
    execute_write(
        f"UPDATE game_scenarios SET name={ph()}, description={ph()}, is_active={ph()}, sort_order={ph()} WHERE id={ph()}",
        (name, description, is_active, sort_order, scenario_id)
    )
    scenario = query_one("SELECT * FROM game_scenarios WHERE id = " + ph(), (scenario_id,))
    return ok(scenario, "情景更新成功")


@api.route('/scenarios/<int:scenario_id>', methods=['DELETE'])
def delete_scenario(scenario_id):
    """删除假设情景"""
    scenario = query_one("SELECT * FROM game_scenarios WHERE id = " + ph(), (scenario_id,))
    if not scenario:
        return fail("情景不存在", 404)
    execute_write(f"DELETE FROM game_scenarios WHERE id = {ph()}", (scenario_id,))
    return ok(message="情景删除成功")


@api.route('/scenarios/<int:scenario_id>/assignments', methods=['POST'])
def set_scenario_assignment(scenario_id):
    """设置情景中某个玩家的假设身份或阵营（存在则更新，不存在则创建）
    支持两种模式：
    1. 具体身份：role_id（如预言家、女巫）
    2. 阵营假设：camp（好人/狼人），role_id为空
    """
    scenario = query_one("SELECT * FROM game_scenarios WHERE id = " + ph(), (scenario_id,))
    if not scenario:
        return fail("情景不存在", 404)
    data = request.get_json() or {}
    player_id = data.get('player_id')
    role_id = data.get('role_id')
    camp = data.get('camp')
    confidence = data.get('confidence', 0.9)
    if not player_id:
        return fail("玩家ID不能为空")
    if not role_id and not camp:
        return fail("请选择假设身份或假设阵营")
    # 检查是否已存在
    existing = query_one(
        f"SELECT * FROM scenario_assignments WHERE scenario_id={ph()} AND player_id={ph()}",
        (scenario_id, player_id)
    )
    if existing:
        execute_write(
            f"UPDATE scenario_assignments SET role_id={ph()}, camp={ph()}, confidence={ph()} WHERE id={ph()}",
            (role_id, camp, confidence, existing['id'])
        )
        assignment_id = existing['id']
    else:
        assignment_id = execute_write(
            f"INSERT INTO scenario_assignments (scenario_id, player_id, role_id, camp, confidence) VALUES ({ph()}, {ph()}, {ph()}, {ph()}, {ph()})",
            (scenario_id, player_id, role_id, camp, confidence)
        )
    assignment = query_one(
        f"""SELECT sa.*, p.name as player_name, r.name as role_name, r.camp as role_camp
            FROM scenario_assignments sa
            JOIN players p ON sa.player_id = p.id
            LEFT JOIN roles r ON sa.role_id = r.id
            WHERE sa.id = {ph()}""",
        (assignment_id,)
    )
    return ok(assignment, "假设身份设置成功")


@api.route('/scenario_assignments/<int:assignment_id>', methods=['DELETE'])
def delete_scenario_assignment(assignment_id):
    """删除情景中的假设身份"""
    assignment = query_one("SELECT * FROM scenario_assignments WHERE id = " + ph(), (assignment_id,))
    if not assignment:
        return fail("假设身份不存在", 404)
    execute_write(f"DELETE FROM scenario_assignments WHERE id = {ph()}", (assignment_id,))
    return ok(message="假设身份删除成功")


@api.route('/games/<int:game_id>/invariant_players', methods=['GET'])
def get_invariant_players(game_id):
    """获取铁狼/铁好人列表（在所有情景下概率都>阈值的玩家）

    铁狼：在所有情景下，狼人阵营概率都>90%的玩家
    铁好人：在所有情景下，好人阵营概率都>90%的玩家

    支持查询参数:
        threshold: 概率阈值，默认0.9（90%）
    """
    game = query_one("SELECT * FROM games WHERE id = " + ph(), (game_id,))
    if not game:
        return fail("对局不存在", 404)

    threshold = request.args.get('threshold', default=0.9, type=float)

    # 获取所有情景
    scenarios = query_all(
        f"SELECT * FROM game_scenarios WHERE game_id = {ph()} AND is_active = 1 ORDER BY sort_order, id",
        (game_id,)
    )

    if not scenarios:
        return ok({
            "iron_wolves": [],
            "iron_goods": [],
            "message": "暂无情景，无法识别铁狼/铁好人"
        })

    # 获取身份的阵营映射
    roles = query_all("SELECT id, name, camp FROM roles")
    role_camp = {r['id']: r['camp'] for r in roles}

    # 对每个情景计算预测，收集每个玩家在各情景下的阵营概率
    player_scenario_probs = {}  # {player_id: {scenario_id: {"狼人": prob, "好人": prob, "第三方": prob}}}

    for scenario in scenarios:
        results = predict_game(game_id, scenario_id=scenario['id'])
        for player_id, data in results.items():
            # 跳过非玩家ID的键（如'_prophet_inference_result'）
            if isinstance(player_id, str) and player_id.startswith('_'):
                continue
            if player_id not in player_scenario_probs:
                player_scenario_probs[player_id] = {}
            # 计算该玩家在该情景下的各阵营概率
            camp_probs = {"狼人": 0.0, "好人": 0.0, "第三方": 0.0}
            for role_id, prob in data['probabilities'].items():
                camp = role_camp.get(role_id, "")
                if camp in camp_probs:
                    camp_probs[camp] += prob
            player_scenario_probs[player_id][scenario['id']] = camp_probs

    # 识别铁狼：在所有情景下狼人概率都>threshold
    iron_wolves = []
    # 识别铁好人：在所有情景下好人概率都>threshold
    iron_goods = []

    for player_id, scenario_probs in player_scenario_probs.items():
        if len(scenario_probs) < len(scenarios):
            continue  # 缺少某些情景的预测，跳过

        # 获取玩家名称
        player_name = ""
        gp = query_one(
            f"SELECT p.name FROM game_players gp JOIN players p ON gp.player_id = p.id WHERE gp.game_id={ph()} AND gp.player_id={ph()}",
            (game_id, player_id)
        )
        if gp:
            player_name = gp['name']

        # 检查是否所有情景下狼人概率都>threshold
        all_wolf = all(probs["狼人"] >= threshold for probs in scenario_probs.values())
        if all_wolf:
            min_wolf_prob = min(probs["狼人"] for probs in scenario_probs.values())
            iron_wolves.append({
                "player_id": player_id,
                "player_name": player_name,
                "min_wolf_probability": round(min_wolf_prob, 4),
                "scenario_count": len(scenarios)
            })

        # 检查是否所有情景下好人概率都>threshold
        all_good = all(probs["好人"] >= threshold for probs in scenario_probs.values())
        if all_good:
            min_good_prob = min(probs["好人"] for probs in scenario_probs.values())
            iron_goods.append({
                "player_id": player_id,
                "player_name": player_name,
                "min_good_probability": round(min_good_prob, 4),
                "scenario_count": len(scenarios)
            })

    return ok({
        "iron_wolves": iron_wolves,
        "iron_goods": iron_goods,
        "threshold": threshold,
        "scenario_count": len(scenarios)
    })


# ============================================================
# 7. 身份预测（贝叶斯算法）
# ============================================================
@api.route('/games/<int:game_id>/predictions', methods=['GET'])
def get_game_predictions(game_id):
    """获取某局所有玩家的身份概率预测（实时计算）

    支持查询参数:
        scenario_id: 假设情景ID（可选）。如果提供，会应用情景中的假设身份
    """
    game = query_one("SELECT * FROM games WHERE id = " + ph(), (game_id,))
    if not game:
        return fail("对局不存在", 404)
    # 获取情景ID（可选）
    scenario_id = request.args.get('scenario_id', type=int)
    # 实时计算预测
    results = predict_game(game_id, scenario_id=scenario_id)
    # 格式化输出
    output = []
    for player_id, data in results.items():
        # 跳过非玩家ID的键（如'_prophet_inference_result'）
        if isinstance(player_id, str) and player_id.startswith('_'):
            continue
        # 获取身份名称
        role_names = {}
        roles = query_all("SELECT id, name, camp FROM roles")
        for r in roles:
            role_names[r["id"]] = {"name": r["name"], "camp": r["camp"]}
        probs = []
        for rid, prob in sorted(data["probabilities"].items(), key=lambda x: -x[1]):
            probs.append({
                "role_id": rid,
                "role_name": role_names.get(rid, {}).get("name", ""),
                "camp": role_names.get(rid, {}).get("camp", ""),
                "probability": prob
            })
        output.append({
            "player_id": player_id,
            "player_name": data["player_name"],
            "top_role_id": data["top_role_id"],
            "top_role_name": data["top_role_name"],
            "top_probability": data["top_probability"],
            "all_probabilities": probs
        })
    return ok(output, "预测完成")


@api.route('/games/<int:game_id>/predictions/refresh', methods=['POST'])
def refresh_predictions(game_id):
    """强制重新计算预测（录入新行为后调用）"""
    game = query_one("SELECT * FROM games WHERE id = " + ph(), (game_id,))
    if not game:
        return fail("对局不存在", 404)
    results = predict_game(game_id)
    return ok({"players_count": len(results)}, "预测已刷新")


@api.route('/games/<int:game_id>/scores', methods=['GET'])
def get_game_scores(game_id):
    """获取某局的预测打分明细（对局确认后可用）"""
    game = query_one("SELECT * FROM games WHERE id = " + ph(), (game_id,))
    if not game:
        return fail("对局不存在", 404)
    scores = query_all("""
        SELECT ps.*, p.name as player_name,
               pr.name as predicted_role_name,
               ar.name as actual_role_name
        FROM prediction_scores ps
        JOIN players p ON ps.player_id = p.id
        LEFT JOIN roles pr ON ps.predicted_role_id = pr.id
        LEFT JOIN roles ar ON ps.actual_role_id = ar.id
        WHERE ps.game_id = """ + ph() + " ORDER BY ps.id", (game_id,))
    if not scores:
        return ok([], "暂无打分明细（对局确认后生成）")
    total = len(scores)
    correct = sum(1 for s in scores if s.get("is_correct"))
    return ok({
        "total_players": total,
        "correct_count": correct,
        "accuracy": round(correct / total, 4) if total > 0 else 0,
        "details": scores
    }, "打分结果")


@api.route('/algorithm/weights', methods=['GET'])
def list_algorithm_weights():
    """查看算法权重表（贝叶斯参数）"""
    weights = query_all("""
        SELECT aw.*, a.name as action_name, r.name as role_name, r.camp
        FROM algorithm_weights aw
        JOIN actions a ON aw.action_id = a.id
        JOIN roles r ON aw.role_id = r.id
        ORDER BY r.camp, r.name, a.name
    """)
    return ok(weights)


# ============================================================
# 8. 玩家关系图与回溯推断（第二阶段）
# ============================================================
@api.route('/games/<int:game_id>/relationships/extract', methods=['POST'])
def extract_game_relationships(game_id):
    """从行为记录中提取玩家间关系（重新提取，会覆盖已有关系）"""
    game = query_one("SELECT * FROM games WHERE id = " + ph(), (game_id,))
    if not game:
        return fail("对局不存在", 404)
    count = extract_relationships(game_id)
    return ok({"extracted_count": count}, f"成功提取 {count} 条玩家关系")


@api.route('/games/<int:game_id>/relationships', methods=['GET'])
def get_game_relationships(game_id):
    """获取对局的玩家关系图"""
    game = query_one("SELECT * FROM games WHERE id = " + ph(), (game_id,))
    if not game:
        return fail("对局不存在", 404)
    graph = get_relationship_graph(game_id)
    return ok(graph)


@api.route('/games/<int:game_id>/backtrack', methods=['POST'])
def backtrack_game(game_id):
    """回溯推断：当某个玩家身份被确认后，回溯修正相关玩家概率

    请求体：
        player_id: 被确认身份的玩家ID
        camp: 确认的阵营（好人/狼人）
        role_id: 确认的具体身份（可选）
    """
    game = query_one("SELECT * FROM games WHERE id = " + ph(), (game_id,))
    if not game:
        return fail("对局不存在", 404)
    data = request.get_json() or {}
    player_id = data.get('player_id')
    camp = data.get('camp')
    role_id = data.get('role_id')
    if not player_id or not camp:
        return fail("玩家ID和阵营不能为空")
    # 先确保关系已提取
    extract_relationships(game_id)
    # 执行回溯推断
    adjustments = backtrack_inference(game_id, player_id, camp, role_id)
    return ok({
        "confirmed_player_id": player_id,
        "confirmed_camp": camp,
        "adjustments": adjustments
    }, f"回溯推断完成，发现 {len(adjustments)} 条修正建议")


# ============================================================
# 9. 游戏流程阶段控制
# ============================================================
@api.route('/games/<int:game_id>/phase', methods=['GET'])
def get_game_phase(game_id):
    """获取对局当前阶段和轮次"""
    game = query_one("SELECT * FROM games WHERE id = " + ph(), (game_id,))
    if not game:
        return fail("对局不存在", 404)
    phase = get_current_phase(game_id)
    return ok(phase)


@api.route('/games/<int:game_id>/phase/advance', methods=['POST'])
def advance_game_phase(game_id):
    """推进到下一阶段

    请求体（可选）：
        pk_round: 是否是PK发言轮次（平票后追加）
    """
    game = query_one("SELECT * FROM games WHERE id = " + ph(), (game_id,))
    if not game:
        return fail("对局不存在", 404)
    data = request.get_json() or {}
    pk_round = data.get('pk_round', False)
    phase = advance_phase(game_id, pk_round=pk_round)
    return ok(phase, f"已推进到：第{phase['round']}轮 {phase['display']}")


@api.route('/games/<int:game_id>/phase/self_explode', methods=['POST'])
def wolf_self_explode_phase(game_id):
    """狼人自爆：直接进入下一个黑夜"""
    game = query_one("SELECT * FROM games WHERE id = " + ph(), (game_id,))
    if not game:
        return fail("对局不存在", 404)
    phase = wolf_self_explode(game_id)
    return ok(phase, f"狼人自爆！进入第{phase['round']}轮 {phase['display']}")


@api.route('/games/<int:game_id>/phase', methods=['PUT'])
def set_game_phase(game_id):
    """手动设置当前阶段（用于调整）

    请求体：
        phase: 阶段名称
        round: 轮次（可选）
    """
    game = query_one("SELECT * FROM games WHERE id = " + ph(), (game_id,))
    if not game:
        return fail("对局不存在", 404)
    data = request.get_json() or {}
    phase = data.get('phase')
    round_number = data.get('round')
    if not phase:
        return fail("阶段名称不能为空")
    result = set_phase(game_id, phase, round_number)
    return ok(result, f"已设置为：第{result['round']}轮 {result['display']}")


# ============================================================
# 10. 确认身份（逻辑基点）
# ============================================================
@api.route('/games/<int:game_id>/confirmed_identities', methods=['GET'])
def list_confirmed_identities(game_id):
    """获取对局的确认身份列表"""
    game = query_one("SELECT * FROM games WHERE id = " + ph(), (game_id,))
    if not game:
        return fail("对局不存在", 404)
    identities = query_all(
        f"""SELECT ci.*, p.name as player_name, r.name as role_name, r.camp as role_camp
            FROM game_confirmed_identities ci
            JOIN players p ON ci.player_id = p.id
            LEFT JOIN roles r ON ci.role_id = r.id
            WHERE ci.game_id = {ph()}
            ORDER BY ci.confirmed_at""",
        (game_id,)
    )
    return ok(identities)


@api.route('/games/<int:game_id>/confirmed_identities', methods=['POST'])
def set_confirmed_identity(game_id):
    """设置确认身份

    请求体：
        player_id: 玩家ID
        role_id: 身份ID（可选，与camp二选一）
        camp: 阵营（可选，与role_id二选一）
        reason: 确认原因（如"单边预言家"、"自爆"等）
    """
    game = query_one("SELECT * FROM games WHERE id = " + ph(), (game_id,))
    if not game:
        return fail("对局不存在", 404)
    data = request.get_json() or {}
    player_id = data.get('player_id')
    role_id = data.get('role_id')
    camp = data.get('camp')
    reason = data.get('reason', '')

    if not player_id:
        return fail("玩家ID不能为空")
    if not role_id and not camp:
        return fail("身份和阵营至少填写一个")

    # 检查玩家是否在对局中
    game_player = query_one(
        f"SELECT * FROM game_players WHERE game_id = {ph()} AND player_id = {ph()}",
        (game_id, player_id)
    )
    if not game_player:
        return fail("该玩家不在此对局中")

    # 删除已有的确认身份（如果存在）
    execute_write(
        f"DELETE FROM game_confirmed_identities WHERE game_id = {ph()} AND player_id = {ph()}",
        (game_id, player_id)
    )

    # 插入新的确认身份
    execute_write(
        f"""INSERT INTO game_confirmed_identities (game_id, player_id, role_id, camp, reason)
            VALUES ({ph()}, {ph()}, {ph()}, {ph()}, {ph()})""",
        (game_id, player_id, role_id, camp, reason)
    )

    # 触发回溯推断（如果确认了阵营）
    if camp:
        try:
            backtrack_inference(game_id, player_id, camp)
        except Exception as e:
            print(f"回溯推断失败: {e}")

    return ok(message="确认身份设置成功，已触发回溯推断")


@api.route('/confirmed_identities/<int:identity_id>', methods=['DELETE'])
def delete_confirmed_identity(identity_id):
    """删除确认身份"""
    identity = query_one("SELECT * FROM game_confirmed_identities WHERE id = " + ph(), (identity_id,))
    if not identity:
        return fail("确认身份不存在", 404)
    execute_write(f"DELETE FROM game_confirmed_identities WHERE id = {ph()}", (identity_id,))
    return ok(message="确认身份已删除")


# ============================================================
# 11. 预言家查验推导
# ============================================================
@api.route('/games/<int:game_id>/prophet_inference', methods=['GET'])
def get_prophet_inference(game_id):
    """获取对局的预言家查验推导信息"""
    game = query_one("SELECT * FROM games WHERE id = " + ph(), (game_id,))
    if not game:
        return fail("对局不存在", 404)
    prophet_claims = get_prophet_claims(game_id)
    # 获取预测结果，填充预言家概率
    predictions = get_predictions(game_id)
    for claim in prophet_claims:
        player_id = claim['player_id']
        if player_id in predictions:
            probs = predictions[player_id].get('probabilities', {})
            claim['prophet_probability'] = probs.get(1, 0)

    # 应用唯一性约束
    from prophet_inference import apply_uniqueness_constraint, detect_contradictions, analyze_check_chains
    prophet_claims, _ = apply_uniqueness_constraint(prophet_claims)
    contradictions = detect_contradictions(prophet_claims)
    chains = analyze_check_chains(prophet_claims)

    return ok({
        'prophet_claims': prophet_claims,
        'contradictions': contradictions,
        'chains': chains,
        'count': len(prophet_claims)
    })
