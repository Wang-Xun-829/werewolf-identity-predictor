"""
查看行为库中的行为
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

os.environ['DATABASE_URL'] = "postgresql://neondb_owner:npg_u1rFnCVX7NTx@ep-restless-feather-azyo5mej-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

from db import query_all

actions = query_all("SELECT id, name, default_weight, parent_id FROM actions ORDER BY parent_id NULLS FIRST, name")

print("行为库中的行为:")
print(f"{'ID':<5} {'名称':<20} {'默认权重':<10} {'父行为ID':<10}")
print("-" * 50)
for a in actions:
    parent_id = a.get('parent_id')
    parent_str = str(parent_id) if parent_id else '无'
    print(f"{a['id']:<5} {a['name']:<20} {a.get('default_weight', 1.0):<10} {parent_str:<10}")
