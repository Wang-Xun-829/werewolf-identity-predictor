"""测试综合逻辑引擎"""
from database import get_db, init_db
from logic_engine_v2 import ComprehensiveLogicEngine

init_db()
db = next(get_db())

# 测试对局17的综合逻辑分析
engine = ComprehensiveLogicEngine(db, 17)
result = engine.run_full_analysis()

print('=== 综合逻辑分析结果 ===')
print(f'确定性事实: {len(result["determined_facts"])} 条')
for f in result["determined_facts"]:
    print(f'  - {f["description"]}')

print(f'推导事实: {len(result["derived_facts"])} 条')
for f in result["derived_facts"]:
    print(f'  - {f["description"]}')

print(f'逻辑警告: {len(result["warnings"])} 条')
for w in result["warnings"]:
    print(f'  - {w["description"]}')

print(f'矛盾点: {len(result["contradictions"])} 条')
for c in result["contradictions"]:
    print(f'  - {c["description"]}')

print(f'公共狼: {len(result["common_wolves"])} 个')
for w in result["common_wolves"]:
    print(f'  - {w["player_name"]}')

print(f'双边分析: {len(result["bilateral_analysis"])} 个视角')
for p in result["bilateral_analysis"]:
    print(f'  - {p["prophet_name"]}视角: 狼坑{p["wolf_count"]}只 - {p["wolf_pit_names"]}')

print('=== 分析完成 ===')
