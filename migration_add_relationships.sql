-- ============================================================
-- 第二阶段：玩家关系图与回溯推断 - 数据库迁移脚本
-- 执行此脚本为线上数据库添加玩家关系表
-- ============================================================

-- 15. 玩家关系表
-- 存储对局中玩家之间的关系（踩、保、站边、投票等），用于关系图推理和回溯推断
CREATE TABLE IF NOT EXISTS player_relationships (
    id                SERIAL PRIMARY KEY,
    game_id           INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    source_player_id  INTEGER NOT NULL REFERENCES players(id),   -- 关系发起者（A踩B中的A）
    target_player_id  INTEGER NOT NULL REFERENCES players(id),   -- 关系目标（A踩B中的B）
    relationship_type VARCHAR(30) NOT NULL,                       -- 关系类型：attack(踩)/defend(保)/side(站边)/vote(投票)/check(查杀)/gold(金水)
    strength          REAL DEFAULT 0.5,                           -- 关系强度 0~1（查杀比普通踩更强）
    round_number      INTEGER,                                     -- 发生轮次
    phase             VARCHAR(20),                                 -- 发生阶段
    behavior_id       INTEGER REFERENCES behavior_records(id),    -- 关联的行为记录
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 添加索引
CREATE INDEX IF NOT EXISTS idx_relationships_game   ON player_relationships(game_id);
CREATE INDEX IF NOT EXISTS idx_relationships_source ON player_relationships(source_player_id);
CREATE INDEX IF NOT EXISTS idx_relationships_target ON player_relationships(target_player_id);

-- 验证
SELECT '迁移完成，已添加 player_relationships 表' as result;
