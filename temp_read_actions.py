import psycopg
import time

# 尝试多种连接方式
connection_strings = [
    # 直接地址（非池化）
    'postgresql://neondb_owner:npg_u1rFnCVX7NTx@ep-restless-feather-azyo5mej.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&connect_timeout=30',
    # 池化地址
    'postgresql://neondb_owner:npg_u1rFnCVX7NTx@ep-restless-feather-azyo5mej-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&connect_timeout=30',
]

conn = None
for i, cs in enumerate(connection_strings):
    try:
        print('尝试连接方式 {}...'.format(i+1))
        conn = psycopg.connect(cs)
        print('连接成功！')
        break
    except Exception as e:
        print('连接失败: {}'.format(str(e)[:100]))
        time.sleep(2)

if not conn:
    print('所有连接方式都失败了')
    exit(1)

cur = conn.cursor()

# 读取行为库所有数据
cur.execute('SELECT id, name, parent_id, default_weight, description FROM actions ORDER BY parent_id NULLS FIRST, id')
rows = cur.fetchall()

print()
print('=' * 80)
print('线上行为库数据（共{}条）'.format(len(rows)))
print('=' * 80)
print('{:<6}{:<20}{:<10}{:<10}{}'.format('ID', '行为名称', '父行为ID', '默认权重', '描述'))
print('-' * 80)

for row in rows:
    id, name, parent_id, default_weight, description = row
    parent_str = str(parent_id) if parent_id else '无(1级)'
    desc_str = description if description else ''
    print('{:<6}{:<20}{:<10}{:<10}{}'.format(id, name, parent_str, default_weight, desc_str))

print('=' * 80)

# 统计分级情况
cur.execute('''
    SELECT 
        CASE WHEN parent_id IS NULL THEN '1级行为' ELSE '2级及以下行为' END as level,
        COUNT(*) as count
    FROM actions 
    GROUP BY level
''')
stats = cur.fetchall()
print('分级统计：')
for stat in stats:
    print('  {}: {}条'.format(stat[0], stat[1]))

# 按层级显示树形结构
print()
print('=' * 80)
print('行为树形结构：')
print('=' * 80)

# 获取所有1级行为
cur.execute('SELECT id, name, default_weight FROM actions WHERE parent_id IS NULL ORDER BY id')
level1 = cur.fetchall()

for l1 in level1:
    l1_id, l1_name, l1_weight = l1
    print('  [{}] {} (权重:{})'.format(l1_id, l1_name, l1_weight))
    
    # 获取子行为
    cur.execute('SELECT id, name, default_weight FROM actions WHERE parent_id = %s ORDER BY id', (l1_id,))
    level2 = cur.fetchall()
    for l2 in level2:
        l2_id, l2_name, l2_weight = l2
        print('    └─ [{}] {} (权重:{})'.format(l2_id, l2_name, l2_weight))
        
        # 获取3级行为
        cur.execute('SELECT id, name, default_weight FROM actions WHERE parent_id = %s ORDER BY id', (l2_id,))
        level3 = cur.fetchall()
        for l3 in level3:
            l3_id, l3_name, l3_weight = l3
            print('       └─ [{}] {} (权重:{})'.format(l3_id, l3_name, l3_weight))

cur.close()
conn.close()
print()
print('数据库连接已关闭')
