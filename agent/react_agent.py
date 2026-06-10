from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import json
import time

from tools.table_retriever import TableRetrieverTool
from tools.sql_executor import SQLExecutor
from tools.table_explorer import TableExplorer, build_schema_summary
from tools.database_connection import DatabaseConnection
from tools.llm_client import LLMClient, Message, MessageRole
from tools.tool_base import ToolResult

# 定义智能状态类
@dataclass
class AgentState:
    messages: list = field(default_factory=list)

    cache: dict = field(default_factory=dict)

    iteration: int = 0

    is_finished: bool = False


SYSTEM_PROMPT = """你是一个专业的 SQL 分析助手，需要帮助用户生成SQL Server数据库的SQL查询。

你的任务是根据用户的问题，选择合适的工具来获取信息，最终给出准确的回答。

可用工具：
1. table_retriever - 搜索与问题相关的表
2. table_explorer - 探索表结构和数据样本,优先一次探索多个表,当需要查看多个表结构时，请使用 table_names 一次性传入多个表。
3. sql_executor - 执行SQL查询，如果只是了解表数据进行的查询，最好只返回5条样例数据。

请根据问题的复杂性决定是否需要调用工具。
- 如果需要先搜索表、查看表结构或执行查询，请调用相应工具
-生成SQL前必须确认：

1. 表是否存在
2. 字段是否存在
3. 字段含义是否确认

如果不确定，优先调用工具获取信息。
"""

TOOLS_SCHEMA = [
    {
        "name": "table_retriever",
        "description": "搜索与问题相关的表",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词"
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回前k个结果",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "table_explorer",
        "description": "探索一个或多个表的结构和数据样本",
        "parameters": {
            "type": "object",
            "properties": {
                "table_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "要探索的表名列表"
                },
                "table_name": {
                    "type": "string",
                    "description": "要探索的单个表名（兼容旧接口）"
                },
                "max_rows": {
                    "type": "integer",
                    "description": "返回的样本行数",
                    "default": 1
                }
            }
        }
    },
    {
        "name": "sql_executor",
        "description": "执行SQL查询",
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "要执行的SQL语句"
                }
            },
            "required": ["sql"]
        }
    }
]


class ReactAgent:
    def __init__(self, max_iterations: int = 10):
        self.llm = LLMClient()
        self.max_iterations = max_iterations
        
        self.table_retriever = TableRetrieverTool(
            metadata_path="tables_metadata.json",
            use_chroma=True
        )
        self.sql_executor = SQLExecutor()
        self.table_explorer = TableExplorer()
    
    def set_db_connection(self, connection: DatabaseConnection):
        self.sql_executor.set_connection(connection)
        self.table_explorer.set_db_connection(connection)
    
    def create_initial_state(self, question: str):
        return AgentState(
            messages=[
                Message(
                    role=MessageRole.USER.value,
                    content=question
                )
            ],
            cache={
                "schemas": {},
                "retrieved_tables": set(),
                "executed_sqls": [],
                "failed_sqls": []
            }
        )
    
 
    

    
    def run(self, question: str) -> Dict[str, Any]:
        state = self.create_initial_state(question)
        
        final_answer = None
        llm_calls = []
        tool_calls = []
        thoughts = []
        
        while state.iteration < self.max_iterations and not state.is_finished:
            state.iteration += 1
            
            messages = self._build_messages(state)
            
            # 记录发送给LLM的输入 - 使用序列化方法确保正确格式
            llm_input = [self._serialize_message(msg) for msg in messages]
            
            response = self.llm.chat(messages, tools=TOOLS_SCHEMA)
            
            # 记录LLM的输出
            llm_output = {
                "content": response.content,
                "has_tool_calls": response.has_tool_calls(),
                "tool_calls": []
            }
            
            if response.has_tool_calls():
                llm_output["tool_calls"] = [
                    {
                        "name": tc.name,
                        "arguments": tc.arguments,
                        "id": tc.id
                    } for tc in response.tool_calls
                ]
            
            # 保存本次LLM调用记录
            llm_calls.append({
                "iteration": state.iteration,
                "input": llm_input,
                "output": llm_output
            })
            
            # 记录思考
            thoughts.append({
                "iteration": state.iteration,
                "thought": response.content or "",
                "has_tool_calls": response.has_tool_calls(),
                "llm_input": llm_input
            })
            
            if response.has_tool_calls():

               state.messages.append(Message(
               role=MessageRole.ASSISTANT.value,
               content=response.content or "",
               tool_calls=response.tool_calls
                 ))

               for tool_call in response.tool_calls:
                   tool_start_time = time.time()
                   
                   observation = self._execute_tool(
                   tool_call.name,
                   tool_call.arguments,state)
                   
                   tool_elapsed_ms = (time.time() - tool_start_time) * 1000
                   
                   # 记录工具调用结果 - 确保 result 格式正确
                   tool_result = observation.get("result")
                   if tool_result is None:
                       # 如果没有 result 字段，从 observation 构建标准格式
                       tool_result = {
                           "success": "error" not in observation,
                           "data": observation.get("data"),
                           "error": observation.get("error")
                       }
                   
                   tool_calls.append({
                       "tool": tool_call.name,
                       "arguments": tool_call.arguments,
                       "result": tool_result,
                       "elapsed_ms": tool_elapsed_ms,
                       "success": tool_result.get("success", True) if isinstance(tool_result, dict) else True
                   })

                   # 对不同工具添加不同级别的结果信息
                   if tool_call.name == "table_explorer":
                       # table_explorer: 简化处理，只传递成功状态和表名
                       table_names = tool_call.arguments.get("table_names", [])
                       if not table_names:
                           table_name = tool_call.arguments.get("table_name")
                           if table_name:
                               table_names = [table_name]
                       state.messages.append(Message(
                           role=MessageRole.TOOL.value,
                           content=json.dumps({
                               "success": tool_result.get("success", True),
                               "explored_tables": table_names,
                               "schema_cached": True
                           }, ensure_ascii=False),
                           name=tool_call.name,
                           tool_call_id=tool_call.id))
                   elif tool_call.name == "table_retriever":
                       # table_retriever: 简化处理，只传递检索到的表名
                       # observation["result"] 是 ToolResult.to_dict() 的结果，包含 success, data, error, metadata
                       # 实际的 tables 数据在 observation["result"]["data"]["tables"] 中
                       retrieved_tables = [t.get("table_name") for t in observation.get("result", {}).get("data", {}).get("tables", []) if t.get("table_name")]
                       state.messages.append(Message(
                           role=MessageRole.TOOL.value,
                           content=json.dumps({
                               "success": tool_result.get("success", True),
                               "retrieved_tables": retrieved_tables,
                               "count": len(retrieved_tables)
                           }, ensure_ascii=False),
                           name=tool_call.name,
                           tool_call_id=tool_call.id))
                   else:
                       # 其他工具（如 sql_executor）: 添加完整结果
                       state.messages.append(Message(
                           role=MessageRole.TOOL.value,
                           content=json.dumps(observation, ensure_ascii=False),
                           name=tool_call.name,
                           tool_call_id=tool_call.id))
            else:
                state.messages.append(Message(
                   role=MessageRole.ASSISTANT.value,
                   content=response.content))
                
                final_answer = response.content
                state.is_finished = True
                break
        
        if final_answer is None:
            final_answer = "抱歉，我无法在规定次数内解决您的问题。"
        
        return {
            "answer": final_answer,
            "state": state,
            "iterations": state.iteration,
            "llm_calls": llm_calls,
            "tool_calls": tool_calls,
            "thoughts": thoughts
        }
    
    def _build_messages(self, state):
        # 构建系统提示，包含已获取的schema信息
        system_content = SYSTEM_PROMPT
        
        # 如果有已探索的表结构，添加到系统提示中
        if state.cache.get("schemas"):
            schema_summary = build_schema_summary(state.cache["schemas"])
            system_content += "\n\n" + schema_summary
        
        return [
            Message(
                role=MessageRole.SYSTEM.value,
                content=system_content
            ),
            *state.messages
        ]
    
    def _serialize_message(self, msg):
        """将 Message 对象序列化为纯字典，确保 tool_calls 也被正确序列化"""
        return {
            "role": msg.role,
            "content": msg.content,
            "name": getattr(msg, "name", None),
            "tool_call_id": getattr(msg, "tool_call_id", None),
            "tool_calls": [
                {
                    "id": tc.id,
                    "name": tc.name,
                    "arguments": tc.arguments
                }
                for tc in (getattr(msg, "tool_calls", None) or [])
            ]
        }
    
    def _extract_sql(self, action_input: dict) -> str:
        for key in ["sql", "query", "statement", "query_sql", "sql_query"]:
            if key in action_input:
                return action_input[key]
        return ""
    
    def _execute_tool(self, action: str, action_input: dict, state: AgentState) -> dict:
        try:
            if action == "table_retriever":
                result = self.table_retriever.search_tables_tool(
                    query=action_input.get("query", ""),
                    top_k=action_input.get("top_k", 5)
                )
                if result.success and result.data:
                    tables = result.data.get("tables", [])
                    for table in tables:
                        table_name = table.get("table_name")
                        if table_name:
                            state.cache["retrieved_tables"].add(table_name)
                return {
                    "tool": "table_retriever",
                    "result": result.to_dict()
                }
            
            elif action == "table_explorer":
                # 兼容单个表名和表名列表
                table_names = action_input.get("table_names", [])
                if not table_names:
                    table_name = action_input.get("table_name", "")
                    if table_name:
                        table_names = [table_name]
                
                if not table_names:
                    return {
                        "tool": "table_explorer",
                        "result": {
                            "success": False,
                            "error": "未提供表名"
                        }
                    }
                
                results = []
                max_rows = action_input.get("max_rows", 1)
                has_error = False
                
                for table_name in table_names:
                    # 先查看缓存
                    if table_name in state.cache["schemas"]:
                        results.append({
                            "table_name": table_name,
                            "cached": True,
                            "data": state.cache["schemas"][table_name]
                        })
                        continue
                    
                    # 缓存不存在再查看数据库
                    result = self.table_explorer.explore_table(
                        table_name=table_name,
                        max_rows=max_rows
                    )
                    
                    if result.success and result.data:
                        real_table_name = result.data.get("table_name", table_name)
                        state.cache["schemas"][real_table_name] = result.data
                        results.append({
                            "table_name": real_table_name,
                            "cached": False,
                            "data": result.data
                        })
                    else:
                        has_error = True
                        results.append({
                            "table_name": table_name,
                            "error": result.error or "探索失败"
                        })
                
                return {
                    "tool": "table_explorer",
                    "result": {
                        "success": not has_error,
                        "data": {"tables": results}
                    }
                }
            
            elif action == "sql_executor":
                sql = self._extract_sql(action_input)
                result = self.sql_executor.execute_sql_tool(sql)
                if result.success:
                    state.cache["executed_sqls"].append({
                        "sql": sql,
                        "result": result.data
                    })
                else:
                    state.cache["failed_sqls"].append({
                        "sql": sql,
                        "error": result.error
                    })
                return {
                    "tool": "sql_executor",
                    "result": result.to_dict()
                }
            
            else:
                return {
                    "tool": action,
                    "result": {
                        "success": False,
                        "error": f"Unknown tool: {action}"
                    }
                }
        except Exception as e:
            return {
                "tool": action,
                "result": {
                    "success": False,
                    "error": str(e)
                }
            }