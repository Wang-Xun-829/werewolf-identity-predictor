import sqlite3
conn = sqlite3.connect('werewolf_v5.db')
cursor = conn.cursor()

print("=" * 60)
print("查询确认身份记录")
print("=" * 60)
cursor.execute("""
    SELECT ci.id, ci.game_id, ci.player_id, p.name as player_name, 
           ci.identity_id, ident.name as identity_name,
           ci.camp_only, ci.reason, ci.created_at
    FROM confirmed_identities ci
    LEFT JOIN players p ON ci.player_id = p.id
    LEFT JOIN identities ident ON ci.identity_id = ident.id
    ORDER BY ci.id DESC
    LIMIT 10
""")
rows = cursor.fetchall()
if rows:
    for row in rows:
        print(f"ID:{row[0]} 玩家:{row[3]} 身份:{row[5]} 阵营:{row[6]} 原因:{row[7]}")
else:
    print("没有确认身份记录")

print("\n" + "=" * 60)
print("查询最近的骑士决斗行为记录")
print("=" * 60)
cursor.execute("""
    SELECT a.id, a.game_id, a.player_id, p1.name as player_name,
           a.target_player_id, p2.name as target_name,
           a.action_type_id, at.name as action_name,
           a.notes, a.result_status, a.created_at
    FROM actions a
    LEFT JOIN players p1 ON a.player_id = p1.id
    LEFT JOIN players p2 ON a.target_player_id = p2.id
    LEFT JOIN action_types at ON a.action_type_id = at.id
    WHERE a.action_type_id = 65
    ORDER BY a.id DESC
    LIMIT 5
""")
rows = cursor.fetchall()
if rows:
    for row in rows:
        print(f"ID:{row[0]} {row[3]} → {row[5]}: {row[7]} 备注:{row[8]} 结果:{row[9]}")
else:
    print("没有骑士决斗行为记录")

conn.close()
