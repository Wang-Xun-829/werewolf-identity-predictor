-- ============================================================
-- 数据库升级脚本 - 行为语义属性 + 逻辑推理引擎
-- 适用于 PostgreSQL (Neon) 和 SQLite
-- ============================================================

-- 1. 行为库增加语义属性字段
ALTER TABLE actions ADD COLUMN IF NOT EXISTS action_type VARCHAR(30) DEFAULT 'other';
-- 行为类型：identity_confirm(身份确认), identity_claim(身份声明), 
-- identity_conflict(身份冲突), check_result(查验结果), 
-- stance_expression(立场表达), vote_action(投票行为), 
-- event(事件), other(其他)

ALTER TABLE actions ADD COLUMN IF NOT EXISTS certainty VARCHAR(20) DEFAULT 'probabilistic';
-- 确定性：absolute(100%确定), probabilistic(概率性), conditional(条件性)

ALTER TABLE actions ADD COLUMN IF NOT EXISTS determine_content VARCHAR(100);
-- 确定内容：actor_werewolf(发起者=狼人), actor_good(发起者=好人),
-- target_good(目标=好人), target_werewolf(目标=狼人),
-- at_least_one_werewolf(两人中至少一个狼), etc.

ALTER TABLE actions ADD COLUMN IF NOT EXISTS trigger_condition VARCHAR(100);
-- 触发条件：if_actor_is_prophet(如果发起者是真预言家), etc.

ALTER TABLE actions ADD COLUMN IF NOT EXISTS has_result_status BOOLEAN DEFAULT FALSE;
-- 是否有结果状态（保人/踩人/站边/投票等行为有正确/错误子状态）

-- 2. 行为记录增加结果状态字段
ALTER TABLE behavior_records ADD COLUMN IF NOT EXISTS result_status VARCHAR(20) DEFAULT 'unconfirmed';
-- 结果状态：unconfirmed(未确认), correct(正确), wrong(错误)

ALTER TABLE behavior_records ADD COLUMN IF NOT EXISTS derived_from INTEGER;
-- 推导来源：记录是从哪条确认身份推导出来的（game_confirmed_identities.id）

-- 3. 为现有行为设置语义属性（根据名称智能识别）
-- 身份确认类：自爆、开枪
UPDATE actions SET action_type = 'identity_confirm', certainty = 'absolute', determine_content = 'actor_werewolf' 
WHERE name LIKE '%自爆%';

UPDATE actions SET action_type = 'identity_confirm', certainty = 'absolute', determine_content = 'actor_hunter_or_wolf_king' 
WHERE name LIKE '%开枪%';

-- 身份声明类：跳XX
UPDATE actions SET action_type = 'identity_claim', certainty = 'probabilistic' 
WHERE name LIKE '跳%' AND name NOT LIKE '%对跳%';

-- 身份冲突类：对跳XX
UPDATE actions SET action_type = 'identity_conflict', certainty = 'probabilistic', determine_content = 'at_least_one_werewolf' 
WHERE name LIKE '%对跳%';

-- 查验结果类：金水、查杀
UPDATE actions SET action_type = 'check_result', certainty = 'conditional', trigger_condition = 'if_actor_is_prophet' 
WHERE name LIKE '%金水%' OR name LIKE '%查杀%';

UPDATE actions SET determine_content = 'target_good' WHERE name LIKE '%金水%';
UPDATE actions SET determine_content = 'target_werewolf' WHERE name LIKE '%查杀%';

-- 立场表达类：保人、踩人、站边
UPDATE actions SET action_type = 'stance_expression', certainty = 'probabilistic', has_result_status = TRUE 
WHERE name LIKE '%保%' OR name LIKE '%踩%' OR name LIKE '%站边%' OR name LIKE '%晃边%' OR name LIKE '%反水%';

-- 投票行为类：投票
UPDATE actions SET action_type = 'vote_action', certainty = 'probabilistic', has_result_status = TRUE 
WHERE name LIKE '%票%';

-- 事件类：死亡、平安夜
UPDATE actions SET action_type = 'event', certainty = 'absolute' 
WHERE name LIKE '%死亡%' OR name LIKE '%死%' OR name LIKE '%平安夜%';

-- 有结果状态的子行为（保对人、保错人、踩对人、踩错人、站对边、站错边等）
UPDATE actions SET has_result_status = TRUE 
WHERE name LIKE '%对%' OR name LIKE '%错%';

-- 4. 创建索引
CREATE INDEX IF NOT EXISTS idx_actions_action_type ON actions(action_type);
CREATE INDEX IF NOT EXISTS idx_behavior_records_result_status ON behavior_records(result_status);
CREATE INDEX IF NOT EXISTS idx_behavior_records_actor_target ON behavior_records(actor_id, target_id);
