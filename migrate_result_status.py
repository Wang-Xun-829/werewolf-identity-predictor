"""
数据库迁移脚本：为behavior_records表添加result_status字段

result_status字段用于存储行为结果状态：
- unknown: 未知（默认）
- correct: 正确（投对/保对/踩对/站对）
- incorrect: 错误（投错/保错/踩错/站错）

同时，将现有的独立结果状态行为（投对/投错、保对/保错等）
迁移为基础行为的结果状态。

使用方法：
  在线上运行：设置DATABASE_URL环境变量后运行
  python migrate_result_status.py
"""

import sys
import os

# 把当前目录加入路径
sys.path.insert(0, os.path.dirname(__file__))

from db import query_all, query_one, execute_write, ph, DB_TYPE


def migrate():
    print("=" * 60)
    print("开始数据库迁移：添加result_status字段")
    print(f"数据库类型: {DB_TYPE}")
    print("=" * 60)

    # 1. 检查result_status字段是否已存在
    print("\n[1/5] 检查result_status字段是否已存在...")
    try:
        # 尝试查询，如果字段不存在会报错
        query_one("SELECT result_status FROM behavior_records LIMIT 1")
        print("  result_status字段已存在，跳过添加")
        field_exists = True
    except Exception as e:
        print(f"  result_status字段不存在，开始添加... (错误: {e})")
        # 添加result_status字段
        if DB_TYPE == "postgresql":
            execute_write(
                "ALTER TABLE behavior_records ADD COLUMN result_status VARCHAR(20) DEFAULT 'unknown'"
            )
        else:
            execute_write(
                "ALTER TABLE behavior_records ADD COLUMN result_status TEXT DEFAULT 'unknown'"
            )
        print("  result_status字段添加成功")
        field_exists = False

    # 2. 为result_status字段创建索引
    print("\n[2/5] 为result_status字段创建索引...")
    try:
        execute_write(
            "CREATE INDEX IF NOT EXISTS idx_behavior_result_status ON behavior_records(result_status)"
        )
        print("  索引创建成功")
    except Exception as e:
        print(f"  索引创建失败（可能已存在）: {e}")

    # 3. 查找现有的独立结果状态行为
    print("\n[3/5] 查找现有的独立结果状态行为...")
    # 可能的结果状态行为名称（支持多种命名）
    result_action_patterns = [
        '%投对%', '%投错%',
        '%保对%', '%保错%',
        '%踩对%', '%踩错%',
        '%站对%', '%站错%',
    ]

    result_actions = []
    seen_ids = set()
    for pattern in result_action_patterns:
        actions = query_all(
            "SELECT * FROM actions WHERE name LIKE " + ph() + " AND is_active = TRUE",
            (pattern,)
        )
        for action in actions:
            if action['id'] not in seen_ids:
                result_actions.append(action)
                seen_ids.add(action['id'])
                print(f"  找到行为: {action['name']} (ID: {action['id']})")

    if not result_actions:
        print("  未找到独立结果状态行为")

    # 4. 迁移现有的行为记录：将独立结果状态行为迁移为基础行为的结果状态
    print("\n[4/5] 迁移现有的行为记录...")

    # 定义映射关系：结果状态行为名关键词 -> (基础行为名关键词, 结果状态)
    # 我们会根据行为名称智能匹配
    def get_migration_info(action_name):
        """根据行为名称获取迁移信息"""
        name = action_name

        # 投票相关
        if '投对' in name and '警徽' in name:
            return ('投警徽票', 'correct')
        if '投错' in name and '警徽' in name:
            return ('投警徽票', 'incorrect')
        if '投对' in name and '放逐' in name:
            return ('投放逐票', 'correct')
        if '投错' in name and '放逐' in name:
            return ('投放逐票', 'incorrect')

        # 保人相关
        if '保对' in name:
            return ('保人', 'correct')
        if '保错' in name:
            return ('保人', 'incorrect')

        # 踩人相关
        if '踩对' in name:
            return ('踩人', 'correct')
        if '踩错' in name:
            return ('踩人', 'incorrect')

        # 站边相关
        if '站对' in name:
            return ('站边', 'correct')
        if '站错' in name:
            return ('站边', 'incorrect')

        return None

    migrated_count = 0
    for result_action in result_actions:
        result_name = result_action['name']
        migration_info = get_migration_info(result_name)

        if not migration_info:
            print(f"  警告: 无法确定行为 '{result_name}' 的迁移信息，跳过")
            continue

        base_name, result_status = migration_info

        # 查找基础行为（模糊匹配）
        base_action = query_one(
            "SELECT * FROM actions WHERE name LIKE " + ph() + " AND is_active = TRUE LIMIT 1",
            (f'%{base_name}%',)
        )

        if not base_action:
            # 如果找不到，尝试查找父行为
            base_action = query_one(
                "SELECT * FROM actions WHERE name = " + ph(),
                (base_name,)
            )

        if not base_action:
            print(f"  警告: 未找到基础行为 '{base_name}'，跳过迁移")
            continue

        # 查找使用该结果状态行为的记录
        records = query_all(
            "SELECT * FROM behavior_records WHERE action_id = " + ph(),
            (result_action['id'],)
        )

        if records:
            print(f"  迁移行为 '{result_name}' -> '{base_action['name']}' ({result_status})，共 {len(records)} 条记录")
            for record in records:
                # 更新行为记录：将action_id改为基础行为，设置result_status
                execute_write(
                    f"""UPDATE behavior_records
                        SET action_id = {ph()}, result_status = {ph()}
                        WHERE id = {ph()}""",
                    (base_action['id'], result_status, record['id'])
                )
                migrated_count += 1
        else:
            print(f"  行为 '{result_name}' 没有使用记录，直接禁用")

    print(f"  共迁移 {migrated_count} 条行为记录")

    # 5. 禁用（不删除）独立结果状态行为
    print("\n[5/5] 禁用独立结果状态行为（设置is_active=FALSE）...")
    disabled_count = 0
    for result_action in result_actions:
        execute_write(
            f"UPDATE actions SET is_active = FALSE WHERE id = {ph()}",
            (result_action['id'],)
        )
        disabled_count += 1
        print(f"  已禁用行为: {result_action['name']} (ID: {result_action['id']})")

    print(f"  共禁用 {disabled_count} 个行为")

    print("\n" + "=" * 60)
    print("数据库迁移完成！")
    print("=" * 60)
    print(f"\n迁移摘要:")
    print(f"  - 添加result_status字段: {'已存在' if field_exists else '新添加'}")
    print(f"  - 创建索引: 完成")
    print(f"  - 迁移行为记录: {migrated_count} 条")
    print(f"  - 禁用独立结果状态行为: {disabled_count} 个")
    print(f"\n注意: 独立结果状态行为只是被禁用（is_active=FALSE），没有被删除，")
    print(f"      如果需要可以重新启用。确认迁移成功后可以手动删除。")


if __name__ == "__main__":
    migrate()
