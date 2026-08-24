-- ============================================================
-- 狼人杀身份预测程序 - 数据库表结构
-- 适用于 PostgreSQL (Neon)
-- 本地开发使用 SQLite，由 db.py 自动转换语法
-- ============================================================

-- 1. 身份库（可增删改）
CREATE TABLE IF NOT EXISTS roles (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(50) NOT NULL UNIQUE,   -- 身份名称：预言家、女巫、狼人...
    camp        VARCHAR(20) NOT NULL,           -- 阵营：好人、狼人、第三方
    description TEXT,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 行为库（可增删改，支持2-3级分级）
CREATE TABLE IF NOT EXISTS actions (
    id             SERIAL PRIMARY KEY,
    name           VARCHAR(50) NOT NULL,           -- 行为名称：跳预言家、查杀、发金水...
    description    TEXT,
    default_weight REAL DEFAULT 1.0,              -- 默认权重（贝叶斯先验）
    parent_id      INTEGER REFERENCES actions(id) ON DELETE SET NULL,  -- 父行为ID（NULL表示一级行为）
    is_active      BOOLEAN DEFAULT TRUE,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, parent_id)                        -- 同一父行为下子行为名称唯一
);

-- 3. 版型库（可增删改）
CREATE TABLE IF NOT EXISTS setups (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(50) NOT NULL UNIQUE,   -- 版型名称：预女猎白、狼王守卫...
    role_config TEXT NOT NULL,                  -- JSON格式身份配置：{"狼人":4,"预言家":1,...}
    description TEXT,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. 玩家表
CREATE TABLE IF NOT EXISTS players (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(100) NOT NULL UNIQUE,   -- 玩家昵称/标识（唯一，避免重名混淆）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. 对局表
CREATE TABLE IF NOT EXISTS games (
    id            SERIAL PRIMARY KEY,
    game_code     VARCHAR(50) NOT NULL,          -- 对局编号（用户自定义）
    setup_id      INTEGER REFERENCES setups(id), -- 版型
    player_count  INTEGER,                        -- 玩家数
    status        VARCHAR(20) DEFAULT '进行中',  -- 进行中 / 已结束 / 已确认
    notes         TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at   TIMESTAMP,
    confirmed_at  TIMESTAMP
);

-- 6. 对局玩家表（每局有哪些玩家、座位、最终真实身份）
CREATE TABLE IF NOT EXISTS game_players (
    id             SERIAL PRIMARY KEY,
    game_id        INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    player_id      INTEGER NOT NULL REFERENCES players(id),
    seat_number    INTEGER,                       -- 座位号
    actual_role_id INTEGER REFERENCES roles(id),  -- 真实身份（对局结束后补全）
    UNIQUE(game_id, player_id)
);

-- 7. 行为记录表（核心表 - 用户录入的观察行为）
-- 对应需求中的6个字段：
--   (1) 行为发起者id  -> actor_id      [必填]
--   (2) 行为目标对象id -> target_id     [可空]
--   (3) 具体行为       -> action_id     [必填]
--   (4) 行为发起者阵营 -> actor_camp    [可空]
--   (5) 行为发起者身份 -> actor_role_id [可空]
--   (6) 对局编号       -> game_id       [必填]
CREATE TABLE IF NOT EXISTS behavior_records (
    id            SERIAL PRIMARY KEY,
    game_id       INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    actor_id      INTEGER NOT NULL REFERENCES players(id),   -- (1) 行为发起者 [必填]
    target_id     INTEGER REFERENCES players(id),             -- (2) 行为目标 [可空]
    action_id     INTEGER NOT NULL REFERENCES actions(id),    -- (3) 具体行为 [必填]
    actor_role_id INTEGER REFERENCES roles(id),                -- (5) 发起者声明身份 [可空]
    actor_camp    VARCHAR(20),                                 -- (4) 发起者声明阵营 [可空]
    round_number  INTEGER,                                     -- 轮次（第几天）[可空]
    phase         VARCHAR(20),                                 -- 阶段：白天发言/投票/黑夜 [可空]
    notes         TEXT,                                        -- 备注 [可空]
    is_verified   BOOLEAN DEFAULT FALSE,                      -- 对局结束后确认是否准确
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. 预测结果表（系统实时预测各玩家身份概率）
CREATE TABLE IF NOT EXISTS predictions (
    id            SERIAL PRIMARY KEY,
    game_id       INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    player_id     INTEGER NOT NULL REFERENCES players(id),
    role_id       INTEGER NOT NULL REFERENCES roles(id),
    probability   REAL NOT NULL,                               -- 概率值 0~1
    predicted_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model_version VARCHAR(20) DEFAULT 'v1'
);

-- 9. 算法权重表（贝叶斯参数 - 用于自我优化）
-- 记录"某身份下出现某行为"的概率倾向，系统根据历史数据自动更新
CREATE TABLE IF NOT EXISTS algorithm_weights (
    id           SERIAL PRIMARY KEY,
    action_id    INTEGER NOT NULL REFERENCES actions(id),
    role_id      INTEGER NOT NULL REFERENCES roles(id),
    weight       REAL DEFAULT 1.0,                             -- 权重系数
    sample_count INTEGER DEFAULT 0,                             -- 样本数（用于加权更新）
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(action_id, role_id)
);

-- 10. 预测打分表（每局结束后对比预测与真实）
CREATE TABLE IF NOT EXISTS prediction_scores (
    id                 SERIAL PRIMARY KEY,
    game_id            INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    player_id          INTEGER NOT NULL REFERENCES players(id),
    predicted_role_id  INTEGER REFERENCES roles(id),           -- 预测的身份（最高概率）
    actual_role_id     INTEGER REFERENCES roles(id),           -- 真实身份
    is_correct         BOOLEAN,                                 -- 是否预测正确
    confidence         REAL,                                    -- 预测时的置信度
    scored_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 11. 玩家个性化行为统计表（持久化存储，用于个性化似然度）
-- 记录每个玩家拿每个身份时，各行为的出现次数和总局数
CREATE TABLE IF NOT EXISTS player_behavior_stats (
    id          SERIAL PRIMARY KEY,
    player_id   INTEGER NOT NULL REFERENCES players(id) ON DELETE CASCADE,
    role_id     INTEGER NOT NULL REFERENCES roles(id),
    action_id   INTEGER NOT NULL REFERENCES actions(id),
    count       INTEGER DEFAULT 0,   -- 该玩家拿该身份时做该行为的次数
    game_count  INTEGER DEFAULT 0,   -- 该玩家拿该身份的总局数（同一玩家同一身份只存一份）
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, role_id, action_id)
);

-- 12. 机器学习模型表（存储训练好的逻辑回归/决策树模型）
CREATE TABLE IF NOT EXISTS ml_models (
    id           SERIAL PRIMARY KEY,
    model_type   VARCHAR(50) NOT NULL,    -- logistic_regression / decision_tree
    target_class VARCHAR(50) NOT NULL,    -- 目标类别：好人/狼人/具体身份名
    model_data   TEXT NOT NULL,            -- 模型参数（JSON格式）
    sample_count INTEGER DEFAULT 0,        -- 训练样本数
    accuracy     REAL DEFAULT 0,           -- 训练集准确率
    trained_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 13. 对局假设情景表（多情景推理）
-- 用于存储用户创建的假设情景，如"假设A是预言家"
CREATE TABLE IF NOT EXISTS game_scenarios (
    id          SERIAL PRIMARY KEY,
    game_id     INTEGER NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    name        VARCHAR(100) NOT NULL,     -- 情景名称：假设A是预言家、假设B是预言家
    description TEXT,                        -- 情景描述
    is_active   BOOLEAN DEFAULT TRUE,       -- 是否启用
    sort_order  INTEGER DEFAULT 0,          -- 排序
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 14. 情景假设身份分配表
-- 存储每个情景中，用户假设某些玩家的身份或阵营
CREATE TABLE IF NOT EXISTS scenario_assignments (
    id            SERIAL PRIMARY KEY,
    scenario_id   INTEGER NOT NULL REFERENCES game_scenarios(id) ON DELETE CASCADE,
    player_id     INTEGER NOT NULL REFERENCES players(id),
    role_id       INTEGER REFERENCES roles(id),        -- 假设的具体身份（可空，与camp二选一）
    camp          VARCHAR(20),                          -- 假设的阵营（好人/狼人，可空，与role_id二选一）
    confidence    REAL DEFAULT 0.9,                     -- 置信度 0~1（0.9表示90%确定）
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(scenario_id, player_id)                      -- 同一情景下同一玩家只能有一个假设
);

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

-- ============================================================
-- 索引（提升查询性能）
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_behavior_game    ON behavior_records(game_id);
CREATE INDEX IF NOT EXISTS idx_behavior_actor   ON behavior_records(actor_id);
CREATE INDEX IF NOT EXISTS idx_behavior_action  ON behavior_records(action_id);
CREATE INDEX IF NOT EXISTS idx_predictions_game ON predictions(game_id);
CREATE INDEX IF NOT EXISTS idx_game_players_game ON game_players(game_id);
CREATE INDEX IF NOT EXISTS idx_scores_game      ON prediction_scores(game_id);
CREATE INDEX IF NOT EXISTS idx_relationships_game   ON player_relationships(game_id);
CREATE INDEX IF NOT EXISTS idx_relationships_source ON player_relationships(source_player_id);
CREATE INDEX IF NOT EXISTS idx_relationships_target ON player_relationships(target_player_id);
