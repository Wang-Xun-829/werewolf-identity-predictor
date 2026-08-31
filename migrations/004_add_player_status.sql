-- 迁移脚本：增加玩家状态字段
-- 用于支持投票规则：上警玩家不能投警徽票，死亡玩家不能投票等

-- 1. 增加game_players表的状态字段
ALTER TABLE game_players ADD COLUMN IF NOT EXISTS is_on_police BOOLEAN DEFAULT FALSE;      -- 是否上警
ALTER TABLE game_players ADD COLUMN IF NOT EXISTS is_retired BOOLEAN DEFAULT FALSE;         -- 是否退水（上警后退水）
ALTER TABLE game_players ADD COLUMN IF NOT EXISTS is_alive BOOLEAN DEFAULT TRUE;            -- 是否存活
ALTER TABLE game_players ADD COLUMN IF NOT EXISTS death_type VARCHAR(20);                    -- 死亡类型：night_death/day_vote

-- 2. 为现有数据设置默认值
UPDATE game_players SET is_on_police = FALSE WHERE is_on_police IS NULL;
UPDATE game_players SET is_retired = FALSE WHERE is_retired IS NULL;
UPDATE game_players SET is_alive = TRUE WHERE is_alive IS NULL;

-- 3. 增加注释
COMMENT ON COLUMN game_players.is_on_police IS '是否上警';
COMMENT ON COLUMN game_players.is_retired IS '是否退水（上警后退水）';
COMMENT ON COLUMN game_players.is_alive IS '是否存活';
COMMENT ON COLUMN game_players.death_type IS '死亡类型：night_death（夜间死亡）/day_vote（白天放逐）';
