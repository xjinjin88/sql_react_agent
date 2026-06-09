from collections import defaultdict
from pydantic import BaseModel, Field
from typing import Type, Optional, List, Dict, Any
from tools.database_connection import DatabaseConnection
from tools.tool_base import Tool, ToolResult, ToolContext


class SchemaNormalizer:
    """用于规范化表结构信息，减少token消耗"""
    
    MAX_EXAMPLES_PER_COLUMN = 3

    @classmethod
    def normalize(cls, explorer_result: dict) -> dict:
        """
        规范化探索结果，精简字段信息并提取示例值
        
        explorer_result:
        {
            "table_name": "...",
            "columns": [...],
            "sample_rows": [...]
        }
        """
        normalized = {
            "table_name": explorer_result["table_name"],
            "columns": []
        }

        sample_rows = explorer_result.get("sample_rows", [])
        example_map = cls._extract_examples(sample_rows)

        for col in explorer_result.get("columns", []):
            col_name = col["name"]
            normalized_col = {
                "name": col_name,
                "type": col.get("type", "")  # 保留类型信息
            }

            comment = col.get("comment")
            if comment:
                normalized_col["comment"] = comment

            examples = example_map.get(col_name, [])
            if examples:
                normalized_col["examples"] = examples

            normalized["columns"].append(normalized_col)

        return normalized

    @classmethod
    def _extract_examples(cls, sample_rows: list[dict]) -> dict:
        """从样本数据中提取每个字段的示例值"""
        example_map = defaultdict(set)

        for row in sample_rows:
            for col, value in row.items():
                if value is None:
                    continue
                value = str(value)
                if len(value) > 30:
                    continue
                example_map[col].add(value)

        return {
            col: list(values)[:cls.MAX_EXAMPLES_PER_COLUMN]
            for col, values in example_map.items()
        }


def build_schema_summary(schemas: dict) -> str:
    """
    将多个表的schema信息格式化为简洁的文本摘要
    
    schemas:
    {
        "table_name": {
            "table_name": "...",
            "columns": [...]
        }
    }
    """
    lines = ["已确认Schema:\n"]

    for table_name, schema in schemas.items():
        lines.append(f"{table_name}:")

        for col in schema.get("columns", []):
            line = f"  - {col['name']}"

            if col.get("comment"):
                line += f" ({col['comment']})"

            if col.get("examples"):
                line += f" 例值:{','.join(col['examples'])}"

            lines.append(line)

        lines.append("")

    return "\n".join(lines)


class ExploreTableArgs(BaseModel):
    table_name: str = Field(description="要探索的表名")
    max_rows: int = Field(default=5, description="返回的最大行数")


class GetTableSchemaArgs(BaseModel):
    table_name: str = Field(description="要获取结构的表名")


class TableExplorer(Tool):
    name = "table_explorer"
    description = "探索数据库表的结构和样例数据，帮助理解表的内容和字段含义"
    access_groups = ["exploration"]
    categories = ["exploration"]

    def __init__(self):
        self.db_connection: Optional[DatabaseConnection] = None
        self.db_type: str = "sqlite"

    def set_db_connection(self, connection: DatabaseConnection):
        self.db_connection = connection
        if connection:
            self.db_type = connection.db_type

    def get_args_schema(self) -> Type[BaseModel]:
        return ExploreTableArgs

    def execute(self, context: ToolContext, args: dict) -> ToolResult:
        table_name = args.get("table_name", "")
        max_rows = args.get("max_rows", 5)
        return self.explore_table(table_name, max_rows)

    def explore_table(self, table_name: str, max_rows: int = 5) -> ToolResult:
        if not self.db_connection:
            return ToolResult(success=False, error="未连接数据库")

        try:
            schema_name = None
            table_only_name = table_name
            
            if "." in table_name:
                parts = table_name.split(".")
                if len(parts) == 2:
                    schema_name = parts[0]
                    table_only_name = parts[1]
                elif len(parts) > 2:
                    schema_name = ".".join(parts[:-1])
                    table_only_name = parts[-1]

            schema = self._get_table_schema_with_schema(table_only_name, schema_name)
            
            if not schema and schema_name and self.db_type.lower() == "sqlite":
                schema = self._get_table_schema_with_schema(table_only_name, None)
            
            if not schema:
                return ToolResult(success=False, error=f"未找到表: {table_name}")

            sample_query = self._build_sample_query(table_name, max_rows)
            sample_data = self.db_connection.execute_query(sample_query)

            total_rows = self._get_table_row_count(table_name)

            result = {
                "table_name": table_name,
                "columns": schema.get("columns", []),
                "foreign_keys": schema.get("foreign_keys", []),
                "sample_data": sample_data or [],
                "sample_row_count": len(sample_data) if sample_data else 0,
                "total_row_count": total_rows
            }

            result["formatted_markdown"] = self._format_result_to_markdown(result)
            
            # 添加规范化后的精简结果，用于LLM处理
            normalized_input = {
                "table_name": table_name,
                "columns": schema.get("columns", []),
                "sample_rows": sample_data or []
            }
            result["normalized"] = SchemaNormalizer.normalize(normalized_input)

            return ToolResult(success=True, data=result)
        except Exception as e:
            return ToolResult(success=False, error=f"探索表失败: {str(e)}")

    def _get_table_row_count(self, table_name: str) -> int:
        """获取表的实际总行数"""
        try:
            query_table_name = table_name
            if "." in table_name and self.db_type.lower() == "sqlite":
                query_table_name = table_name.split(".")[-1]
            count_query = f"SELECT COUNT(*) as total FROM {query_table_name}"
            result = self.db_connection.execute_query(count_query)
            if result and len(result) > 0:
                return int(result[0].get("total", 0))
            return 0
        except Exception as e:
            print(f"[table_explorer] 获取表行数失败: {e}")
            return 0

    def _format_result_to_markdown(self, result: Dict[str, Any]) -> str:
        """将探索结果格式化为精简的 markdown 格式"""
        lines = []
        
        table_name = result.get("table_name", "")
        lines.append(f"## 表: {table_name}")
        
        lines.append("\n### 字段列表")
        columns = result.get("columns", [])
        if columns:
            lines.append("| 字段名 | 数据类型 |")
            lines.append("|--------|----------|")
            for col in columns:
                col_name = col.get("name", "")
                col_type = col.get("type", "")
                # 简化数据类型显示，移除不必要的COLLATE信息
                if "COLLATE" in col_type:
                    col_type = col_type.split("COLLATE")[0].strip()
                lines.append(f"| {col_name} | {col_type} |")
        
        foreign_keys = result.get("foreign_keys", [])
        if foreign_keys:
            lines.append("\n### 外键关系")
            for fk in foreign_keys:
                constrained_cols = ", ".join(fk.get("constrained_columns", []))
                ref_table = fk.get("referred_table", "")
                ref_cols = ", ".join(fk.get("referred_columns", []))
                lines.append(f"- `{constrained_cols}` → `{ref_table}({ref_cols})`")
        
        sample_data = result.get("sample_data", [])
        if sample_data:
            lines.append("\n### 样例数据")
            if sample_data:
                headers = list(sample_data[0].keys())
                lines.append("| " + " | ".join(headers) + " |")
                lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
                for row in sample_data:
                    values = [str(row.get(h, "")) for h in headers]
                    lines.append("| " + " | ".join(values) + " |")
        
        total_rows = result.get("total_row_count", 0)
        sample_rows = result.get("sample_row_count", 0)
        lines.append(f"\n**表总记录数**: {total_rows} 条")
        if sample_rows > 0:
            lines.append(f"**展示样例**: {sample_rows} 条")
        
        return "\n".join(lines)

    def _get_table_schema_with_schema(self, table_name: str, schema_name: str = None) -> Dict[str, Any]:
        if not self.db_connection or not self.db_connection.inspector:
            return {}

        columns = []
        try:
            for col in self.db_connection.inspector.get_columns(table_name, schema=schema_name):
                columns.append({
                    "name": col["name"],
                    "type": str(col["type"])
                })

            foreign_keys = []
            for fk in self.db_connection.inspector.get_foreign_keys(table_name, schema=schema_name):
                foreign_keys.append({
                    "constrained_columns": fk["constrained_columns"],
                    "referred_table": fk["referred_table"],
                    "referred_columns": fk["referred_columns"]
                })

            return {
                "table_name": table_name if not schema_name else f"{schema_name}.{table_name}",
                "columns": columns,
                "foreign_keys": foreign_keys
            }
        except Exception as e:
            print(f"[table_explorer] 获取表结构失败: {e}")
            return {}

    def _build_sample_query(self, table_name: str, max_rows: int) -> str:
        db_type = self.db_type.lower() if self.db_type else "sqlite"
        
        query_table_name = table_name
        if "." in table_name and db_type == "sqlite":
            query_table_name = table_name.split(".")[-1]
        
        if db_type == "mssql":
            return f"SELECT TOP {max_rows} * FROM {query_table_name}"
        elif db_type in ["mysql", "sqlite", "postgres", "postgresql"]:
            return f"SELECT * FROM {query_table_name} LIMIT {max_rows}"
        else:
            return f"SELECT * FROM {query_table_name} LIMIT {max_rows}"

    def get_table_schema_tool(self, table_name: str) -> ToolResult:
        if not self.db_connection:
            return ToolResult(success=False, error="未连接数据库")

        try:
            schema_name = None
            table_only_name = table_name
            
            if "." in table_name:
                parts = table_name.split(".")
                if len(parts) == 2:
                    schema_name = parts[0]
                    table_only_name = parts[1]

            schema = self._get_table_schema_with_schema(table_only_name, schema_name)
            if not schema:
                return ToolResult(success=False, error=f"未找到表: {table_name}")

            return ToolResult(success=True, data=schema)
        except Exception as e:
            return ToolResult(success=False, error=f"获取表结构失败: {str(e)}")

    def get_multiple_tables_info(self, table_names: List[str], max_rows: int = 3) -> ToolResult:
        if not self.db_connection:
            return ToolResult(success=False, error="未连接数据库")

        results = {}
        markdown_parts = []
        
        for table_name in table_names:
            try:
                result = self.explore_table(table_name, max_rows)
                if result.success:
                    results[table_name] = result.data
                    markdown_parts.append(result.data.get("formatted_markdown", ""))
            except Exception as e:
                results[table_name] = {"error": str(e)}
                markdown_parts.append(f"## 表: {table_name}\n\n**错误**: {str(e)}")

        return ToolResult(
            success=True, 
            data={
                "tables": results, 
                "count": len(results),
                "formatted_markdown": "\n\n---\n\n".join(markdown_parts)
            }
        )