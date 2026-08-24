"""
生成完整的 init.sql 文件（建表 + 初始数据 + 算法权重）
用户可以在 Neon 控制台的 SQL Editor 中直接执行
"""
import json

# 身份列表
roles = [
    ("预言家", "好人", "每晚可查验一名玩家身份"),
    ("女巫", "好人", "拥有一瓶解药和一瓶毒药"),
    ("猎人", "好人", "被淘汰时可开枪带走一人"),
    ("白痴", "好人", "被投票出局时可翻牌免死"),
    ("守卫", "好人", "每晚可守护一人免受狼人杀害"),
    ("平民", "好人", "无特殊技能，靠推理投票"),
    ("狼人", "狼人", "每晚可杀害一人"),
    ("狼王", "狼人", "被淘汰时可开枪带走一人"),
    ("白狼王", "狼人", "白天可自爆带走一人"),
    ("丘比特", "第三方", "可连接两名玩家成为情侣"),
    ("盗贼", "第三方", "开局可从两张额外身份牌中选择"),
]

# 行为列表
actions = [
    ("跳预言家", "声称自己是预言家", 2.0),
    ("查杀", "预言家查验某人为狼人", 3.0),
    ("发金水", "预言家查验某人为好人", 2.5),
    ("跳女巫", "声称自己是女巫", 2.0),
    ("跳猎人", "声称自己是猎人", 1.5),
    ("跳守卫", "声称自己是守卫", 1.5),
    ("认平民", "声称自己是平民", 1.0),
    ("投票", "投票放逐某玩家", 1.0),
    ("弃票", "投票阶段弃票", 0.8),
    ("站边", "表示支持某名预言家", 1.2),
    ("倒钩", "狼人假装好人站边真预言家", 1.5),
    ("冲锋", "狼人积极为狼队友号票", 1.5),
    ("自爆", "狼人白天自爆身份", 5.0),
    ("开枪", "猎人/狼王被淘汰时开枪带人", 3.0),
    ("使用解药", "女巫使用解药救人", 2.5),
    ("使用毒药", "女巫使用毒药毒人", 2.5),
    ("守护", "守卫守护某玩家", 2.0),
    ("质疑", "质疑某玩家身份", 1.0),
    ("划水", "发言无营养、回避分析", 0.8),
]

# 版型列表
setups = [
    ("预女猎白", '{"狼人":4,"预言家":1,"女巫":1,"猎人":1,"白痴":1,"平民":4}', "12人标准局"),
    ("预女猎守", '{"狼人":4,"预言家":1,"女巫":1,"猎人":1,"守卫":1,"平民":4}', "12人守卫局"),
    ("狼王守卫", '{"狼人":3,"狼王":1,"预言家":1,"女巫":1,"猎人":1,"守卫":1,"平民":4}', "12人狼王守卫局"),
    ("白狼王守卫", '{"狼人":3,"白狼王":1,"预言家":1,"女巫":1,"猎人":1,"守卫":1,"平民":4}', "12人白狼王守卫局"),
    ("9人预女猎", '{"狼人":3,"预言家":1,"女巫":1,"猎人":1,"平民":3}', "9人标准局"),
]

# 读取 schema.sql
with open("schema.sql", "r", encoding="utf-8") as f:
    schema_sql = f.read()

# 生成 INSERT 语句
sql_parts = [
    "-- ============================================================",
    "-- 狼人杀身份预测程序 - 完整初始化脚本",
    "-- 适用于 PostgreSQL (Neon)",
    "-- ============================================================",
    "",
    "-- ========== 建表 ==========",
    schema_sql,
    "",
    "-- ========== 初始身份数据 ==========",
]

for i, (name, camp, desc) in enumerate(roles, 1):
    sql_parts.append(f"INSERT INTO roles (id, name, camp, description) VALUES ({i}, '{name}', '{camp}', '{desc}');")

sql_parts.append("")
sql_parts.append("-- ========== 初始行为数据 ==========")
for i, (name, desc, weight) in enumerate(actions, 1):
    sql_parts.append(f"INSERT INTO actions (id, name, description, default_weight) VALUES ({i}, '{name}', '{desc}', {weight});")

sql_parts.append("")
sql_parts.append("-- ========== 初始版型数据 ==========")
for i, (name, config, desc) in enumerate(setups, 1):
    # 转义单引号
    config_escaped = config.replace("'", "''")
    desc_escaped = desc.replace("'", "''")
    sql_parts.append(f"INSERT INTO setups (id, name, role_config, description) VALUES ({i}, '{name}', '{config_escaped}', '{desc_escaped}');")

# 生成算法权重
sql_parts.append("")
sql_parts.append("-- ========== 初始算法权重数据（行为×身份的语义关联） ==========")

wolf_role_ids = {7, 8, 9}  # 狼人、狼王、白狼王
weight_id = 1

for action_idx, (aname, adesc, default_w) in enumerate(actions, 1):
    for role_idx, (rname, camp, rdesc) in enumerate(roles, 1):
        weight = default_w

        # 规则1：行为名称包含身份名称（跳预言家、跳女巫、跳猎人、跳守卫）
        if rname in aname and "跳" in aname:
            weight = default_w * 3
            if role_idx in wolf_role_ids:
                weight = default_w * 1.5  # 狼人悍跳

        # 规则2：狼人特有行为
        elif aname in ("自爆", "冲锋", "倒钩"):
            if role_idx in wolf_role_ids:
                weight = default_w * 3
            else:
                weight = default_w * 0.3

        # 规则3：好人技能行为
        elif aname in ("使用解药", "使用毒药") and rname == "女巫":
            weight = default_w * 3
        elif aname == "守护" and rname == "守卫":
            weight = default_w * 3
        elif aname == "开枪" and rname in ("猎人", "狼王"):
            weight = default_w * 3

        # 规则4：认平民
        elif aname == "认平民":
            if rname == "平民":
                weight = default_w * 2
            else:
                weight = default_w * 0.5

        # 规则5：查杀/发金水更可能是预言家或悍跳狼
        elif aname in ("查杀", "发金水"):
            if rname == "预言家":
                weight = default_w * 3
            elif role_idx in wolf_role_ids:
                weight = default_w * 1.5
            else:
                weight = default_w * 0.3

        sql_parts.append(
            f"INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) "
            f"VALUES ({weight_id}, {action_idx}, {role_idx}, {weight}, 0);"
        )
        weight_id += 1

# 修复自增序列（PostgreSQL 需要设置序列起始值）
sql_parts.append("")
sql_parts.append("-- ========== 修复自增序列 ==========")
sql_parts.append(f"SELECT setval('roles_id_seq', (SELECT MAX(id) FROM roles));")
sql_parts.append(f"SELECT setval('actions_id_seq', (SELECT MAX(id) FROM actions));")
sql_parts.append(f"SELECT setval('setups_id_seq', (SELECT MAX(id) FROM setups));")
sql_parts.append(f"SELECT setval('algorithm_weights_id_seq', (SELECT MAX(id) FROM algorithm_weights));")
sql_parts.append("")
sql_parts.append("-- ========== 初始化完成 ==========")

# 写入文件
with open("init.sql", "w", encoding="utf-8") as f:
    f.write("\n".join(sql_parts))

print(f"✅ init.sql 生成完成！")
print(f"  身份: {len(roles)} 个")
print(f"  行为: {len(actions)} 个")
print(f"  版型: {len(setups)} 个")
print(f"  算法权重: {weight_id - 1} 条")
print(f"  文件大小: {len(chr(10).join(sql_parts))} 字符")
print(f"\n请在 Neon 控制台的 SQL Editor 中打开并执行 init.sql")
