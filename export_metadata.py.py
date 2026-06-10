import json
import datetime
import decimal
from sqlalchemy import create_engine  # 如果需要使用 SQLAlchemy 引擎，可改为 create_engine
import pyodbc 

# ----------------- 配置你的数据库连接 -----------------
DB_CONFIG = {
    "server": "x123456",
    "database": "成绩管理",
    "driver": "{ODBC Driver 17 for SQL Server}",
    "trusted_connection": "yes"
}

# 构造跟你 JSON 中一致的数据库连接 URL（仅用于记录在 JSON 中）
DATABASE_URL = f"mssql+pyodbc://{DB_CONFIG['server']}/{DB_CONFIG['database']}?trusted_connection={DB_CONFIG['trusted_connection']}&driver=ODBC+Driver+17+for+SQL"

OUTPUT_FILE = "tables_metadata.json"

# 自定义 JSON 编码器，处理 SQL 中的 Decimal 和 Date/Datetime 类型，防止无法序列化
class AlchemyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        elif isinstance(obj, decimal.Decimal):
            return float(obj)
        return super(AlchemyEncoder, self).default(obj)

def get_db_connection():
    conn_str = (
        f"DRIVER={DB_CONFIG['driver']};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
        f"Trusted_Connection={DB_CONFIG['trusted_connection']};"
    )
    return pyodbc.connect(conn_str)

def generate_mock_description(table_name, columns):
    """
    智能生成业务描述。
    提示：如果你后续配合大模型，可以把这里的文本替换为调用 OpenAI/DeepSeek API，
    让大模型根据表名和字段生成更详细的业务解释。目前先生成标准模板。
    """
    col_str = ", ".join(columns)
    return f"该表为核心业务中的“{table_name}”实体。关键筛选与统计字段包括：{col_str}。用于支撑相关的教务管理和数据统计场景。"

def export_metadata():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 初始化最终的 JSON 结构
    result = {
        "version": 1,
        "tables": {},
        "database_dialect": "mssql",
        "database_url": DATABASE_URL,
        "updated_at": datetime.datetime.utcnow().isoformat() + "+00:00"
    }
    
    print("正在读取数据库表结构...")
    
    # 1. 查询所有用户表及其 Schema
    cursor.execute("""
        SELECT t.name AS table_name, s.name AS schema_name
        FROM sys.tables t
        INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
        WHERE t.is_ms_shipped = 0
    """)
    tables = cursor.fetchall()
    
    for row in tables:
        t_name = row.table_name
        s_name = row.schema_name
        qualified_name = f"{s_name}.{t_name}"
        
        print(f"正在处理表: {qualified_name} ...")
        
        # 2. 获取该表的字段列表
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = ? AND table_schema = ?
        """, (t_name, s_name))
        columns = [col_row[0] for col_row in cursor.fetchall()]
        
        # 3. 智能获取数据样例 (Column Examples) - 限制取前 5 条数据
        column_examples = {}
        if columns:
            try:
                # 组装动态 SQL 安全地读取前 5 条数据
                col_selectors = ", ".join([f"[{c}]" for c in columns])
                cursor.execute(f"SELECT TOP 5 {col_selectors} FROM [{s_name}].[{t_name}]")
                rows = cursor.fetchall()
                
                # 初始化每个字段的列表
                for c in columns:
                    column_examples[c] = []
                    
                # 填充数据并去重、转成字符串
                for r in rows:
                    for idx, val in enumerate(r):
                        if val is not None and str(val).strip() != "":
                            # 格式化日期或特殊类型
                            if isinstance(val, (datetime.datetime, datetime.date)):
                                val_str = val.isoformat()
                            elif isinstance(val, decimal.Decimal):
                                val_str = float(val)
                            else:
                                val_str = str(val)
                                
                            if val_str not in column_examples[columns[idx]]:
                                column_examples[columns[idx]].append(val_str)
                                
                # 清理掉没有样例数据的空字段
                column_examples = {k: v for k, v in column_examples.items() if v}
            except Exception as e:
                print(f"  警告: 无法获取 {qualified_name} 的数据样例: {e}")
                column_examples = {}

        # 4. 生成或提取 DDL (这里通过查询系统表拼装一个简易的基础 DDL，确保符合要求)
        # 提示：SQL Server 产生完美 DDL 较复杂，这里生成标准 ANSI DDL
        ddl_lines = []
        for col in columns:
            cursor.execute("""
                SELECT data_type, character_maximum_length, is_nullable
                FROM information_schema.columns 
                WHERE table_name = ? AND table_schema = ? AND column_name = ?
            """, (t_name, s_name, col))
            c_info = cursor.fetchone()
            if c_info:
                dt, length, is_null = c_info
                type_str = f"{dt}({length})" if length and length != -1 else dt
                null_str = "NULL" if is_null == "YES" else "NOT NULL"
                ddl_lines.append(f"  [{col}] {type_str.upper()} {null_str}")
                
        ddl_string = f"CREATE TABLE [{s_name}].[{t_name}] (\n" + ",\n".join(ddl_lines) + "\n);"

        # 5. 组装单张表的元数据对象
        table_meta = {
            "table_name": t_name,
            "schema": s_name,
            "qualified_name": qualified_name,
            "status": "ok",
            "ddl": ddl_string,
            "ddl_source": "inspector",
            "description": generate_mock_description(t_name, columns),
            "generated_at": datetime.datetime.utcnow().isoformat() + "+00:00"
        }
        
        # 如果存在样例数据，则加入
        if column_examples:
            table_meta["column_examples"] = column_examples
            
        # 存入大字典
        result["tables"][qualified_name] = table_meta

    # 6. 写入到本地 JSON 文件中
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, cls=AlchemyEncoder, ensure_ascii=False, indent=2)
        
    print(f"\n🎉 元数据导出成功！已保存到文件: {OUTPUT_FILE}")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    export_metadata()