-- ============================================================
-- 行为分级功能数据库迁移脚本
-- 为actions表添加parent_id字段，支持2-3级行为分级
-- ============================================================

-- 1. 添加parent_id字段
ALTER TABLE actions ADD COLUMN IF NOT EXISTS parent_id INTEGER REFERENCES actions(id) ON DELETE SET NULL;

-- 2. 删除原来的name UNIQUE约束（如果存在）
-- 注意：PostgreSQL中UNIQUE约束会自动创建索引，需要先删除约束
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'actions_name_key'
        AND conrelid = 'actions'::regclass
    ) THEN
        ALTER TABLE actions DROP CONSTRAINT actions_name_key;
    END IF;
END $$;

-- 3. 添加新的联合唯一约束：同一父行为下子行为名称唯一
-- 注意：对于一级行为（parent_id为NULL），PostgreSQL的UNIQUE约束不会将NULL视为相等，
-- 所以多个一级行为可以有相同名称。如果需要一级行为名称也唯一，需要使用部分索引。
CREATE UNIQUE INDEX IF NOT EXISTS actions_name_parent_id_unique
    ON actions (name, parent_id)
    WHERE parent_id IS NOT NULL;

-- 对于一级行为（parent_id为NULL），保持名称唯一
CREATE UNIQUE INDEX IF NOT EXISTS actions_name_root_unique
    ON actions (name)
    WHERE parent_id IS NULL;

-- 4. 添加注释
COMMENT ON COLUMN actions.parent_id IS '父行为ID，NULL表示一级行为';

-- ============================================================
-- 迁移完成
-- 现有行为全部为一级行为（parent_id为NULL），无需数据迁移
-- ============================================================
