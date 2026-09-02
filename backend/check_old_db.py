import sqlite3

conn = sqlite3.connect(r'D:\project-AI\werewolf_2\werewolf.db')
cursor = conn.cursor()

# 获取所有表名
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = cursor.fetchall()
print('数据库中的表:')
for table in tables:
    print(f'  - {table[0]}')

print()

# 查看每个表的结构
for table in tables:
    table_name = table[0]
    print(f'=== {table_name} ===')
    cursor.execute(f'PRAGMA table_info({table_name})')
    columns = cursor.fetchall()
    for col in columns:
        print(f'  {col[1]} ({col[2]})')
    print()

    # 查看数据量
    try:
        cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
        count = cursor.fetchone()[0]
        print(f'  数据量: {count} 条')
        print()
    except:
        pass

conn.close()
