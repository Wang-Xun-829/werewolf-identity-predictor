import sqlite3
conn = sqlite3.connect('werewolf_v5.db')
cursor = conn.cursor()

print("=" * 60)
print("查询所有身份")
print("=" * 60)
cursor.execute("SELECT id, name, faction_id, is_god, is_active FROM identities ORDER BY id")
rows = cursor.fetchall()
for row in rows:
    print(f"ID:{row[0]} 名称:{row[1]} 阵营ID:{row[2]} 神职:{row[3]} 启用:{row[4]}")

print("\n" + "=" * 60)
print("查询名称包含'骑士'的身份")
print("=" * 60)
cursor.execute("SELECT id, name FROM identities WHERE name LIKE '%骑士%'")
rows = cursor.fetchall()
if rows:
    for row in rows:
        print(f"ID:{row[0]} 名称:{row[1]}")
else:
    print("没有找到包含'骑士'的身份")

conn.close()
