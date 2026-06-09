from pydantic import BaseModel, Field
from typing import Type, List, Dict, Any, Optional
from tools.database_connection import DatabaseConnection
from tools.sql_validator import SQLValidator
from tools.llm_client import LLMClient
from tools.tool_base import Tool, ToolResult, ToolContext


class ExecuteSQLArgs(BaseModel):
    sql: str = Field(description="要执行的SQL语句")


class SQLExecutor(Tool):
    name = "sql_executor"
    description = "执行SQL并返回结果"
    access_groups = ["sql"]
    categories = ["sql"]

    def __init__(self):
        self.validator = SQLValidator()
        self.connection: Optional[DatabaseConnection] = None

    def get_args_schema(self) -> Type[BaseModel]:
        return ExecuteSQLArgs

    def execute(self, context: ToolContext, args: dict) -> ToolResult:
        sql = args.get("sql", "")
        return self.execute_sql_tool(sql)

    def set_connection(self, connection: DatabaseConnection):
        self.connection = connection

    def execute_sql_tool(self, sql: str) -> ToolResult:
        if not self.connection:
            return ToolResult(success=False, error="未连接数据库")

        validation = self.validator.validate_sql(sql)
        if not validation["valid"]:
            return ToolResult(success=False, error="; ".join(validation["errors"]))

        try:
            data = self.connection.execute_query(sql)
            if data is None:
                return ToolResult(success=False, error="SQL执行失败")

            return ToolResult(
                success=True,
                data={"results": data, "row_count": len(data)},
                metadata={"row_count": len(data)}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def execute_sql(self, sql: str) -> dict:
        result = {
            "success": False,
            "data": None,
            "error": None,
            "row_count": 0
        }

        if not self.connection:
            result["error"] = "未连接数据库"
            return result

        validation = self.validator.validate_sql(sql)
        if not validation["valid"]:
            result["error"] = "; ".join(validation["errors"])
            return result

        try:
            data = self.connection.execute_query(sql)
            if data is None:
                result["error"] = "SQL执行失败"
                return result

            result["success"] = True
            result["data"] = data
            result["row_count"] = len(data)
            return result
        except Exception as e:
            result["error"] = str(e)
            return result


class AnalyzeResultsArgs(BaseModel):
    sql: str = Field(description="执行的SQL语句")
    results: List[Dict[str, Any]] = Field(description="查询结果数据")
    question: str = Field(description="用户的原始问题")


class FormatResultsArgs(BaseModel):
    results: List[Dict[str, Any]] = Field(description="要格式化的查询结果")
    max_rows: int = Field(default=10, description="最多显示的行数")


class ResultAnalyzer(Tool):
    name = "result_analyzer"
    description = "分析查询结果生成总结"
    access_groups = ["analysis"]
    categories = ["analysis"]

    def __init__(self):
        self.llm = LLMClient()

    def get_args_schema(self) -> Type[BaseModel]:
        return AnalyzeResultsArgs

    def execute(self, context: ToolContext, args: dict) -> ToolResult:
        sql = args.get("sql", "")
        results = args.get("results", [])
        question = args.get("question", "")
        return self.analyze_results_tool(sql, results, question)

    def analyze_results_tool(self, sql: str, results: List[Dict[str, Any]], question: str) -> ToolResult:
        try:
            analysis = self.analyze_results(sql, results, question)
            return ToolResult(success=True, data={"analysis": analysis})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def analyze_results(self, sql: str, results: List[Dict[str, Any]], question: str) -> str:
        try:
            results_str = str(results)

            prompt = f"""用户问题: {question}

执行的SQL: {sql}

查询结果: {results_str}

请基于以上信息，用中文对查询结果进行分析和总结。
分析应包括：
1. 查询结果的主要发现
2. 数据的趋势或模式
3. 对用户问题的直接回答

请用清晰、友好的语言表达。"""

            return self.llm.generate(prompt)
        except Exception as e:
            print(f"结果分析失败: {e}")
            return "无法分析结果"

    def format_results_tool(self, results: List[Dict[str, Any]], max_rows: int = 100) -> ToolResult:
        try:
            formatted = self.format_results(results, max_rows)
            return ToolResult(success=True, data={"formatted": formatted})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def format_results(self, results: List[Dict[str, Any]], max_rows: int = 10) -> str:
        if not results:
            return "查询结果为空"

        if len(results) > max_rows:
            display_results = results[:max_rows]
            remaining = len(results) - max_rows
        else:
            display_results = results
            remaining = 0

        if isinstance(display_results[0], dict):
            columns = list(display_results[0].keys())
            header = " | ".join(columns)
            separator = "-" * len(header)

            rows = []
            for row in display_results:
                row_str = " | ".join(str(row[col]) for col in columns)
                rows.append(row_str)

            result_str = "\n".join([header, separator] + rows)
            if remaining > 0:
                result_str += f"\n... 还有 {remaining} 行未显示"
            return result_str
        else:
            return str(results)

    def get_statistics_tool(self, results: List[Dict[str, Any]]) -> ToolResult:
        try:
            stats = self.get_statistics(results)
            return ToolResult(success=True, data={"statistics": stats})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def get_statistics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not results or not isinstance(results[0], dict):
            return {}

        stats = {}
        for key in results[0].keys():
            values = [row[key] for row in results if row[key] is not None]

            if not values:
                continue

            if isinstance(values[0], (int, float)):
                stats[key] = {
                    "count": len(values),
                    "sum": sum(values),
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values)
                }
            else:
                stats[key] = {
                    "count": len(values),
                    "unique": len(set(values))
                }

        return stats