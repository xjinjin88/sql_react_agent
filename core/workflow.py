from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable, Awaitable
from enum import Enum

from tools.tool_base import ToolContext


class WorkflowTriggerResult(Enum):
    HANDLED = "handled"
    NOT_TRIGGERED = "not_triggered"
    ERROR = "error"


@dataclass
class WorkflowResult:
    should_skip_llm: bool = False
    components: Optional[List[Any]] = None
    conversation_mutation: Optional[Callable[[Any], Awaitable[None]]] = None
    error: Optional[str] = None


class WorkflowHandler(ABC):
    @abstractmethod
    async def try_handle(
        self, agent: Any, user: Any, conversation: Any, message: str
    ) -> WorkflowResult:
        pass

    @abstractmethod
    async def get_starter_ui(
        self, agent: Any, user: Any, conversation: Any
    ) -> Optional[List[Any]]:
        pass


class DefaultWorkflowHandler(WorkflowHandler):
    def __init__(self):
        self.workflows: Dict[str, Callable[..., Awaitable[WorkflowResult]]] = {}

    def register_workflow(
        self, trigger: str, handler: Callable[..., Awaitable[WorkflowResult]]
    ) -> None:
        self.workflows[trigger] = handler

    async def try_handle(
        self, agent: Any, user: Any, conversation: Any, message: str
    ) -> WorkflowResult:
        message_lower = message.lower().strip()

        for trigger, handler in self.workflows.items():
            if trigger.lower() in message_lower:
                try:
                    result = await handler(agent=agent, user=user, conversation=conversation, message=message)
                    if result.should_skip_llm:
                        return result
                except Exception as e:
                    return WorkflowResult(
                        should_skip_llm=False,
                        error=f"Workflow error: {str(e)}"
                    )

        return WorkflowResult(should_skip_llm=False)

    async def get_starter_ui(
        self, agent: Any, user: Any, conversation: Any
    ) -> Optional[List[Any]]:
        return None


class ConversationWorkflow:
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.steps: List[Callable[..., Awaitable[WorkflowResult]]] = []

    def add_step(self, step: Callable[..., Awaitable[WorkflowResult]]) -> "ConversationWorkflow":
        self.steps.append(step)
        return self

    async def execute(
        self, agent: Any, user: Any, conversation: Any, context: ToolContext
    ) -> WorkflowResult:
        results = []
        for step in self.steps:
            try:
                result = await step(agent=agent, user=user, conversation=conversation, context=context)
                results.append(result)
                if result.should_skip_llm:
                    return result
            except Exception as e:
                return WorkflowResult(
                    should_skip_llm=False,
                    error=f"Step {len(results)} error: {str(e)}"
                )

        return WorkflowResult(should_skip_llm=False)


class WorkflowRegistry:
    _workflows: Dict[str, ConversationWorkflow] = {}

    @classmethod
    def register(cls, name: str, workflow: ConversationWorkflow) -> None:
        cls._workflows[name] = workflow

    @classmethod
    def get(cls, name: str) -> Optional[ConversationWorkflow]:
        return cls._workflows.get(name)

    @classmethod
    def list_all(cls) -> List[str]:
        return list(cls._workflows.keys())


class QuickQueryWorkflow:
    QUICK_QUERIES = {
        "show tables": "SHOW TABLES",
        "show me the tables": "SHOW TABLES",
        "what tables exist": "SHOW TABLES",
        "list all tables": "SHOW TABLES",
    }

    @classmethod
    async def try_handle(cls, message: str, agent: Any) -> Optional[WorkflowResult]:
        message_lower = message.lower().strip()

        for trigger, sql in cls.QUICK_QUERIES.items():
            if trigger in message_lower:
                try:
                    from tools import ToolRegistry
                    context = ToolContext()

                    tool = ToolRegistry.get_tool("sql_executor")
                    if tool:
                        result = await tool.execute(context, {"sql": sql})
                        if result.success:
                            return WorkflowResult(
                                should_skip_llm=True,
                                components=[cls._format_result(result.data)]
                            )
                except Exception as e:
                    return WorkflowResult(
                        should_skip_llm=False,
                        error=str(e)
                    )

        return None

    @classmethod
    def _format_result(cls, data: Any) -> Dict[str, Any]:
        return {
            "type": "table",
            "data": data,
            "message": "Query executed successfully"
        }


class StarterUIBuilder:
    @staticmethod
    async def build(agent: Any, user: Any, conversation: Any) -> Optional[List[Any]]:
        from dataclasses import dataclass

        @dataclass
        class StarterComponent:
            type: str = "starter"
            message: str = ""
            options: List[Dict[str, str]] = field(default_factory=list)

        options = [
            {"label": "Show Tables", "message": "show tables"},
            {"label": "Describe a Table", "message": "describe "},
            {"label": "Count Records", "message": "how many "},
        ]

        return [
            StarterComponent(
                type="starter",
                message="Welcome! What would you like to know about your database?",
                options=options
            )
        ]
