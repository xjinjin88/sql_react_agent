import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class SpanStatus(Enum):
    STARTED = "started"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class Span:
    name: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    status: SpanStatus = SpanStatus.STARTED
    attributes: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def set_status(self, status: SpanStatus, error: Optional[str] = None) -> None:
        self.status = status
        self.error = error

    def end(self) -> None:
        self.end_time = time.time()

    def duration_ms(self) -> Optional[float]:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return None


@dataclass
class Metric:
    name: str
    value: float
    unit: str
    timestamp: float = field(default_factory=time.time)
    tags: Dict[str, str] = field(default_factory=dict)


class ObservabilityProvider(ABC):
    @abstractmethod
    async def create_span(self, name: str, attributes: Dict[str, Any] = None) -> Span:
        pass

    @abstractmethod
    async def end_span(self, span: Span) -> None:
        pass

    @abstractmethod
    async def record_metric(
        self, name: str, value: float, unit: str, tags: Dict[str, str] = None
    ) -> None:
        pass

    @abstractmethod
    async def log(self, level: str, message: str, **kwargs) -> None:
        pass


class ConsoleObservabilityProvider(ObservabilityProvider):
    def __init__(self):
        self.spans: List[Span] = []
        self.metrics: List[Metric] = []

    async def create_span(self, name: str, attributes: Dict[str, Any] = None) -> Span:
        span = Span(name=name, attributes=attributes or {})
        self.spans.append(span)
        print(f"[Span] Started: {name}")
        return span

    async def end_span(self, span: Span) -> None:
        span.end()
        duration = span.duration_ms()
        print(f"[Span] Ended: {span.name} ({duration:.2f}ms)")
        if span.status == SpanStatus.ERROR:
            print(f"[Span] Error: {span.error}")

    async def record_metric(
        self, name: str, value: float, unit: str, tags: Dict[str, str] = None
    ) -> None:
        metric = Metric(name=name, value=value, unit=unit, tags=tags or {})
        self.metrics.append(metric)
        tags_str = ", ".join(f"{k}={v}" for k, v in (tags or {}).items())
        print(f"[Metric] {name}={value}{unit} [{tags_str}]")

    async def log(self, level: str, message: str, **kwargs) -> None:
        timestamp = datetime.now().isoformat()
        extra = ", ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
        print(f"[{timestamp}] {level.upper()}: {message} {extra}")


class MetricsCollector:
    def __init__(self):
        self.metrics: Dict[str, List[float]] = {}
        self.counters: Dict[str, int] = {}

    def record(self, name: str, value: float) -> None:
        if name not in self.metrics:
            self.metrics[name] = []
        self.metrics[name].append(value)

    def increment(self, name: str, delta: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + delta

    def get_average(self, name: str) -> Optional[float]:
        values = self.metrics.get(name)
        if values:
            return sum(values) / len(values)
        return None

    def get_count(self, name: str) -> int:
        return self.counters.get(name, 0)

    def get_all_metrics(self) -> Dict[str, Any]:
        result = {}
        for name, values in self.metrics.items():
            if values:
                result[name] = {
                    "count": len(values),
                    "sum": sum(values),
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                }
        result["_counters"] = dict(self.counters)
        return result

    def reset(self) -> None:
        self.metrics.clear()
        self.counters.clear()


class StructuredLogger:
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(name)

    def _format_message(self, message: str, **kwargs) -> str:
        parts = [message]
        if kwargs:
            parts.append(" | ")
            parts.append(
                ", ".join(f"{k}={self._format_value(v)}" for k, v in kwargs.items())
            )
        return "".join(parts)

    def _format_value(self, value: Any) -> str:
        if isinstance(value, (str, int, float, bool)):
            return str(value)
        elif isinstance(value, dict):
            return str(value)
        else:
            return repr(value)

    def debug(self, message: str, **kwargs) -> None:
        self.logger.debug(self._format_message(message, **kwargs))

    def info(self, message: str, **kwargs) -> None:
        self.logger.info(self._format_message(message, **kwargs))

    def warning(self, message: str, **kwargs) -> None:
        self.logger.warning(self._format_message(message, **kwargs))

    def error(self, message: str, **kwargs) -> None:
        self.logger.error(self._format_message(message, **kwargs))

    def critical(self, message: str, **kwargs) -> None:
        self.logger.critical(self._format_message(message, **kwargs))


class AgentMetrics:
    def __init__(self):
        self.total_messages: int = 0
        self.total_tool_calls: int = 0
        self.total_errors: int = 0
        self.total_latency_ms: float = 0.0
        self.tool_call_counts: Dict[str, int] = {}
        self.error_types: Dict[str, int] = {}

    def record_message(self, latency_ms: float) -> None:
        self.total_messages += 1
        self.total_latency_ms += latency_ms

    def record_tool_call(self, tool_name: str, success: bool, latency_ms: float) -> None:
        self.total_tool_calls += 1
        self.tool_call_counts[tool_name] = self.tool_call_counts.get(tool_name, 0) + 1
        if not success:
            self.total_errors += 1

    def record_error(self, error_type: str) -> None:
        self.error_types[error_type] = self.error_types.get(error_type, 0) + 1
        self.total_errors += 1

    def get_summary(self) -> Dict[str, Any]:
        avg_latency = (
            self.total_latency_ms / self.total_messages if self.total_messages > 0 else 0
        )
        return {
            "total_messages": self.total_messages,
            "total_tool_calls": self.total_tool_calls,
            "total_errors": self.total_errors,
            "average_latency_ms": avg_latency,
            "tool_call_counts": dict(self.tool_call_counts),
            "error_types": dict(self.error_types),
        }

    def reset(self) -> None:
        self.total_messages = 0
        self.total_tool_calls = 0
        self.total_errors = 0
        self.total_latency_ms = 0.0
        self.tool_call_counts.clear()
        self.error_types.clear()
