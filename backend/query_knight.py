import sqlite3
conn = sqlite3.connect('werewolf_v5.db')
cursor = conn.cursor()
cursor.execute("SELECT id, name, category, parent_id, description FROM action_types WHERE name LIKE '%决斗%' OR name LIKE '%骑士%'")
rows = cursor.fetchall()
for row in rows:
    print(f'ID:{row[0]} 名称:{row[1]} 分类:{row[2]} 父ID:{row[3]} 描述:{row[4]}')
conn.close()
