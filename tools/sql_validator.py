from pydantic import BaseModel, Field
from typing import Type, Optional, List
import re
from tools.llm_client import LLMClient
from tools.tool_base import Tool, ToolResult, ToolContext


class ValidateSQLArgs(BaseModel):
    sql: str = Field(description="要验证的SQL语句")


class ExplainSQLArgs(BaseModel):
    sql: str = Field(description="要解释的SQL语句")
    schema: str = Field(description="数据库表结构信息")


class SQLValidator(Tool):
    name = "sql_validator"
    description = "验证SQL安全性和语法"
    access_groups = ["sql"]
    categories = ["sql"]

    dangerous_patterns = [
        r"\bDROP\s+TABLE\b",
        r"\bDROP\s+DATABASE\b",
        r"\bDELETE\s+FROM\b",
        r"\bTRUNCATE\s+TABLE\b",
        r"\bUPDATE\s+\w+\b",
        r"\bINSERT\s+INTO\b",
        r"\bALTER\s+TABLE\b",
        r"\bCREATE\s+TABLE\b",
        r"\bDROP\s+INDEX\b",
        r"\bEXEC\b",
        r"\bEXECUTE\b",
        r";.*--",
        r"--.*;"
    ]

    def __init__(self):
        self.patterns = [re.compile(pattern, re.IGNORECASE) for pattern in self.dangerous_patterns]
        self.llm = LLMClient()

    def get_args_schema(self) -> Type[BaseModel]:
        return ValidateSQLArgs

    def execute(self, context: ToolContext, args: dict) -> ToolResult:
        sql = args.get("sql", "")
        return self.validate_sql_tool(sql)

    def validate_sql_tool(self, sql: str) -> ToolResult:
        errors: List[str] = []
        warnings: List[str] = []

        if not sql.strip():
            return ToolResult(success=False, error="SQL语句为空")

        if not self.is_safe(sql):
            return ToolResult(
                success=False,
                error="检测到危险SQL操作",
                metadata={"dangerous": True}
            )

        if not sql.strip().upper().startswith("SELECT"):
            warnings.append("建议只使用SELECT查询")

        validation_result = {
            "valid": True,
            "errors": errors,
            "warnings": warnings
        }

        return ToolResult(
            success=True,
            data=validation_result,
            metadata={"warnings_count": len(warnings)}
        )

    def is_safe(self, sql: str) -> bool:
        for pattern in self.patterns:
            if pattern.search(sql):
                return False
        return True

    def validate_sql(self, sql: str) -> dict:
        result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }

        if not sql.strip():
            result["valid"] = False
            result["errors"].append("SQL语句为空")
            return result

        if not self.is_safe(sql):
            result["valid"] = False
            result["errors"].append("检测到危险SQL操作")
            return result

        if not sql.strip().upper().startswith("SELECT"):
            result["warnings"].append("建议只使用SELECT查询")

        return result

    def explain_sql(self, sql: str, schema: str) -> Optional[str]:
        try:
            prompt = f"""解释以下SQL查询的含义：

SQL: {sql}

数据库表结构: {schema}

请用中文清晰地解释这个SQL查询做了什么。"""

            return self.llm.generate(prompt)
        except Exception as e:
            print(f"SQL解释失败: {e}")
            return None

    def explain_sql_tool(self, sql: str, schema: str) -> ToolResult:
        try:
            explanation = self.explain_sql(sql, schema)
            if not explanation:
                return ToolResult(success=False, error="SQL解释失败")
            return ToolResult(success=True, data={"explanation": explanation})
        except Exception as e:
            return ToolResult(success=False, error=str(e))