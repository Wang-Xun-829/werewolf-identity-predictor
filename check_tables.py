import sqlite3
conn = sqlite3.connect('werewolf.db')
cur = conn.cursor()
# 查看所有表
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [row[0] for row in cur.fetchall()]
print('数据库中的表:')
for t in tables:
    print('  - ' + t)
print()
# 检查game_confirmed_identities表是否存在
if 'game_confirmed_identities' in tables:
    print('game_confirmed_identities 表存在')
else:
    print('game_confirmed_identities 表不存在！')
conn.close()
