"""
重新运行预测算法，检查是否有问题
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

os.environ['DATABASE_URL'] = "postgresql://neondb_owner:npg_u1rFnCVX7NTx@ep-restless-feather-azyo5mej-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

from db import query_all, query_one, ph, execute_write
from prediction import predict_game

game_id = 17

print(f"重新运行对局 #{game_id} 的预测算法...")

try:
    results = predict_game(game_id)
    print(f"预测完成，返回 {len(results)} 个玩家的结果")

    print("\n预测结果详情:")
    for player_id, data in results.items():
        player_name = data.get('player_name', f'玩家{player_id}')
        top_role = data.get('top_role_name', '未知')
        top_prob = data.get('top_probability', 0)
        print(f"  {player_name}: 最高概率身份={top_role} ({top_prob:.2%})")

        # 打印所有身份的概率
        probs = data.get('probabilities', {})
        for role_id, prob in sorted(probs.items(), key=lambda x: -x[1])[:5]:
            role = query_one("SELECT name FROM roles WHERE id = " + ph(), (role_id,))
            role_name = role['name'] if role else f'身份{role_id}'
            print(f"    {role_name}: {prob:.4f} ({prob:.2%})")

except Exception as e:
    import traceback
    print(f"预测算法出错: {e}")
    print(f"错误堆栈: {traceback.format_exc()}")
