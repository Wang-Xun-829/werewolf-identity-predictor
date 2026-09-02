"""
重置线上数据库玩家个性权重到初始状态（1.0）
"""
import os
import sys
from sqlalchemy import create_engine, text

# 线上数据库连接串
DATABASE_URL = "postgresql://neondb_owner:npg_u1rFnCVX7NTx@ep-restless-feather-azyo5mej-pooler.c-3.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# 使用psycopg3驱动
DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

def reset_weights():
    print("=" * 60)
    print("重置线上数据库玩家个性权重到初始状态（1.0）")
    print("=" * 60)
    
    # 连接数据库
    print("\n连接线上数据库...")
    engine = create_engine(DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            # 先查询当前的权重统计
            result = conn.execute(text("""
                SELECT 
                    COUNT(*) as total_count,
                    COUNT(DISTINCT player_id) as player_count,
                    AVG(weight) as avg_weight,
                    MIN(weight) as min_weight,
                    MAX(weight) as max_weight
                FROM identity_weights
            """))
            row = result.fetchone()
            print(f"\n重置前统计：")
            print(f"  总权重记录数: {row[0]}")
            print(f"  涉及玩家数: {row[1]}")
            print(f"  平均权重: {row[2]:.4f}")
            print(f"  最小权重: {row[3]:.4f}")
            print(f"  最大权重: {row[4]:.4f}")
            
            # 查询有多少权重不是1.0
            result = conn.execute(text("""
                SELECT COUNT(*) FROM identity_weights WHERE weight != 1.0
            """))
            non_default_count = result.fetchone()[0]
            print(f"  非默认权重（≠1.0）记录数: {non_default_count}")
            
            # 执行重置
            print(f"\n正在重置所有权重为1.0...")
            result = conn.execute(text("""
                UPDATE identity_weights SET weight = 1.0
            """))
            conn.commit()
            print(f"  已重置 {result.rowcount} 条记录")
            
            # 验证重置结果
            result = conn.execute(text("""
                SELECT 
                    COUNT(*) as total_count,
                    COUNT(DISTINCT player_id) as player_count,
                    AVG(weight) as avg_weight,
                    MIN(weight) as min_weight,
                    MAX(weight) as max_weight
                FROM identity_weights
            """))
            row = result.fetchone()
            print(f"\n重置后统计：")
            print(f"  总权重记录数: {row[0]}")
            print(f"  涉及玩家数: {row[1]}")
            print(f"  平均权重: {row[2]:.4f}")
            print(f"  最小权重: {row[3]:.4f}")
            print(f"  最大权重: {row[4]:.4f}")
            
            # 验证是否所有重都是1.0
            result = conn.execute(text("""
                SELECT COUNT(*) FROM identity_weights WHERE weight != 1.0
            """))
            remaining = result.fetchone()[0]
            if remaining == 0:
                print(f"\n✅ 重置成功！所有权重已恢复为初始值1.0")
            else:
                print(f"\n⚠️  还有 {remaining} 条记录不是1.0，请检查")
    
    except Exception as e:
        print(f"\n❌ 重置失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        engine.dispose()
    
    print("\n" + "=" * 60)
    print("操作完成")
    print("=" * 60)

if __name__ == "__main__":
    reset_weights()
