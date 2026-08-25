import sqlite3
conn = sqlite3.connect('werewolf.db')
cur = conn.cursor()
# 查看game_confirmed_identities表结构
cur.execute("PRAGMA table_info(game_confirmed_identities)")
columns = cur.fetchall()
print('game_confirmed_identities 表结构:')
for col in columns:
    print('  - ' + col[1] + ' (' + col[2] + ')')
print()
# 查看behavior_records表结构
cur.execute("PRAGMA table_info(behavior_records)")
columns = cur.fetchall()
print('behavior_records 表结构:')
for col in columns:
    print('  - ' + col[1] + ' (' + col[2] + ')')
conn.close()
