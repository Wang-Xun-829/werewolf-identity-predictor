"""检查对局17的行为记录"""
from database import get_db, init_db
from models import Action, ActionType, Player

init_db()
db = next(get_db())

# 获取对局17的所有行为
actions = db.query(Action).filter(Action.game_id == 17).all()
action_type_map = {at.id: at.name for at in db.query(ActionType).all()}
player_map = {p.id: p.name for p in db.query(Player).all()}

print(f'对局17共有 {len(actions)} 条行为记录')
print('=== 行为类型列表 ===')
for at in db.query(ActionType).all():
    print(f'  ID={at.id}, 名称={at.name}, 父ID={at.parent_id}')

print('\n=== 对局17行为记录 ===')
for action in actions[:20]:  # 只显示前20条
    action_name = action_type_map.get(action.action_type_id, '未知')
    actor_name = player_map.get(action.player_id, '未知')
    target_name = player_map.get(action.target_player_id, '无') if action.target_player_id else '无'
    print(f'  轮次{action.round_number} {action.phase}: {actor_name} -> {target_name}, 行为={action_name}')
