"""
初始化 Neon 线上数据库（调试版）
"""
import os
import sys
import traceback

# 尝试不同的连接字符串
DATABASE_URLS = [
    # 原始地址
    "postgresql://neondb_owner:npg_u1rFnCVX7NTx@ep-restless-feather-azyo5mej-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require",
    # 去掉 pooler
    "postgresql://neondb_owner:npg_u1rFnCVX7NTx@ep-restless-feather-azyo5mej.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require",
]

for i, url in enumerate(DATABASE_URLS):
    print(f"\n尝试连接方式 {i+1}...")
    print(f"  地址: {url[:60]}...")
    try:
        import psycopg
        conn = psycopg.connect(url, connect_timeout=10)
        cur = conn.cursor()
        cur.execute("SELECT 1")
        print(f"  ✅ 连接成功！测试查询结果: {cur.fetchone()[0]}")
        conn.close()
        
        # 设置环境变量并初始化
        os.environ["DATABASE_URL"] = url
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        # 重新导入（确保使用新的环境变量）
        import importlib
        import db
        importlib.reload(db)
        
        print(f"\n  数据库类型: {db.DB_TYPE}")
        print("  正在创建数据表...")
        db.init_db()
        print("  ✅ 数据表创建成功！")
        
        print("  正在插入初始数据...")
        db.seed_initial_data()
        print("  ✅ 初始数据插入成功！")
        
        # 验证
        print("\n  验证数据...")
        conn = db.get_db()
        cur = conn.cursor()
        for table in ["roles", "actions", "setups", "algorithm_weights"]:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            print(f"    {table}: {cur.fetchone()[0]} 条")
        conn.close()
        
        print(f"\n🎉 Neon 数据库初始化完成！（使用连接方式 {i+1}）")
        sys.exit(0)
        
    except Exception as e:
        print(f"  ❌ 连接失败: {type(e).__name__}: {e}")
        traceback.print_exc()
        continue

print("\n❌ 所有连接方式都失败了")
sys.exit(1)
