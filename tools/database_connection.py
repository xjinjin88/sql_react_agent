
# 数据库连接工具
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel, Field
from typing import Type, List, Dict, Any, Optional
from decimal import Decimal
from datetime import date, datetime
from config import Config
from tools.tool_base import Tool, ToolResult, ToolContext


def _convert_special_types(value):
    """将特殊类型转换为可序列化的类型"""
    if isinstance(value, Decimal):
        return float(value)
    elif isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


class DatabaseConnection:
    def __init__(self, db_type: str = "sqlite"):
        self.db_type = db_type
        self.engine = None
        self.connection = None
        self.inspector = None

    def connect(self) -> bool:
        try:
            database_url = Config.get_database_url(self.db_type)
            self.engine = create_engine(database_url)
            self.connection = self.engine.connect()
            self.inspector = inspect(self.engine)
            return True
        except SQLAlchemyError as e:
            print(f"数据库连接失败: {e}")
            return False

    def disconnect(self):
        if self.connection:
            self.connection.close()
        if self.engine:
            self.engine.dispose()

    def get_tables(self) -> List[str]:
        if not self.inspector:
            return []
        return self.inspector.get_table_names()

    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        if not self.inspector:
            return {}

        columns = []
        try:
            for col in self.inspector.get_columns(table_name):
                columns.append({
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col["nullable"],
                    "default": col["default"]
                })

            foreign_keys = []
            for fk in self.inspector.get_foreign_keys(table_name):
                foreign_keys.append({
                    "constrained_columns": fk["constrained_columns"],
                    "referred_table": fk["referred_table"],
                    "referred_columns": fk["referred_columns"]
                })

            indexes = []
            for idx in self.inspector.get_indexes(table_name):
                indexes.append({
                    "name": idx["name"],
                    "columns": idx["column_names"],
                    "unique": idx["unique"]
                })

            return {
                "table_name": table_name,
                "columns": columns,
                "foreign_keys": foreign_keys,
                "indexes": indexes
            }
        except SQLAlchemyError as e:
            print(f"获取表结构失败: {e}")
            return {}

    def get_database_schema(self) -> Dict[str, Any]:
        tables = self.get_tables()
        schema = {}
        for table in tables:
            schema[table] = self.get_table_schema(table)
        return schema

    def execute_query(self, query: str) -> Optional[List[Dict[str, Any]]]:
        if not self.connection:
            return None

        try:
            result = self.connection.execute(text(query))
            if result.returns_rows:
                columns = result.keys()
                rows = result.fetchall()
                # 转换特殊类型为可序列化类型
                return [{col: _convert_special_types(val) for col, val in zip(columns, row)} for row in rows]
            else:
                self.connection.commit()
                return [{"status": "success", "row_count": result.rowcount}]
        except SQLAlchemyError as e:
            print(f"SQL执行失败: {e}")
            return None


class ConnectArgs(BaseModel):
    db_type: str = Field(default="sqlite", description="数据库类型: mysql, postgres, sqlite, mssql")


class GetSchemaArgs(BaseModel):
    pass


class DisconnectArgs(BaseModel):
    pass


class DatabaseConnectionTool(Tool):
    name = "database_connection"
    description = "连接数据库或获取表结构"
    access_groups = ["database"]
    categories = ["database"]

    def __init__(self):
        self.connection: Optional[DatabaseConnection] = None

    def get_args_schema(self) -> Type[BaseModel]:
        return ConnectArgs

    def execute(self, context: ToolContext, args: dict) -> ToolResult:
        return self.connect(args.get("db_type", "sqlite"))

    def connect(self, db_type: str = "sqlite") -> ToolResult:
        try:
            self.connection = DatabaseConnection(db_type)
            if self.connection.connect():
                return ToolResult(
                    success=True,
                    data={"message": f"成功连接到{db_type}数据库", "db_type": db_type}
                )
            else:
                return ToolResult(success=False, error=f"连接{db_type}数据库失败")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def disconnect(self) -> ToolResult:
        try:
            if self.connection:
                self.connection.disconnect()
                self.connection = None
                return ToolResult(success=True, data={"message": "已断开数据库连接"})
            return ToolResult(success=False, error="没有活跃的数据库连接")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def get_schema(self) -> ToolResult:
        try:
            if not self.connection:
                return ToolResult(success=False, error="请先连接数据库")

            schema = self.connection.get_database_schema()
            if not schema:
                return ToolResult(success=True, data={"schema": {}, "message": "数据库中没有表"})

            result = "数据库表结构:\n"
            for table_name, table_info in schema.items():
                result += f"\n表名: {table_name}\n"
                result += "字段:\n"
                for col in table_info["columns"]:
                    nullable = "NULL" if col["nullable"] else "NOT NULL"
                    result += f"  - {col['name']}: {col['type']} ({nullable})"
                    if col["default"]:
                        result += f", 默认值: {col['default']}"
                    result += "\n"

                if table_info["foreign_keys"]:
                    result += "外键:\n"
                    for fk in table_info["foreign_keys"]:
                        result += f"  - {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}\n"

                if table_info["indexes"]:
                    result += "索引:\n"
                    for idx in table_info["indexes"]:
                        unique = "UNIQUE" if idx["unique"] else ""
                        result += f"  - {idx['name']}: {idx['columns']} {unique}\n"

            return ToolResult(success=True, data={"schema": schema, "formatted": result})
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    def set_connection(self, connection: DatabaseConnection):
        self.connection = connection

    def get_connection(self) -> Optional[DatabaseConnection]:
        return self.connection