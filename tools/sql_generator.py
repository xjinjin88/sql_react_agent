from pydantic import BaseModel, Field
from typing import Type, Optional, List
from tools.llm_client import LLMClient
from tools.tool_base import Tool, ToolResult, ToolContext
from tools.table_retriever import TableMetadataLoader


class GenerateSQLArgs(BaseModel):
    question: str = Field(description="用户的自然语言问题")
    table_schema: str = Field(default="", description="数据库表结构信息")
    table_names: List[str] = Field(default=None, description="表名列表，用于动态获取表结构")
    db_type: str = Field(default="sqlite", description="数据库类型: mysql, postgres, sqlite, mssql")


class SQLGenerator(Tool):
    name = "sql_generator"
    description = "根据问题和表结构生成SQL"
    access_groups = ["sql"]
    categories = ["sql"]

    def __init__(self):
        self.llm = LLMClient()
        self.metadata = None

    def _load_metadata(self):
        if self.metadata is None:
            self.metadata = TableMetadataLoader.load_from_file("tables_metadata.json")

    def _get_table_schema(self, table_name: str) -> Optional[str]:
        self._load_metadata()
        table_info = self.metadata.get("tables", {}).get(table_name)
        if not table_info:
            return None

        ddl = table_info.get("ddl", "")
        description = table_info.get("description", "")

        return f"""表名: {table_name}

描述: {description}

DDL:
{ddl}"""

    def _get_tables_schema(self, table_names: List[str]) -> str:
        schemas = []
        for table_name in table_names:
            schema = self._get_table_schema(table_name)
            if schema:
                schemas.append(schema)
        return "\n\n".join(schemas)

    def get_args_schema(self) -> Type[BaseModel]:
        return GenerateSQLArgs

    def execute(self, context: ToolContext, args: dict) -> ToolResult:
        print(f"[sql_generator] Received args: {args}")
        question = args.get("question", "")
        table_schema = args.get("table_schema", "") or args.get("schema", "")
        table_names = args.get("table_names", [])
        db_type = args.get("db_type", "sqlite")

        print(f"[sql_generator] question={question[:50] if question else 'EMPTY'}, table_names={table_names}, db_type={db_type}")

        if not question:
            return ToolResult(success=False, error="问题不能为空")

        if not table_schema and not table_names:
            return ToolResult(success=False, error="数据库表结构或表名列表不能为空")

        try:
            if table_names:
                table_schema = self._get_tables_schema(table_names)
                print(f"[sql_generator] Generated schema from table_names: {len(table_schema)} chars")

            dialect = self._get_sql_dialect(db_type)
            prompt = f"""你是一个专业的{dialect}数据库SQL专家。根据用户的问题和提供的数据库表结构信息，生成准确、高效、语法正确的SQL查询语句。

数据库类型: {dialect}

数据库表结构:
{table_schema}

用户问题: {question}

SQL生成规则：
- 必须使用标准的{dialect} SQL语法
- 必须使用上述表结构中定义的准确表名和列名，区分大小写
- NULL值判断必须使用 IS NULL / IS NOT NULL，禁止使用 = NULL
- 字符串值必须使用单引号包裹
- 日期值使用 'YYYY-MM-DD' 格式，日期时间使用 'YYYY-MM-DD HH:MM:SS' 格式
- GROUP BY 子句必须包含 SELECT 中非聚合列的所有字段
- 根据外键关系使用适当的JOIN类型（INNER JOIN、LEFT JOIN等）
- 对于复杂查询，可以使用子查询或CTE（WITH子句）
- 优先使用索引字段作为过滤条件
- 除非用户明确要求，否则不要添加 LIMIT、TOP 或 OFFSET/FETCH 限制

{dialect}特定语法：
- MySQL: 使用 LIMIT 进行分页，字符串连接使用 CONCAT()
- SQL Server: 使用 TOP 或 OFFSET/FETCH 进行分页，字符串连接使用 + 或 CONCAT()
- SQLite: 使用 LIMIT/OFFSET 进行分页
- PostgreSQL: 使用 LIMIT/OFFSET 进行分页，字符串连接使用 ||

输出格式：
- 请只返回纯SQL语句，不要包含任何解释、说明或markdown格式
- 确保SQL语句完整且可以直接执行

例如:
SELECT student_name, score
FROM dbo.student
JOIN dbo.score ON student.student_id = score.student_id
WHERE score > 60
ORDER BY score DESC;"""

            result = self.llm.generate(prompt)
            sql = self._clean_sql(result)

            if not sql:
                return ToolResult(success=False, error="无法生成SQL语句")

            sql = self._fix_sql_dialect(sql, db_type)

            return ToolResult(success=True, data={"sql": sql})
        except Exception as e:
            return ToolResult(success=False, error=f"SQL生成失败: {str(e)}")

    def _get_sql_dialect(self, db_type: str) -> str:
        dialects = {
            "mysql": "MySQL",
            "postgres": "PostgreSQL",
            "sqlite": "SQLite",
            "mssql": "SQL Server"
        }
        return dialects.get(db_type.lower(), "SQLite")

    def _fix_sql_dialect(self, sql: str, db_type: str) -> str:
        if db_type.lower() == "mssql":
            import re
            sql = re.sub(r'\bLIMIT\s+(\d+)\s*;?$', r'TOP \1', sql, flags=re.IGNORECASE)
        return sql

    def generate_sql(self, question: str, schema: str, db_type: str = "sqlite") -> Optional[str]:
        try:
            dialect = self._get_sql_dialect(db_type)
            prompt = f"""你是一个专业的{dialect}数据库SQL专家。根据用户的问题和提供的数据库表结构信息，生成准确、高效、语法正确的SQL查询语句。

数据库类型: {dialect}

数据库表结构:
{schema}

用户问题: {question}

SQL生成规则：
- 必须使用标准的{dialect} SQL语法
- 必须使用上述表结构中定义的准确表名和列名，区分大小写
- NULL值判断必须使用 IS NULL / IS NOT NULL，禁止使用 = NULL
- 字符串值必须使用单引号包裹
- GROUP BY 子句必须包含 SELECT 中非聚合列的所有字段
- 根据外键关系使用适当的JOIN类型（INNER JOIN、LEFT JOIN等）
- 对于复杂查询，可以使用子查询或CTE（WITH子句）
- 优先使用索引字段作为过滤条件
- 除非用户明确要求，否则不要添加 LIMIT、TOP 或 OFFSET/FETCH 限制

输出格式：
- 请只返回纯SQL语句，不要包含任何解释、说明或markdown格式
- 确保SQL语句完整且可以直接执行

例如:
SELECT student_name, score
FROM student
JOIN score ON student.student_id = score.student_id
WHERE score > 60
ORDER BY score DESC;"""

            result = self.llm.generate(prompt)
            return self._clean_sql(result)
        except Exception as e:
            print(f"SQL生成失败: {e}")
            return None

    def _clean_sql(self, sql: str) -> str:
        if not sql:
            return ""
        sql = sql.strip()
        if sql.startswith("```sql"):
            sql = sql[6:]
        if sql.startswith("```"):
            sql = sql[3:]
        if sql.endswith("```"):
            sql = sql[:-3]
        return sql.strip()