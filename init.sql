-- ============================================================
-- 狼人杀身份预测程序 - 完整初始化脚本
-- 适用于 PostgreSQL (Neon)
-- ============================================================

-- ========== 建表 ==========
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

-- 2. 行为库（可增删改）
CREATE TABLE IF NOT EXISTS actions (
    id             SERIAL PRIMARY KEY,
    name           VARCHAR(50) NOT NULL UNIQUE,  -- 行为名称：跳预言家、查杀、发金水...
    description    TEXT,
    default_weight REAL DEFAULT 1.0,              -- 默认权重（贝叶斯先验）
    is_active      BOOLEAN DEFAULT TRUE,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    name       VARCHAR(100) NOT NULL,           -- 玩家昵称/标识
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

-- ============================================================
-- 索引（提升查询性能）
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_behavior_game    ON behavior_records(game_id);
CREATE INDEX IF NOT EXISTS idx_behavior_actor   ON behavior_records(actor_id);
CREATE INDEX IF NOT EXISTS idx_behavior_action  ON behavior_records(action_id);
CREATE INDEX IF NOT EXISTS idx_predictions_game ON predictions(game_id);
CREATE INDEX IF NOT EXISTS idx_game_players_game ON game_players(game_id);
CREATE INDEX IF NOT EXISTS idx_scores_game      ON prediction_scores(game_id);


-- ========== 初始身份数据 ==========
INSERT INTO roles (id, name, camp, description) VALUES (1, '预言家', '好人', '每晚可查验一名玩家身份');
INSERT INTO roles (id, name, camp, description) VALUES (2, '女巫', '好人', '拥有一瓶解药和一瓶毒药');
INSERT INTO roles (id, name, camp, description) VALUES (3, '猎人', '好人', '被淘汰时可开枪带走一人');
INSERT INTO roles (id, name, camp, description) VALUES (4, '白痴', '好人', '被投票出局时可翻牌免死');
INSERT INTO roles (id, name, camp, description) VALUES (5, '守卫', '好人', '每晚可守护一人免受狼人杀害');
INSERT INTO roles (id, name, camp, description) VALUES (6, '平民', '好人', '无特殊技能，靠推理投票');
INSERT INTO roles (id, name, camp, description) VALUES (7, '狼人', '狼人', '每晚可杀害一人');
INSERT INTO roles (id, name, camp, description) VALUES (8, '狼王', '狼人', '被淘汰时可开枪带走一人');
INSERT INTO roles (id, name, camp, description) VALUES (9, '白狼王', '狼人', '白天可自爆带走一人');
INSERT INTO roles (id, name, camp, description) VALUES (10, '丘比特', '第三方', '可连接两名玩家成为情侣');
INSERT INTO roles (id, name, camp, description) VALUES (11, '盗贼', '第三方', '开局可从两张额外身份牌中选择');

-- ========== 初始行为数据 ==========
INSERT INTO actions (id, name, description, default_weight) VALUES (1, '跳预言家', '声称自己是预言家', 2.0);
INSERT INTO actions (id, name, description, default_weight) VALUES (2, '查杀', '预言家查验某人为狼人', 3.0);
INSERT INTO actions (id, name, description, default_weight) VALUES (3, '发金水', '预言家查验某人为好人', 2.5);
INSERT INTO actions (id, name, description, default_weight) VALUES (4, '跳女巫', '声称自己是女巫', 2.0);
INSERT INTO actions (id, name, description, default_weight) VALUES (5, '跳猎人', '声称自己是猎人', 1.5);
INSERT INTO actions (id, name, description, default_weight) VALUES (6, '跳守卫', '声称自己是守卫', 1.5);
INSERT INTO actions (id, name, description, default_weight) VALUES (7, '认平民', '声称自己是平民', 1.0);
INSERT INTO actions (id, name, description, default_weight) VALUES (8, '投票', '投票放逐某玩家', 1.0);
INSERT INTO actions (id, name, description, default_weight) VALUES (9, '弃票', '投票阶段弃票', 0.8);
INSERT INTO actions (id, name, description, default_weight) VALUES (10, '站边', '表示支持某名预言家', 1.2);
INSERT INTO actions (id, name, description, default_weight) VALUES (11, '倒钩', '狼人假装好人站边真预言家', 1.5);
INSERT INTO actions (id, name, description, default_weight) VALUES (12, '冲锋', '狼人积极为狼队友号票', 1.5);
INSERT INTO actions (id, name, description, default_weight) VALUES (13, '自爆', '狼人白天自爆身份', 5.0);
INSERT INTO actions (id, name, description, default_weight) VALUES (14, '开枪', '猎人/狼王被淘汰时开枪带人', 3.0);
INSERT INTO actions (id, name, description, default_weight) VALUES (15, '使用解药', '女巫使用解药救人', 2.5);
INSERT INTO actions (id, name, description, default_weight) VALUES (16, '使用毒药', '女巫使用毒药毒人', 2.5);
INSERT INTO actions (id, name, description, default_weight) VALUES (17, '守护', '守卫守护某玩家', 2.0);
INSERT INTO actions (id, name, description, default_weight) VALUES (18, '质疑', '质疑某玩家身份', 1.0);
INSERT INTO actions (id, name, description, default_weight) VALUES (19, '划水', '发言无营养、回避分析', 0.8);

-- ========== 初始版型数据 ==========
INSERT INTO setups (id, name, role_config, description) VALUES (1, '预女猎白', '{"狼人":4,"预言家":1,"女巫":1,"猎人":1,"白痴":1,"平民":4}', '12人标准局');
INSERT INTO setups (id, name, role_config, description) VALUES (2, '预女猎守', '{"狼人":4,"预言家":1,"女巫":1,"猎人":1,"守卫":1,"平民":4}', '12人守卫局');
INSERT INTO setups (id, name, role_config, description) VALUES (3, '狼王守卫', '{"狼人":3,"狼王":1,"预言家":1,"女巫":1,"猎人":1,"守卫":1,"平民":4}', '12人狼王守卫局');
INSERT INTO setups (id, name, role_config, description) VALUES (4, '白狼王守卫', '{"狼人":3,"白狼王":1,"预言家":1,"女巫":1,"猎人":1,"守卫":1,"平民":4}', '12人白狼王守卫局');
INSERT INTO setups (id, name, role_config, description) VALUES (5, '9人预女猎', '{"狼人":3,"预言家":1,"女巫":1,"猎人":1,"平民":3}', '9人标准局');

-- ========== 初始算法权重数据（行为×身份的语义关联） ==========
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (1, 1, 1, 6.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (2, 1, 2, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (3, 1, 3, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (4, 1, 4, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (5, 1, 5, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (6, 1, 6, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (7, 1, 7, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (8, 1, 8, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (9, 1, 9, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (10, 1, 10, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (11, 1, 11, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (12, 2, 1, 9.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (13, 2, 2, 0.8999999999999999, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (14, 2, 3, 0.8999999999999999, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (15, 2, 4, 0.8999999999999999, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (16, 2, 5, 0.8999999999999999, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (17, 2, 6, 0.8999999999999999, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (18, 2, 7, 4.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (19, 2, 8, 4.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (20, 2, 9, 4.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (21, 2, 10, 0.8999999999999999, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (22, 2, 11, 0.8999999999999999, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (23, 3, 1, 7.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (24, 3, 2, 0.75, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (25, 3, 3, 0.75, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (26, 3, 4, 0.75, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (27, 3, 5, 0.75, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (28, 3, 6, 0.75, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (29, 3, 7, 3.75, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (30, 3, 8, 3.75, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (31, 3, 9, 3.75, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (32, 3, 10, 0.75, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (33, 3, 11, 0.75, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (34, 4, 1, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (35, 4, 2, 6.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (36, 4, 3, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (37, 4, 4, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (38, 4, 5, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (39, 4, 6, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (40, 4, 7, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (41, 4, 8, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (42, 4, 9, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (43, 4, 10, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (44, 4, 11, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (45, 5, 1, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (46, 5, 2, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (47, 5, 3, 4.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (48, 5, 4, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (49, 5, 5, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (50, 5, 6, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (51, 5, 7, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (52, 5, 8, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (53, 5, 9, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (54, 5, 10, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (55, 5, 11, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (56, 6, 1, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (57, 6, 2, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (58, 6, 3, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (59, 6, 4, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (60, 6, 5, 4.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (61, 6, 6, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (62, 6, 7, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (63, 6, 8, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (64, 6, 9, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (65, 6, 10, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (66, 6, 11, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (67, 7, 1, 0.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (68, 7, 2, 0.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (69, 7, 3, 0.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (70, 7, 4, 0.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (71, 7, 5, 0.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (72, 7, 6, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (73, 7, 7, 0.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (74, 7, 8, 0.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (75, 7, 9, 0.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (76, 7, 10, 0.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (77, 7, 11, 0.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (78, 8, 1, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (79, 8, 2, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (80, 8, 3, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (81, 8, 4, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (82, 8, 5, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (83, 8, 6, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (84, 8, 7, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (85, 8, 8, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (86, 8, 9, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (87, 8, 10, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (88, 8, 11, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (89, 9, 1, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (90, 9, 2, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (91, 9, 3, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (92, 9, 4, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (93, 9, 5, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (94, 9, 6, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (95, 9, 7, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (96, 9, 8, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (97, 9, 9, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (98, 9, 10, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (99, 9, 11, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (100, 10, 1, 1.2, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (101, 10, 2, 1.2, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (102, 10, 3, 1.2, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (103, 10, 4, 1.2, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (104, 10, 5, 1.2, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (105, 10, 6, 1.2, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (106, 10, 7, 1.2, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (107, 10, 8, 1.2, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (108, 10, 9, 1.2, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (109, 10, 10, 1.2, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (110, 10, 11, 1.2, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (111, 11, 1, 0.44999999999999996, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (112, 11, 2, 0.44999999999999996, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (113, 11, 3, 0.44999999999999996, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (114, 11, 4, 0.44999999999999996, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (115, 11, 5, 0.44999999999999996, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (116, 11, 6, 0.44999999999999996, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (117, 11, 7, 4.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (118, 11, 8, 4.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (119, 11, 9, 4.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (120, 11, 10, 0.44999999999999996, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (121, 11, 11, 0.44999999999999996, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (122, 12, 1, 0.44999999999999996, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (123, 12, 2, 0.44999999999999996, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (124, 12, 3, 0.44999999999999996, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (125, 12, 4, 0.44999999999999996, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (126, 12, 5, 0.44999999999999996, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (127, 12, 6, 0.44999999999999996, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (128, 12, 7, 4.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (129, 12, 8, 4.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (130, 12, 9, 4.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (131, 12, 10, 0.44999999999999996, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (132, 12, 11, 0.44999999999999996, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (133, 13, 1, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (134, 13, 2, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (135, 13, 3, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (136, 13, 4, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (137, 13, 5, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (138, 13, 6, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (139, 13, 7, 15.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (140, 13, 8, 15.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (141, 13, 9, 15.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (142, 13, 10, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (143, 13, 11, 1.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (144, 14, 1, 3.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (145, 14, 2, 3.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (146, 14, 3, 9.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (147, 14, 4, 3.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (148, 14, 5, 3.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (149, 14, 6, 3.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (150, 14, 7, 3.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (151, 14, 8, 9.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (152, 14, 9, 3.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (153, 14, 10, 3.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (154, 14, 11, 3.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (155, 15, 1, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (156, 15, 2, 7.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (157, 15, 3, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (158, 15, 4, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (159, 15, 5, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (160, 15, 6, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (161, 15, 7, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (162, 15, 8, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (163, 15, 9, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (164, 15, 10, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (165, 15, 11, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (166, 16, 1, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (167, 16, 2, 7.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (168, 16, 3, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (169, 16, 4, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (170, 16, 5, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (171, 16, 6, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (172, 16, 7, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (173, 16, 8, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (174, 16, 9, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (175, 16, 10, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (176, 16, 11, 2.5, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (177, 17, 1, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (178, 17, 2, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (179, 17, 3, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (180, 17, 4, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (181, 17, 5, 6.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (182, 17, 6, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (183, 17, 7, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (184, 17, 8, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (185, 17, 9, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (186, 17, 10, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (187, 17, 11, 2.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (188, 18, 1, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (189, 18, 2, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (190, 18, 3, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (191, 18, 4, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (192, 18, 5, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (193, 18, 6, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (194, 18, 7, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (195, 18, 8, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (196, 18, 9, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (197, 18, 10, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (198, 18, 11, 1.0, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (199, 19, 1, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (200, 19, 2, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (201, 19, 3, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (202, 19, 4, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (203, 19, 5, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (204, 19, 6, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (205, 19, 7, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (206, 19, 8, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (207, 19, 9, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (208, 19, 10, 0.8, 0);
INSERT INTO algorithm_weights (id, action_id, role_id, weight, sample_count) VALUES (209, 19, 11, 0.8, 0);

-- ========== 修复自增序列 ==========
SELECT setval('roles_id_seq', (SELECT MAX(id) FROM roles));
SELECT setval('actions_id_seq', (SELECT MAX(id) FROM actions));
SELECT setval('setups_id_seq', (SELECT MAX(id) FROM setups));
SELECT setval('algorithm_weights_id_seq', (SELECT MAX(id) FROM algorithm_weights));

-- ========== 初始化完成 ==========