import time
from typing import Optional, List, Dict, Any, Callable, Awaitable
from tools.database_connection import DatabaseConnectionTool
from tools.sql_generator import SQLGenerator
from tools.sql_validator import SQLValidator
from tools.sql_executor import SQLExecutor, ResultAnalyzer
from tools.table_retriever import TableRetrieverTool
from tools.table_explorer import TableExplorer
from tools.tool_base import ToolRegistry, ToolContext, ToolResult

from core.lifecycle import (
    LifecycleHook,
    HookRegistry,
    HookPhase,
    BeforeMessageHook,
    AfterMessageHook,
    BeforeToolHook,
    AfterToolHook,
    HookResult,
)
from core.observability import (
    ObservabilityProvider,
    ConsoleObservabilityProvider,
    StructuredLogger,
    AgentMetrics,
    MetricsCollector,
)
from core.workflow import (
    WorkflowHandler,
    DefaultWorkflowHandler,
    WorkflowResult,
)


class SQLAgent:
    def __init__(
        self,
        metadata_path: str = "tables_metadata.json",
        observability_provider: Optional[ObservabilityProvider] = None,
        workflow_handler: Optional[WorkflowHandler] = None,
        lifecycle_hooks: Optional[List[LifecycleHook]] = None,
    ):
        self.db_tool = DatabaseConnectionTool()
        self.sql_generator = SQLGenerator()
        self.sql_validator = SQLValidator()
        self.sql_executor = SQLExecutor()
        self.result_analyzer = ResultAnalyzer()
        self.table_retriever = TableRetrieverTool(metadata_path)
        self.table_explorer = TableExplorer()
        self.current_db_type = None

        self.observability = observability_provider or ConsoleObservabilityProvider()
        self.workflow_handler = workflow_handler or DefaultWorkflowHandler()
        self.lifecycle_hooks = lifecycle_hooks or []
        self.metrics = AgentMetrics()
        self.logger = StructuredLogger("SQLAgent")

        for hook in self.lifecycle_hooks:
            HookRegistry.register(hook)

        self._setup_registry()

    def _setup_registry(self):
        ToolRegistry.clear()
        ToolRegistry.register(self.db_tool, categories=["database"])
        ToolRegistry.register(self.sql_generator, categories=["sql"])
        ToolRegistry.register(self.sql_validator, categories=["sql"])
        ToolRegistry.register(self.sql_executor, categories=["sql"])
        ToolRegistry.register(self.result_analyzer, categories=["analysis"])
        ToolRegistry.register(self.table_retriever, categories=["retrieval"])
        ToolRegistry.register(self.table_explorer, categories=["exploration"])

    def get_registry(self) -> ToolRegistry:
        return ToolRegistry

    def get_tools_description(self) -> str:
        return ToolRegistry.generate_tools_description()

    def connect_database(self, db_type: str) -> str:
        result = self.db_tool.connect(db_type)
        if result.success:
            self.current_db_type = db_type
            db_connection = self.db_tool.get_connection()
            self.sql_executor.set_connection(db_connection)
            self.table_explorer.set_db_connection(db_connection)
        return result.data.get("message", str(result)) if result.success else result.error

    def disconnect_database(self) -> str:
        result = self.db_tool.disconnect()
        self.current_db_type = None
        return result.data.get("message", str(result)) if result.success else result.error

    def get_database_schema(self) -> str:
        result = self.db_tool.get_schema()
        return result.data.get("formatted", str(result)) if result.success else result.error

    async def _execute_with_hooks(
        self,
        tool_name: str,
        context: ToolContext,
        args: dict,
    ) -> ToolResult:
        span = await self.observability.create_span(
            "tool.execute",
            attributes={"tool": tool_name, "args": str(args)[:100]}
        )

        context_dict = {"tool": tool_name, "context": context, "args": args}
        await HookRegistry.execute_phase(HookPhase.BEFORE_TOOL, context_dict)

        start_time = time.time()
        tool = ToolRegistry.get_tool(tool_name)

        if not tool:
            result = ToolResult(success=False, error=f"Tool '{tool_name}' not found")
        else:
            result = tool.execute(context, args)

        result.metadata["start_time"] = start_time
        result.metadata["tool_name"] = tool_name
        result.metadata["elapsed_ms"] = (time.time() - start_time) * 1000

        await self.observability.end_span(span)

        await HookRegistry.execute_phase(HookPhase.AFTER_TOOL, {"result": result})

        return result

    async def run_query_async(self, question: str) -> dict:
        start_time = time.time()
        span = await self.observability.create_span(
            "agent.run_query_async",
            attributes={"question": question[:100]}
        )

        await HookRegistry.execute_phase(
            HookPhase.BEFORE_MESSAGE,
            {"message": question}
        )

        result = {
            "status": "completed",
            "steps": [],
            "sql": None,
            "validation": None,
            "execution_result": None,
            "analysis": None,
            "error": None
        }

        if not self.current_db_type:
            result["status"] = "error"
            result["error"] = "请先连接数据库"
            await self.observability.end_span(span)
            return result

        schema_result = self.db_tool.get_schema()
        result["steps"].append("获取数据库表结构")

        if not schema_result.success:
            result["status"] = "error"
            result["error"] = schema_result.error
            await self.observability.end_span(span)
            return result

        schema = schema_result.data.get("formatted", "")

        sql_result = self.sql_generator.generate_sql(question, schema)
        if not sql_result:
            result["status"] = "error"
            result["error"] = "无法生成SQL语句"
            await self.observability.end_span(span)
            return result

        result["sql"] = sql_result
        result["steps"].append(f"生成SQL: {sql_result}")

        validation = self.sql_validator.validate_sql(sql_result)
        result["validation"] = validation
        result["steps"].append(f"SQL验证: {'通过' if validation['valid'] else '失败'}")

        if not validation["valid"]:
            result["status"] = "error"
            result["error"] = "; ".join(validation["errors"])
            await self.observability.end_span(span)
            return result

        execution_result = self.sql_executor.execute_sql(sql_result)
        result["execution_result"] = execution_result
        result["steps"].append(f"执行SQL: {'成功' if execution_result['success'] else '失败'}")

        if not execution_result["success"]:
            result["status"] = "error"
            result["error"] = execution_result["error"]
            await self.observability.end_span(span)
            return result

        analysis = self.result_analyzer.analyze_results(
            sql_result,
            execution_result["data"],
            question
        )
        result["analysis"] = analysis
        result["steps"].append("分析查询结果")

        elapsed_ms = (time.time() - start_time) * 1000
        self.metrics.record_message(elapsed_ms)
        await self.observability.record_metric(
            "agent.query.duration", elapsed_ms, "ms", {"type": "sync_query"}
        )

        await HookRegistry.execute_phase(
            HookPhase.AFTER_MESSAGE,
            {"message": question, "result": result}
        )

        await self.observability.end_span(span)
        return result

    async def run_query_with_retrieval_async(self, question: str, top_k: int = 3) -> dict:
        start_time = time.time()
        span = await self.observability.create_span(
            "agent.run_query_with_retrieval_async",
            attributes={"question": question[:100], "top_k": top_k}
        )

        await HookRegistry.execute_phase(
            HookPhase.BEFORE_MESSAGE,
            {"message": question}
        )

        result = {
            "status": "completed",
            "steps": [],
            "sql": None,
            "validation": None,
            "execution_result": None,
            "analysis": None,
            "error": None,
            "retrieved_tables": []
        }

        if not self.current_db_type:
            result["status"] = "error"
            result["error"] = "请先连接数据库"
            await self.observability.end_span(span)
            return result

        result["steps"].append("检索相关表")
        selected_schema = self.table_retriever.select_tables_for_query(question, top_k)

        if "未找到相关表" in selected_schema:
            result["status"] = "error"
            result["error"] = "未找到与查询相关的表"
            await self.observability.end_span(span)
            return result

        table_names = []
        lines = selected_schema.split("\n")
        for line in lines:
            if line.startswith("表名:"):
                table_names.append(line.replace("表名:", "").strip())

        result["retrieved_tables"] = table_names
        result["steps"].append(f"检索到相关表: {', '.join(table_names)}")

        sql = self.sql_generator.generate_sql(question, selected_schema, self.current_db_type)
        if not sql:
            result["status"] = "error"
            result["error"] = "无法生成SQL语句"
            await self.observability.end_span(span)
            return result

        result["sql"] = sql
        result["steps"].append(f"生成SQL: {sql}")

        validation = self.sql_validator.validate_sql(sql)
        result["validation"] = validation
        result["steps"].append(f"SQL验证: {'通过' if validation['valid'] else '失败'}")

        if not validation["valid"]:
            result["status"] = "error"
            result["error"] = "; ".join(validation["errors"])
            await self.observability.end_span(span)
            return result

        execution_result = self.sql_executor.execute_sql(sql)
        result["execution_result"] = execution_result
        result["steps"].append(f"执行SQL: {'成功' if execution_result['success'] else '失败'}")

        if not execution_result["success"]:
            result["status"] = "error"
            result["error"] = execution_result["error"]
            await self.observability.end_span(span)
            return result

        analysis = self.result_analyzer.analyze_results(sql, execution_result["data"], question)
        result["analysis"] = analysis
        result["steps"].append("分析查询结果")

        elapsed_ms = (time.time() - start_time) * 1000
        self.metrics.record_message(elapsed_ms)
        await self.observability.record_metric(
            "agent.query.duration", elapsed_ms, "ms", {"type": "retrieval_query"}
        )

        await HookRegistry.execute_phase(
            HookPhase.AFTER_MESSAGE,
            {"message": question, "result": result}
        )

        await self.observability.end_span(span)
        return result

    async def process_message_async(
        self,
        message: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> dict:
        context = ToolContext(
            session_id=session_id,
            user_id=user_id,
            tools_registry=ToolRegistry,
            custom_context={}
        )

        workflow_result = await self.workflow_handler.try_handle(
            agent=self,
            user={"id": user_id} if user_id else None,
            conversation={"id": session_id},
            message=message
        )

        if workflow_result.should_skip_llm:
            return {
                "status": "workflow_handled",
                "components": workflow_result.components,
                "error": workflow_result.error
            }

        return await self.run_query_with_retrieval_async(message)

    def run_query(self, question: str) -> dict:
        result = {
            "status": "completed",
            "steps": [],
            "sql": None,
            "validation": None,
            "execution_result": None,
            "analysis": None,
            "error": None
        }

        if not self.current_db_type:
            result["status"] = "error"
            result["error"] = "请先连接数据库"
            return result

        schema_result = self.db_tool.get_schema()
        result["steps"].append("获取数据库表结构")

        if not schema_result.success:
            result["status"] = "error"
            result["error"] = schema_result.error
            return result

        schema = schema_result.data.get("formatted", "")

        sql_result = self.sql_generator.generate_sql(question, schema)
        if not sql_result:
            result["status"] = "error"
            result["error"] = "无法生成SQL语句"
            return result

        result["sql"] = sql_result
        result["steps"].append(f"生成SQL: {sql_result}")

        validation = self.sql_validator.validate_sql(sql_result)
        result["validation"] = validation
        result["steps"].append(f"SQL验证: {'通过' if validation['valid'] else '失败'}")

        if not validation["valid"]:
            result["status"] = "error"
            result["error"] = "; ".join(validation["errors"])
            return result

        execution_result = self.sql_executor.execute_sql(sql_result)
        result["execution_result"] = execution_result
        result["steps"].append(f"执行SQL: {'成功' if execution_result['success'] else '失败'}")

        if not execution_result["success"]:
            result["status"] = "error"
            result["error"] = execution_result["error"]
            return result

        analysis = self.result_analyzer.analyze_results(
            sql_result,
            execution_result["data"],
            question
        )
        result["analysis"] = analysis
        result["steps"].append("分析查询结果")

        return result

    def run_query_with_retrieval(self, question: str, top_k: int = 3) -> dict:
        result = {
            "status": "completed",
            "steps": [],
            "sql": None,
            "validation": None,
            "execution_result": None,
            "analysis": None,
            "error": None,
            "retrieved_tables": []
        }

        if not self.current_db_type:
            result["status"] = "error"
            result["error"] = "请先连接数据库"
            return result

        result["steps"].append("检索相关表")
        selected_schema = self.table_retriever.select_tables_for_query(question, top_k)

        if "未找到相关表" in selected_schema:
            result["status"] = "error"
            result["error"] = "未找到与查询相关的表"
            return result

        table_names = []
        lines = selected_schema.split("\n")
        for line in lines:
            if line.startswith("表名:"):
                table_names.append(line.replace("表名:", "").strip())

        result["retrieved_tables"] = table_names
        result["steps"].append(f"检索到相关表: {', '.join(table_names)}")

        sql = self.sql_generator.generate_sql(question, selected_schema, self.current_db_type)
        if not sql:
            result["status"] = "error"
            result["error"] = "无法生成SQL语句"
            return result

        result["sql"] = sql
        result["steps"].append(f"生成SQL: {sql}")

        validation = self.sql_validator.validate_sql(sql)
        result["validation"] = validation
        result["steps"].append(f"SQL验证: {'通过' if validation['valid'] else '失败'}")

        if not validation["valid"]:
            result["status"] = "error"
            result["error"] = "; ".join(validation["errors"])
            return result

        execution_result = self.sql_executor.execute_sql(sql)
        result["execution_result"] = execution_result
        result["steps"].append(f"执行SQL: {'成功' if execution_result['success'] else '失败'}")

        if not execution_result["success"]:
            result["status"] = "error"
            result["error"] = execution_result["error"]
            return result

        analysis = self.result_analyzer.analyze_results(sql, execution_result["data"], question)
        result["analysis"] = analysis
        result["steps"].append("分析查询结果")

        return result

    def explain_sql(self, sql: str) -> Optional[str]:
        if not self.current_db_type:
            return "请先连接数据库"

        schema_result = self.db_tool.get_schema()
        if not schema_result.success:
            return schema_result.error

        schema = schema_result.data.get("formatted", "")
        return self.sql_validator.explain_sql(sql, schema)

    def format_results(self, results) -> str:
        return self.result_analyzer.format_results(results)

    def get_statistics(self, results) -> dict:
        return self.result_analyzer.get_statistics(results)

    def search_tables(self, query: str, top_k: int = 5) -> str:
        return self.table_retriever.search_tables(query, top_k)

    def get_table_info(self, table_name: str) -> str:
        return self.table_retriever.get_table_info(table_name)

    def get_metrics_summary(self) -> dict:
        return self.metrics.get_summary()

    def reset_metrics(self) -> None:
        self.metrics.reset()

    def add_lifecycle_hook(self, hook: LifecycleHook) -> None:
        self.lifecycle_hooks.append(hook)
        HookRegistry.register(hook)

    def remove_lifecycle_hook(self, hook: LifecycleHook) -> None:
        if hook in self.lifecycle_hooks:
            self.lifecycle_hooks.remove(hook)
            HookRegistry.unregister(hook)

    def run_react_query(self, question: str, user_id: str = None, session_id: str = None) -> Dict[str, Any]:
        from agent.react_agent import ReActAgent
        import asyncio

        react_agent = ReActAgent(
            tool_registry=self._setup_react_registry(),
            observability_provider=self.observability,
            workflow_handler=self.workflow_handler,
            lifecycle_hooks=self.lifecycle_hooks,
            db_type=self.current_db_type or "sqlite",
        )

        if self.current_db_type:
            react_agent.default_system_prompt += f"\n\n当前已连接数据库类型: {self.current_db_type}"

        return asyncio.run(react_agent.run(
            question=question,
            user_id=user_id,
            session_id=session_id
        ))

    async def run_react_query_async(self, question: str, user_id: str = None, session_id: str = None) -> Dict[str, Any]:
        from agent.react_agent import ReActAgent

        react_agent = ReActAgent(
            tool_registry=self._setup_react_registry(),
            observability_provider=self.observability,
            workflow_handler=self.workflow_handler,
            lifecycle_hooks=self.lifecycle_hooks,
            db_type=self.current_db_type or "sqlite",
        )

        return await react_agent.run(
            question=question,
            user_id=user_id,
            session_id=session_id
        )

    def _setup_react_registry(self):
        registry = ToolRegistry()
        registry._tools = dict(ToolRegistry._tools)
        registry._categories = dict(ToolRegistry._categories)
        return registry