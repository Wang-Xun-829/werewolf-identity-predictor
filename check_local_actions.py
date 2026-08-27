"""
检查本地数据库的actions表
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from db import query_all

print("检查本地数据库的actions表...")
actions = query_all("SELECT id, name, parent_id, is_active FROM actions ORDER BY id")
print(f"总行为数: {len(actions)}")
print("\n行为列表:")
for a in actions:
    parent_str = f" (父行为ID: {a['parent_id']})" if a['parent_id'] else ""
    active_str = "✓" if a['is_active'] else "✗"
    print(f"  [{active_str}] ID: {a['id']}, 名称: {a['name']}{parent_str}")
