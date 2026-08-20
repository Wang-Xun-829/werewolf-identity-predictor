"""
数据库连接与初始化模块
- 本地开发：自动使用 SQLite（零配置，Python 自带）
- 线上部署：使用 PostgreSQL（Neon，通过 DATABASE_URL 环境变量连接）
"""
import os
import sqlite3
import re
from contextlib import contextmanager

# 判断使用哪种数据库
DATABASE_URL = os.getenv("DATABASE_URL", "")

if DATABASE_URL.startswith("postgresql"):
    DB_TYPE = "postgresql"
    import psycopg
    from psycopg.rows import dict_row
else:
    DB_TYPE = "sqlite"
    # 本地 SQLite 数据库文件路径
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "werewolf.db")


def get_db():
    """获取数据库连接（自动适配 SQLite / PostgreSQL）"""
    if DB_TYPE == "postgresql":
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        # 开启外键约束
        conn.execute("PRAGMA foreign_keys = ON")
        return conn


@contextmanager
def get_db_cursor():
    """上下文管理器：自动获取连接、创建游标、提交/回滚、关闭连接"""
    conn = get_db()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _convert_sql_for_sqlite(sql):
    """将 PostgreSQL 语法的 SQL 转换为 SQLite 兼容的语法"""
    # SERIAL PRIMARY KEY -> INTEGER PRIMARY KEY AUTOINCREMENT
    sql = re.sub(r'\bSERIAL\s+PRIMARY\s+KEY\b', 'INTEGER PRIMARY KEY AUTOINCREMENT', sql)
    # 单独的 SERIAL（如果有）-> INTEGER
    sql = re.sub(r'\bSERIAL\b', 'INTEGER', sql)
    # BOOLEAN -> INTEGER（SQLite 用 0/1 表示布尔）
    sql = re.sub(r'\bBOOLEAN\b', 'INTEGER', sql)
    # TIMESTAMP -> DATETIME
    sql = re.sub(r'\bTIMESTAMP\b', 'DATETIME', sql)
    # VARCHAR(n) -> TEXT（SQLite 不强制长度）
    sql = re.sub(r'VARCHAR\(\d+\)', 'TEXT', sql)
    return sql


def init_db():
    """初始化数据库：创建所有表和索引"""
    # 读取 schema.sql
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        sql_script = f.read()

    if DB_TYPE == "sqlite":
        sql_script = _convert_sql_for_sqlite(sql_script)

    conn = get_db()
    try:
        cur = conn.cursor()
        # 按分号分割执行多条语句
        statements = [s.strip() for s in sql_script.split(";") if s.strip()]
        for stmt in statements:
            cur.execute(stmt)
        conn.commit()
        print(f"[数据库初始化] 成功，共执行 {len(statements)} 条语句，数据库类型: {DB_TYPE}")
    except Exception as e:
        conn.rollback()
        print(f"[数据库初始化] 失败: {e}")
        raise
    finally:
        conn.close()


def seed_initial_data():
    """插入初始数据：默认身份、行为、版型（仅在表为空时插入）"""
    with get_db_cursor() as cur:
        # 检查是否已有数据
        cur.execute("SELECT COUNT(*) as cnt FROM roles")
        role_count = cur.fetchone()["cnt"] if DB_TYPE == "postgresql" else cur.fetchone()["cnt"]

        if role_count == 0:
            # 默认身份
            default_roles = [
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
            for name, camp, desc in default_roles:
                cur.execute(
                    "INSERT INTO roles (name, camp, description) VALUES (%s, %s, %s)"
                    if DB_TYPE == "postgresql" else
                    "INSERT INTO roles (name, camp, description) VALUES (?, ?, ?)",
                    (name, camp, desc)
                )
            print(f"[初始数据] 已插入 {len(default_roles)} 个身份")

        # 检查行为库
        cur.execute("SELECT COUNT(*) as cnt FROM actions")
        action_count = cur.fetchone()["cnt"]

        if action_count == 0:
            default_actions = [
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
            for name, desc, weight in default_actions:
                cur.execute(
                    "INSERT INTO actions (name, description, default_weight) VALUES (%s, %s, %s)"
                    if DB_TYPE == "postgresql" else
                    "INSERT INTO actions (name, description, default_weight) VALUES (?, ?, ?)",
                    (name, desc, weight)
                )
            print(f"[初始数据] 已插入 {len(default_actions)} 个行为")

        # 检查版型库
        cur.execute("SELECT COUNT(*) as cnt FROM setups")
        setup_count = cur.fetchone()["cnt"]

        if setup_count == 0:
            default_setups = [
                ("预女猎白", '{"狼人":4,"预言家":1,"女巫":1,"猎人":1,"白痴":1,"平民":4}', "12人标准局"),
                ("预女猎守", '{"狼人":4,"预言家":1,"女巫":1,"猎人":1,"守卫":1,"平民":4}', "12人守卫局"),
                ("狼王守卫", '{"狼人":3,"狼王":1,"预言家":1,"女巫":1,"猎人":1,"守卫":1,"平民":4}', "12人狼王守卫局"),
                ("白狼王守卫", '{"狼人":3,"白狼王":1,"预言家":1,"女巫":1,"猎人":1,"守卫":1,"平民":4}', "12人白狼王守卫局"),
                ("9人预女猎", '{"狼人":3,"预言家":1,"女巫":1,"猎人":1,"平民":3}', "9人标准局"),
            ]
            for name, config, desc in default_setups:
                cur.execute(
                    "INSERT INTO setups (name, role_config, description) VALUES (%s, %s, %s)"
                    if DB_TYPE == "postgresql" else
                    "INSERT INTO setups (name, role_config, description) VALUES (?, ?, ?)",
                    (name, config, desc)
                )
            print(f"[初始数据] 已插入 {len(default_setups)} 个版型")

    # 初始化算法权重（在 with 块之外调用，避免 SQLite 锁冲突）
    _seed_algorithm_weights()


def _seed_algorithm_weights():
    """初始化算法权重表：根据行为和身份的语义关系设置先验权重

    规则：
    - 身份特有行为（如"跳预言家"）：对应身份权重 ×3，狼人 ×1.5（悍跳），其他 ×0.3
    - 狼人特有行为（自爆、冲锋、倒钩）：狼人阵营 ×3，其他 ×0.3
    - 好人技能行为（解药、毒药、守护、开枪）：对应身份 ×3，其他 ×0.3
    - 认平民：平民 ×2，其他 ×0.5
    - 通用行为（投票、站边、质疑、划水等）：所有身份用默认权重
    """
    roles = query_all("SELECT id, name, camp FROM roles")
    actions = query_all("SELECT id, name, default_weight FROM actions")

    if not roles or not actions:
        return

    # 检查是否已有权重数据
    existing = query_all("SELECT COUNT(*) as cnt FROM algorithm_weights")
    if existing and existing[0]["cnt"] > 0:
        return

    role_name_to_id = {r["name"]: r["id"] for r in roles}
    wolf_role_ids = {r["id"] for r in roles if r["camp"] == "狼人"}

    inserted = 0
    for act in actions:
        aid = act["id"]
        aname = act["name"]
        default_w = act.get("default_weight", 1.0)

        for role in roles:
            rid = role["id"]
            rname = role["name"]
            weight = default_w  # 默认

            # 规则1：行为名称包含身份名称（跳预言家、跳女巫、跳猎人、跳守卫）
            if rname in aname and "跳" in aname:
                weight = default_w * 3
                if rid in wolf_role_ids:
                    weight = default_w * 1.5  # 狼人悍跳

            # 规则2：狼人特有行为
            elif aname in ("自爆", "冲锋", "倒钩"):
                if rid in wolf_role_ids:
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
                elif rid in wolf_role_ids:
                    weight = default_w * 1.5
                else:
                    weight = default_w * 0.3

            execute_write(
                f"INSERT INTO algorithm_weights (action_id, role_id, weight, sample_count) VALUES ({ph()}, {ph()}, {ph()}, 0)",
                (aid, rid, weight)
            )
            inserted += 1

    print(f"[初始数据] 已初始化 {inserted} 条算法权重")


if __name__ == "__main__":
    # 直接运行此文件可初始化数据库并插入初始数据
    init_db()
    seed_initial_data()
    print("数据库初始化完成！")


# ============================================================
# 通用数据库操作函数（供所有模块使用）
# ============================================================
def ph():
    """参数占位符：PostgreSQL 用 %s，SQLite 用 ?"""
    return '%s' if DB_TYPE == 'postgresql' else '?'


def query_all(sql, params=()):
    """查询多行，返回字典列表"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def query_one(sql, params=()):
    """查询单行，返回字典或 None"""
    conn = get_db()
    cur = conn.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def execute_write(sql, params=()):
    """执行 INSERT/UPDATE/DELETE，返回新插入的 ID（仅 INSERT）"""
    conn = get_db()
    cur = conn.cursor()
    new_id = None
    if DB_TYPE == 'postgresql' and sql.strip().upper().startswith('INSERT'):
        if 'RETURNING' not in sql.upper():
            sql = sql.rstrip().rstrip(';') + ' RETURNING id'
        cur.execute(sql, params)
        row = cur.fetchone()
        # psycopg3 dict_row 返回字典，用 ['id']；兼容元组情况
        new_id = row['id'] if isinstance(row, dict) else row[0]
    else:
        cur.execute(sql, params)
        new_id = cur.lastrowid
    conn.commit()
    conn.close()
    return new_id
