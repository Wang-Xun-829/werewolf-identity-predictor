import sqlite3

conn = sqlite3.connect('werewolf.db')
cur = conn.cursor()

# 检查字段是否存在
cur.execute('PRAGMA table_info(actions)')
columns = [col[1] for col in cur.fetchall()]
print('actions表现有字段:', columns)

# 添加新字段
if 'action_type' not in columns:
    cur.execute("ALTER TABLE actions ADD COLUMN action_type VARCHAR(30) DEFAULT 'other'")
    print('添加 action_type 字段')
if 'certainty' not in columns:
    cur.execute("ALTER TABLE actions ADD COLUMN certainty VARCHAR(20) DEFAULT 'probabilistic'")
    print('添加 certainty 字段')
if 'determine_content' not in columns:
    cur.execute("ALTER TABLE actions ADD COLUMN determine_content VARCHAR(100)")
    print('添加 determine_content 字段')
if 'trigger_condition' not in columns:
    cur.execute("ALTER TABLE actions ADD COLUMN trigger_condition VARCHAR(100)")
    print('添加 trigger_condition 字段')
if 'has_result_status' not in columns:
    cur.execute("ALTER TABLE actions ADD COLUMN has_result_status BOOLEAN DEFAULT 0")
    print('添加 has_result_status 字段')

# behavior_records表
cur.execute('PRAGMA table_info(behavior_records)')
columns = [col[1] for col in cur.fetchall()]
print('behavior_records表现有字段:', columns)

if 'result_status' not in columns:
    cur.execute("ALTER TABLE behavior_records ADD COLUMN result_status VARCHAR(20) DEFAULT 'unconfirmed'")
    print('添加 result_status 字段')
if 'derived_from' not in columns:
    cur.execute("ALTER TABLE behavior_records ADD COLUMN derived_from INTEGER")
    print('添加 derived_from 字段')

conn.commit()

# 为现有行为设置语义属性
cur.execute("UPDATE actions SET action_type = 'identity_confirm', certainty = 'absolute', determine_content = 'actor_werewolf' WHERE name LIKE '%自爆%'")
cur.execute("UPDATE actions SET action_type = 'identity_confirm', certainty = 'absolute', determine_content = 'actor_hunter_or_wolf_king' WHERE name LIKE '%开枪%'")
cur.execute("UPDATE actions SET action_type = 'identity_claim', certainty = 'probabilistic' WHERE name LIKE '跳%' AND name NOT LIKE '%对跳%'")
cur.execute("UPDATE actions SET action_type = 'identity_conflict', certainty = 'probabilistic', determine_content = 'at_least_one_werewolf' WHERE name LIKE '%对跳%'")
cur.execute("UPDATE actions SET action_type = 'check_result', certainty = 'conditional', trigger_condition = 'if_actor_is_prophet' WHERE name LIKE '%金水%' OR name LIKE '%查杀%'")
cur.execute("UPDATE actions SET determine_content = 'target_good' WHERE name LIKE '%金水%'")
cur.execute("UPDATE actions SET determine_content = 'target_werewolf' WHERE name LIKE '%查杀%'")
cur.execute("UPDATE actions SET action_type = 'stance_expression', certainty = 'probabilistic', has_result_status = 1 WHERE name LIKE '%保%' OR name LIKE '%踩%' OR name LIKE '%站边%' OR name LIKE '%晃边%' OR name LIKE '%反水%'")
cur.execute("UPDATE actions SET action_type = 'vote_action', certainty = 'probabilistic', has_result_status = 1 WHERE name LIKE '%票%'")
cur.execute("UPDATE actions SET action_type = 'event', certainty = 'absolute' WHERE name LIKE '%死亡%' OR name LIKE '%死%' OR name LIKE '%平安夜%'")
cur.execute("UPDATE actions SET has_result_status = 1 WHERE name LIKE '%对%' OR name LIKE '%错%'")

conn.commit()
print('数据库迁移完成！')

# 验证
cur.execute('SELECT id, name, action_type, certainty, determine_content, has_result_status FROM actions LIMIT 15')
print('\n验证结果（前15条）：')
for row in cur.fetchall():
    print(row)

conn.close()
