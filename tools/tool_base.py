from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from typing import Type, List, Dict, Any, Optional, Callable
import json


class ToolResult(BaseModel):
    success: bool = True
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "metadata": self.metadata
        }


class ToolContext(BaseModel):
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    tools_registry: Optional[Any] = None
    custom_context: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True


class Tool(ABC):
    name: str = ""
    description: str = ""
    access_groups: List[str] = []
    categories: List[str] = []

    @abstractmethod
    def get_args_schema(self) -> Type[BaseModel]:
        pass

    @abstractmethod
    def execute(self, context: ToolContext, args: dict) -> ToolResult:
        pass

    def get_schema_json(self) -> dict:
        schema = self.get_args_schema()
        return schema.model_json_schema()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "access_groups": self.access_groups,
            "categories": self.categories,
            "args_schema": self.get_schema_json()
        }


class ToolRegistry:
    _tools: Dict[str, Tool] = {}
    _categories: Dict[str, List[str]] = {}

    @classmethod
    def register(cls, tool: Tool, categories: List[str] = None) -> None:
        if not tool.name:
            raise ValueError("Tool must have a name")
        if tool.name in cls._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")

        cls._tools[tool.name] = tool

        if categories:
            for category in categories:
                if category not in cls._categories:
                    cls._categories[category] = []
                cls._categories[category].append(tool.name)

    @classmethod
    def unregister(cls, tool_name: str) -> bool:
        if tool_name not in cls._tools:
            return False

        tool = cls._tools.pop(tool_name)
        for category, tools in cls._categories.items():
            if tool_name in tools:
                tools.remove(tool_name)

        return True

    @classmethod
    def get_tool(cls, tool_name: str) -> Optional[Tool]:
        return cls._tools.get(tool_name)

    @classmethod
    def get_all_tools(cls) -> List[Tool]:
        return list(cls._tools.values())

    @classmethod
    def get_tools_by_category(cls, category: str) -> List[Tool]:
        tool_names = cls._categories.get(category, [])
        return [cls._tools[name] for name in tool_names if name in cls._tools]

    @classmethod
    def get_all_categories(cls) -> List[str]:
        return list(cls._categories.keys())

    @classmethod
    def generate_tools_description(cls) -> str:
        lines = ["你可以使用以下工具：", ""]
        for tool in cls._tools.values():
            lines.append(f"## {tool.name}")
            lines.append(f"描述: {tool.description}")
            schema = tool.get_args_schema()
            lines.append(f"参数类型:")
            for field_name, field_info in schema.model_fields.items():
                field_type = field_info.annotation if hasattr(field_info, 'annotation') else str(field_info)
                description = field_info.description or ""
                lines.append(f"  - {field_name}: {field_type} - {description}")
            lines.append("")
        return "\n".join(lines)

    @classmethod
    def generate_tools_json(cls) -> str:
        tools_list = [tool.to_dict() for tool in cls._tools.values()]
        return json.dumps(tools_list, ensure_ascii=False, indent=2)

    @classmethod
    def clear(cls) -> None:
        cls._tools.clear()
        cls._categories.clear()

    @classmethod
    def execute_tool(cls, tool_name: str, context: ToolContext, args: dict) -> ToolResult:
        tool = cls.get_tool(tool_name)
        if not tool:
            return ToolResult(success=False, error=f"Tool '{tool_name}' not found")

        try:
            schema = tool.get_args_schema()
            validated_args = schema(**args)
            return tool.execute(context, validated_args.model_dump())
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    @classmethod
    def get_tools_by_access_group(cls, access_group: str) -> List[Tool]:
        return [
            tool for tool in cls._tools.values()
            if access_group in tool.access_groups
        ]