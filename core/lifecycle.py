from abc import ABC, abstractmethod
from typing import Optional, Any, Dict, List, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum

if TYPE_CHECKING:
    from tools.tool_base import Tool, ToolContext, ToolResult


class HookPhase(Enum):
    BEFORE_MESSAGE = "before_message"
    AFTER_MESSAGE = "after_message"
    BEFORE_TOOL = "before_tool"
    AFTER_TOOL = "after_tool"


@dataclass
class HookResult:
    modified: bool = False
    data: Any = None
    error: Optional[str] = None

    @classmethod
    def unchanged(cls) -> "HookResult":
        return cls(modified=False)

    @classmethod
    def modified_result(cls, data: Any) -> "HookResult":
        return cls(modified=True, data=data)

    @classmethod
    def error_result(cls, error: str) -> "HookResult":
        return cls(modified=False, error=error)


class LifecycleHook(ABC):
    name: str = "base_hook"
    phase: HookPhase = HookPhase.BEFORE_MESSAGE

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> HookResult:
        pass

    async def before_message(self, message: str) -> Optional[str]:
        return None

    async def after_message(self, message: str) -> Optional[str]:
        return None

    async def before_tool(self, tool: "Tool", context: "ToolContext") -> None:
        pass

    async def after_tool(self, result: "ToolResult") -> Optional["ToolResult"]:
        return None


class BeforeMessageHook(LifecycleHook):
    phase = HookPhase.BEFORE_MESSAGE

    @abstractmethod
    async def before_message(self, message: str) -> Optional[str]:
        pass

    async def execute(self, context: Dict[str, Any]) -> HookResult:
        message = context.get("message", "")
        result = await self.before_message(message)
        if result is not None and result != message:
            return HookResult.modified_result(result)
        return HookResult.unchanged()


class AfterMessageHook(LifecycleHook):
    phase = HookPhase.AFTER_MESSAGE

    @abstractmethod
    async def after_message(self, message: str) -> Optional[str]:
        pass

    async def execute(self, context: Dict[str, Any]) -> HookResult:
        message = context.get("message", "")
        result = await self.after_message(message)
        if result is not None:
            return HookResult.modified_result(result)
        return HookResult.unchanged()


class BeforeToolHook(LifecycleHook):
    phase = HookPhase.BEFORE_TOOL

    @abstractmethod
    async def before_tool(self, tool: "Tool", context: "ToolContext") -> None:
        pass

    async def execute(self, context: Dict[str, Any]) -> HookResult:
        tool = context.get("tool")
        tool_context = context.get("tool_context")
        if tool and tool_context:
            await self.before_tool(tool, tool_context)
        return HookResult.unchanged()


class AfterToolHook(LifecycleHook):
    phase = HookPhase.AFTER_TOOL

    @abstractmethod
    async def after_tool(self, result: "ToolResult") -> Optional["ToolResult"]:
        pass

    async def execute(self, context: Dict[str, Any]) -> HookResult:
        result = context.get("result")
        if result:
            modified_result = await self.after_tool(result)
            if modified_result is not None:
                return HookResult.modified_result(modified_result)
        return HookResult.unchanged()


class HookRegistry:
    _hooks: Dict[HookPhase, List[LifecycleHook]] = {
        HookPhase.BEFORE_MESSAGE: [],
        HookPhase.AFTER_MESSAGE: [],
        HookPhase.BEFORE_TOOL: [],
        HookPhase.AFTER_TOOL: [],
    }

    @classmethod
    def register(cls, hook: LifecycleHook) -> None:
        cls._hooks[hook.phase].append(hook)

    @classmethod
    def unregister(cls, hook: LifecycleHook) -> None:
        if hook in cls._hooks[hook.phase]:
            cls._hooks[hook.phase].remove(hook)

    @classmethod
    def get_hooks(cls, phase: HookPhase) -> List[LifecycleHook]:
        return list(cls._hooks.get(phase, []))

    @classmethod
    def clear(cls) -> None:
        for phase in cls._hooks:
            cls._hooks[phase].clear()

    @classmethod
    async def execute_phase(
        cls, phase: HookPhase, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        hooks = cls.get_hooks(phase)
        for hook in hooks:
            result = await hook.execute(context)
            if result.modified and result.data is not None:
                context[f"modified_by_{hook.name}"] = True
                if phase in (HookPhase.BEFORE_MESSAGE, HookPhase.AFTER_MESSAGE):
                    context["message"] = result.data
                elif phase == HookPhase.AFTER_TOOL:
                    context["result"] = result.data
        return context


class LoggingHook(BeforeMessageHook):
    name = "logging_hook"

    def __init__(self):
        self.name = "logging_hook"

    async def before_message(self, message: str) -> Optional[str]:
        print(f"[Hook] Before message: {message[:100]}...")
        return None


class QuotaCheckHook(BeforeMessageHook):
    name = "quota_check_hook"

    def __init__(self, max_requests_per_minute: int = 60):
        self.name = "quota_check_hook"
        self.max_requests_per_minute = max_requests_per_minute
        self.request_counts: Dict[str, List[float]] = {}

    async def before_message(self, message: str) -> Optional[str]:
        user_id = "default"
        import time
        current_time = time.time()

        if user_id not in self.request_counts:
            self.request_counts[user_id] = []

        self.request_counts[user_id] = [
            t for t in self.request_counts[user_id] if current_time - t < 60
        ]

        if len(self.request_counts[user_id]) >= self.max_requests_per_minute:
            print(f"[Hook] Quota exceeded for user {user_id}")
            return None

        self.request_counts[user_id].append(current_time)
        return None


class TimingHook(AfterToolHook):
    name = "timing_hook"

    def __init__(self):
        self.name = "timing_hook"
        self.tool_timings: Dict[str, float] = {}

    async def after_tool(self, result: "ToolResult") -> Optional["ToolResult"]:
        tool_name = result.metadata.get("tool_name", "unknown")
        start_time = result.metadata.get("start_time")

        if start_time:
            import time
            elapsed = time.time() - start_time
            self.tool_timings[tool_name] = elapsed
            print(f"[Hook] Tool '{tool_name}' took {elapsed:.3f}s")

        return None
