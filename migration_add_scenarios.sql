-- ============================================================
-- 多情景假设推理 - 数据库迁移脚本
-- 执行此脚本为线上数据库添加情景相关表
-- ============================================================

-- 13. 对局假设情景表
CREATE TABLE IF NOT EXISTS game_scenarios (
    id          SERIAL PRIMARY KEY,
    game_id     INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL,
    description TEXT,
    is_active   BOOLEAN DEFAULT TRUE,
    sort_order  INTEGER DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 14. 情景假设身份分配表
CREATE TABLE IF NOT EXISTS scenario_assignments (
    id            SERIAL PRIMARY KEY,
    scenario_id   INTEGER NOT NULL REFERENCES game_scenarios(id) ON DELETE CASCADE,
    player_id     INTEGER NOT NULL REFERENCES players(id),
    role_id       INTEGER REFERENCES roles(id),
    camp          VARCHAR(20),
    confidence    REAL DEFAULT 0.9,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(scenario_id, player_id)
);

-- 添加索引
CREATE INDEX IF NOT EXISTS idx_scenarios_game_id ON game_scenarios(game_id);
CREATE INDEX IF NOT EXISTS idx_assignments_scenario_id ON scenario_assignments(scenario_id);

-- 验证
SELECT '迁移完成，已添加 game_scenarios 和 scenario_assignments 表' as result;
