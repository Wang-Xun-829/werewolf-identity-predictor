import sqlite3

conn = sqlite3.connect('werewolf_v5.db')
cursor = conn.cursor()

# 查看所有表
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('数据库中的表:')
for t in tables:
    print(' -', t[0])

print()

# 查看setups表
try:
    cursor.execute('SELECT * FROM setups')
    setups = cursor.fetchall()
    print('setups表数据:')
    for s in setups:
        print(' ', s)
except Exception as e:
    print('setups表查询失败:', e)

print()

# 查看所有包含setup或identity的表
for t in tables:
    tname = t[0]
    if 'setup' in tname.lower() or 'identity' in tname.lower():
        print(f'=== 表 {tname} ===')
        try:
            cursor.execute(f'PRAGMA table_info({tname})')
            cols = cursor.fetchall()
            print('结构:')
            for c in cols:
                print(' ', c)
            cursor.execute(f'SELECT * FROM {tname}')
            rows = cursor.fetchall()
            print('数据:')
            for r in rows:
                print(' ', r)
        except Exception as e:
            print('查询失败:', e)
        print()

conn.close()
