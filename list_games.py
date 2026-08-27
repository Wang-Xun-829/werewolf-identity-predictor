"""
列出线上所有对局
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

os.environ['DATABASE_URL'] = "postgresql://neondb_owner:npg_u1rFnCVX7NTx@ep-restless-feather-azyo5mej-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

from db import query_all

games = query_all("""
    SELECT g.*, s.name as setup_name
    FROM games g
    LEFT JOIN setups s ON g.setup_id = s.id
    ORDER BY g.id DESC
""")

print(f"找到 {len(games)} 个对局:")
print()
for i, g in enumerate(games, 1):
    status = g.get('status', '未知')
    setup = g.get('setup_name', '未指定版型')
    code = g.get('game_code', '未命名')
    print(f"  {i}. 对局 #{g['id']} - {code} ({setup}) - 状态: {status}")
