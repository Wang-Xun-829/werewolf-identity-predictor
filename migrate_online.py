import psycopg
import time

# 连接线上Neon数据库（使用直接地址）
conn = psycopg.connect(
    'postgresql://neondb_owner:npg_u1rFnCVX7NTx@ep-restless-feather-azyo5mej.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&connect_timeout=30'
)
cur = conn.cursor()

# 检查字段是否存在
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'actions' AND column_name = 'action_type'
""")
exists = cur.fetchone()

if not exists:
    print('开始迁移 actions 表...')
    cur.execute("ALTER TABLE actions ADD COLUMN action_type VARCHAR(30) DEFAULT 'other'")
    cur.execute("ALTER TABLE actions ADD COLUMN certainty VARCHAR(20) DEFAULT 'probabilistic'")
    cur.execute("ALTER TABLE actions ADD COLUMN determine_content VARCHAR(100)")
    cur.execute("ALTER TABLE actions ADD COLUMN trigger_condition VARCHAR(100)")
    cur.execute("ALTER TABLE actions ADD COLUMN has_result_status BOOLEAN DEFAULT FALSE")
    print('actions 表迁移完成')
else:
    print('actions 表已存在新字段，跳过')

# behavior_records表
cur.execute("""
    SELECT column_name FROM information_schema.columns 
    WHERE table_name = 'behavior_records' AND column_name = 'result_status'
""")
exists = cur.fetchone()

if not exists:
    print('开始迁移 behavior_records 表...')
    cur.execute("ALTER TABLE behavior_records ADD COLUMN result_status VARCHAR(20) DEFAULT 'unconfirmed'")
    cur.execute("ALTER TABLE behavior_records ADD COLUMN derived_from INTEGER")
    print('behavior_records 表迁移完成')
else:
    print('behavior_records 表已存在新字段，跳过')

conn.commit()

# 为现有行为设置语义属性
print('开始设置行为语义属性...')
cur.execute("UPDATE actions SET action_type = 'identity_confirm', certainty = 'absolute', determine_content = 'actor_werewolf' WHERE name LIKE '%自爆%'")
cur.execute("UPDATE actions SET action_type = 'identity_confirm', certainty = 'absolute', determine_content = 'actor_hunter_or_wolf_king' WHERE name LIKE '%开枪%'")
cur.execute("UPDATE actions SET action_type = 'identity_claim', certainty = 'probabilistic' WHERE name LIKE '跳%' AND name NOT LIKE '%对跳%'")
cur.execute("UPDATE actions SET action_type = 'identity_conflict', certainty = 'probabilistic', determine_content = 'at_least_one_werewolf' WHERE name LIKE '%对跳%'")
cur.execute("UPDATE actions SET action_type = 'check_result', certainty = 'conditional', trigger_condition = 'if_actor_is_prophet' WHERE name LIKE '%金水%' OR name LIKE '%查杀%'")
cur.execute("UPDATE actions SET determine_content = 'target_good' WHERE name LIKE '%金水%'")
cur.execute("UPDATE actions SET determine_content = 'target_werewolf' WHERE name LIKE '%查杀%'")
cur.execute("UPDATE actions SET action_type = 'stance_expression', certainty = 'probabilistic', has_result_status = TRUE WHERE name LIKE '%保%' OR name LIKE '%踩%' OR name LIKE '%站边%' OR name LIKE '%晃边%' OR name LIKE '%反水%'")
cur.execute("UPDATE actions SET action_type = 'vote_action', certainty = 'probabilistic', has_result_status = TRUE WHERE name LIKE '%票%'")
cur.execute("UPDATE actions SET action_type = 'event', certainty = 'absolute' WHERE name LIKE '%死亡%' OR name LIKE '%死%' OR name LIKE '%平安夜%'")
cur.execute("UPDATE actions SET has_result_status = TRUE WHERE name LIKE '%对%' OR name LIKE '%错%'")

conn.commit()
print('行为语义属性设置完成')

# 验证
cur.execute('SELECT COUNT(*) FROM actions WHERE action_type != %s', ('other',))
count = cur.fetchone()[0]
print(f'已设置语义属性的行为数量: {count}')

cur.execute('SELECT id, name, action_type, certainty, determine_content FROM actions WHERE action_type != %s LIMIT 10', ('other',))
print('\n验证结果（前10条）：')
for row in cur.fetchall():
    print(row)

cur.close()
conn.close()
print('\n线上数据库迁移完成！')
