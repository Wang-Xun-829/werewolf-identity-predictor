"""
修复行为类型分类名：把英文分类名改成中文
"""
import os
import sys

# 分类映射表（英文小写 → 中文）
CATEGORY_MAP = {
    'identity_claim': '身份声明',
    'stance_expression': '立场表达',
    'identity_conflict': '身份冲突',
    'vote_action': '投票行为',
    'identity_confirm': '身份确认',
    'other': '其他',
    'event': '事件',
    'check_result': '查验结果',
}

def fix_local_db():
    """修复本地SQLite数据库"""
    import sqlite3
    db_path = os.path.join(os.path.dirname(__file__), 'werewolf_v5.db')
    if not os.path.exists(db_path):
        print(f"本地数据库不存在: {db_path}")
        return
    
    print("=" * 60)
    print("修复本地数据库行为类型分类名")
    print("=" * 60)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 查询当前所有分类
    cursor.execute('SELECT DISTINCT category FROM action_types')
    categories = [row[0] for row in cursor.fetchall()]
    print(f"当前分类: {categories}")
    
    # 修改分类名
    total_updated = 0
    for eng, chn in CATEGORY_MAP.items():
        cursor.execute('UPDATE action_types SET category = ? WHERE category = ?', (chn, eng))
        updated = cursor.rowcount
        if updated > 0:
            print(f"  {eng} → {chn}: 更新了 {updated} 条")
            total_updated += updated
    
    conn.commit()
    
    # 查询修改后的分类
    cursor.execute('SELECT DISTINCT category FROM action_types')
    categories = [row[0] for row in cursor.fetchall()]
    print(f"\n修改后分类: {categories}")
    print(f"总共更新了 {total_updated} 条记录")
    
    conn.close()
    print("本地数据库修复完成！")

def fix_online_db():
    """修复线上PostgreSQL数据库"""
    from sqlalchemy import create_engine, text
    
    DATABASE_URL = os.environ.get('DATABASE_URL')
    if not DATABASE_URL:
        # 使用Neon连接串
        DATABASE_URL = "postgresql://neondb_owner:npg_u1rFnCVX7NTx@ep-restless-feather-azyo5mej-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    
    # 转换为psycopg3格式
    if DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
    
    print("\n" + "=" * 60)
    print("修复线上数据库行为类型分类名")
    print("=" * 60)
    
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # 查询当前所有分类
        result = conn.execute(text('SELECT DISTINCT category FROM action_types'))
        categories = [row[0] for row in result.fetchall()]
        print(f"当前分类: {categories}")
        
        # 修改分类名
        total_updated = 0
        for eng, chn in CATEGORY_MAP.items():
            result = conn.execute(text('UPDATE action_types SET category = :chn WHERE category = :eng'), {'chn': chn, 'eng': eng})
            updated = result.rowcount
            if updated > 0:
                print(f"  {eng} → {chn}: 更新了 {updated} 条")
                total_updated += updated
        
        conn.commit()
        
        # 查询修改后的分类
        result = conn.execute(text('SELECT DISTINCT category FROM action_types'))
        categories = [row[0] for row in result.fetchall()]
        print(f"\n修改后分类: {categories}")
        print(f"总共更新了 {total_updated} 条记录")
    
    engine.dispose()
    print("线上数据库修复完成！")

if __name__ == '__main__':
    fix_local_db()
    fix_online_db()
    print("\n" + "=" * 60)
    print("全部修复完成！")
    print("=" * 60)
