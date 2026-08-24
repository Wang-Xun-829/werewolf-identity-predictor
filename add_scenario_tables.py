import sqlite3
conn = sqlite3.connect('werewolf.db')
# 创建game_scenarios表
conn.execute('''
CREATE TABLE IF NOT EXISTS game_scenarios (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id     INTEGER NOT NULL,
    name        VARCHAR(100) NOT NULL,
    description TEXT,
    is_active   INTEGER DEFAULT 1,
    sort_order  INTEGER DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')
# 创建scenario_assignments表
conn.execute('''
CREATE TABLE IF NOT EXISTS scenario_assignments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id   INTEGER NOT NULL,
    player_id     INTEGER NOT NULL,
    role_id       INTEGER NOT NULL,
    confidence    REAL DEFAULT 0.9,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(scenario_id, player_id)
)
''')
conn.commit()
print('两张表创建成功')
# 验证
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%scenario%'")
print('情景相关表:', [row[0] for row in cursor.fetchall()])
conn.close()
