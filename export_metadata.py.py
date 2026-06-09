import json
from sqlalchemy import create_engine, inspect

def export_db_metadata(db_uri, output_filename="tables_metada.json"):
    """
    连接数据库并将其元数据导出为 JSON 文件
    """
    try:
        # 1. 创建数据库引擎
        engine = create_engine(db_uri)
        
        # 2. 创建检查器（Inspector）用于获取元数据
        inspector = inspect(engine)
        
        metadata_dict = {}
        
        # 3. 获取所有表名
        table_names = inspector.get_table_names()
        print(f"成功连接数据库，共发现 {len(table_names)} 张表。开始导出...")
        
        for table_name in table_names:
            metadata_dict[table_name] = {
                "columns": [],
                "primary_keys": inspector.get_pk_constraint(table_name).get("constrained_columns", []),
                "foreign_keys": []
            }
            
            # 获取列信息
            columns = inspector.get_columns(table_name)
            for col in columns:
                metadata_dict[table_name]["columns"].append({
                    "name": col["name"],
                    "type": str(col["type"]),  # 将 SQLAlchemy 类型转换为字符串
                    "nullable": col["nullable"],
                    "default": str(col["default"]) if col["default"] is not None else None,
                    "comment": col.get("comment", None)  # 部分数据库支持列注释
                })
                
            # 获取外键信息
            fk_constraints = inspector.get_foreign_keys(table_name)
            for fk in fk_constraints:
                metadata_dict[table_name]["foreign_keys"].append({
                    "constrained_columns": fk["constrained_columns"],
                    "referred_schema": fk["referred_schema"],
                    "referred_table": fk["referred_table"],
                    "referred_columns": fk["referred_columns"]
                })
                
        # 4. 写入 JSON 文件
        with open(output_filename, 'w', encoding='utf-8') as f:
            json.dump(metadata_dict, f, indent=4, ensure_ascii=False)
            
        print(f"导出成功！元数据已写入: {output_filename}")

    except Exception as e:
        print(f"导出过程中发生错误: {e}")

if __name__ == "__main__":
    # ================= 配置区域 =================
    # 替换为你的数据库连接字符串 (Database URI)
    # 格式: 数据库驱动://用户名:密码@主机地址:端口号/数据库名
    
    # 示例 (MSSQL): 请把下面的字符串替换为你的实际连接 URL，并用引号包裹
    DB_URI = "mssql+pyodbc://x123456/成绩管理?trusted_connection=yes&driver=ODBC+Driver+17+for+SQL+Server"
    
    # 示例 (PostgreSQL):
    # DB_URI = "postgresql+psycopg2://user:password@localhost:5432/my_database"
    
    # 示例 (SQLite):
    # DB_URI = "sqlite:///my_database.db"
    # ============================================

    OUTPUT_FILE = "tables_metadata.json"
    
    export_db_metadata(DB_URI, OUTPUT_FILE)