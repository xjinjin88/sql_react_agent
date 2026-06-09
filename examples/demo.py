import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.sql_agent import SQLAgent

def main():
    agent = SQLAgent()
    
    print("欢迎使用SQL智能体！")
    print("=" * 50)
    
    while True:
        print("\n可用命令:")
        print("1. connect <db_type> - 连接数据库 (支持: mysql, postgres, sqlite, mssql)")
        print("2. disconnect - 断开数据库连接")
        print("3. schema - 查看数据库表结构")
        print("4. query <question> - 执行SQL查询(全表)")
        print("5. smart_query <question> - 智能查询(表检索+SQL生成)")
        print("6. search <keyword> - 搜索相关表")
        print("7. table_info <table_name> - 查看表详细信息")
        print("8. explain <sql> - 解释SQL语句")
        print("9. exit - 退出")
        
        command = input("\n请输入命令: ").strip()
        
        if not command:
            continue
        
        parts = command.split(" ", 1)
        cmd = parts[0].lower()
        
        if cmd == "exit":
            print("退出SQL智能体...")
            break
        
        elif cmd == "connect":
            if len(parts) < 2:
                print("请指定数据库类型: connect <mysql|postgres|sqlite|mssql>")
                continue
            
            db_type = parts[1].lower()
            if db_type not in ["mysql", "postgres", "sqlite", "mssql"]:
                print("不支持的数据库类型")
                continue
            
            result = agent.connect_database(db_type)
            print(result)
        
        elif cmd == "disconnect":
            result = agent.disconnect_database()
            print(result)
        
        elif cmd == "schema":
            schema = agent.get_database_schema()
            print(schema)
        
        elif cmd == "query":
            if len(parts) < 2:
                print("请输入查询问题: query <your question>")
                continue
            
            question = parts[1]
            print(f"\n正在处理查询: {question}")
            print("-" * 50)
            
            result = agent.run_query(question)
            
            if result["status"] == "error":
                print(f"错误: {result['error']}")
                continue
            
            print(f"\n生成的SQL:")
            print(result["sql"])
            
            print(f"\n查询结果:")
            print(agent.format_results(result["execution_result"]["data"]))
            
            print(f"\n结果分析:")
            print(result["analysis"])
        
        elif cmd == "smart_query":
            if len(parts) < 2:
                print("请输入查询问题: smart_query <your question>")
                continue
            
            question = parts[1]
            print(f"\n正在智能查询: {question}")
            print("-" * 50)
            
            result = agent.run_query_with_retrieval(question)
            
            if result["status"] == "error":
                print(f"错误: {result['error']}")
                continue
            
            print(f"\n检索到的表:")
            for table in result["retrieved_tables"]:
                print(f"  - {table}")
            
            print(f"\n生成的SQL:")
            print(result["sql"])
            
            print(f"\n查询结果:")
            print(agent.format_results(result["execution_result"]["data"]))
            
            print(f"\n结果分析:")
            print(result["analysis"])
        
        elif cmd == "search":
            if len(parts) < 2:
                print("请输入搜索关键词: search <keyword>")
                continue
            
            keyword = parts[1]
            print(f"\n搜索表: {keyword}")
            print("-" * 50)
            
            result = agent.search_tables(keyword)
            print(result)
        
        elif cmd == "table_info":
            if len(parts) < 2:
                print("请输入表名: table_info <table_name>")
                continue
            
            table_name = parts[1]
            print(f"\n表信息: {table_name}")
            print("-" * 50)
            
            info = agent.get_table_info(table_name)
            print(info)
        
        elif cmd == "explain":
            if len(parts) < 2:
                print("请输入SQL语句: explain <sql>")
                continue
            
            sql = parts[1]
            explanation = agent.explain_sql(sql)
            print(f"\nSQL解释:")
            print(explanation)
        
        else:
            print("未知命令，请重试")

if __name__ == "__main__":
    main()