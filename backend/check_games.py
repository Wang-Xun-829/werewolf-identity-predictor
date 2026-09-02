"""检查本地数据库中的对局和行为记录"""
from database import get_db, init_db
from models import Game, Action, ActionType, Player

init_db()
db = next(get_db())

games = db.query(Game).all()
print(f'本地数据库共有 {len(games)} 个对局')
for game in games:
    action_count = db.query(Action).filter(Action.game_id == game.id).count()
    print(f'  对局{game.id}: {game.name or "未命名"}, 玩家数={game.player_count}, 状态={game.status}, 行为记录={action_count}条')

# 找一个有行为记录的对局
for game in games:
    action_count = db.query(Action).filter(Action.game_id == game.id).count()
    if action_count > 0:
        print(f'\n=== 使用对局{game.id}进行测试 ===')
        actions = db.query(Action).filter(Action.game_id == game.id).all()
        action_type_map = {at.id: at.name for at in db.query(ActionType).all()}
        player_map = {p.id: p.name for p in db.query(Player).all()}
        
        for action in actions[:10]:
            action_name = action_type_map.get(action.action_type_id, '未知')
            actor_name = player_map.get(action.player_id, '未知')
            target_name = player_map.get(action.target_player_id, '无') if action.target_player_id else '无'
            print(f'  轮次{action.round_number} {action.phase}: {actor_name} -> {target_name}, 行为={action_name}')
        break
