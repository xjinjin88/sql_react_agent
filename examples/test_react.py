import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.react_agent import ReactAgent
from tools.database_connection import DatabaseConnection


def main():
    print("=== ReAct Agent 测试 ===")
    print()
    
    # 1. 初始化 Agent
    print("1. 初始化 ReAct Agent...")
    agent = ReactAgent(max_iterations=10)
    print("   ✓ Agent 初始化完成")
    print()
    
    # 2. 连接数据库
    print("2. 连接数据库 (SQLite)...")
    db = DatabaseConnection(db_type="sqlite")
    if db.connect():
        print("   ✓ 数据库连接成功")
        agent.set_db_connection(db)
    else:
        print("   ✗ 数据库连接失败")
        print("   提示: 确保 example.db 存在或配置正确的数据库")
        return
    print()
    
    # 3. 测试运行
    print("3. 测试 ReAct 工作流...")
    question = "查看数据库中有哪些表"
    print(f"   用户问题: {question}")
    print()
    
    try:
        result = agent.run(question)
        print("   ✓ 运行完成")
        print()
        print("=" * 50)
        print("最终答案:")
        print(result["answer"])
        print("=" * 50)
        print()
        print(f"迭代次数: {result['iterations']}")
        print(f"发现的表: {result['state'].discovered_tables}")
        print(f"已探索的 Schema: {list(result['state'].explored_schemas.keys())}")
        
    except Exception as e:
        print(f"   ✗ 运行失败: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=== 测试结束 ===")


if __name__ == "__main__":
    main()
