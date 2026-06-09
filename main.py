import os
os.environ["TRANSFORMERS_DISABLE_TF"] = "1"

from decimal import Decimal
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio
import time

def convert_decimals(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_decimals(item) for item in obj]
    return obj

app = FastAPI(title="SQL Agent API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

agent = None
db_connection = None

class QueryRequest(BaseModel):
    question: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None

class ToolCallResult(BaseModel):
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class ToolCall(BaseModel):
    tool: str
    arguments: Dict[str, Any]
    result: ToolCallResult
    elapsed_ms: float
    success: bool

class LlmMessage(BaseModel):
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    name: Optional[str] = None
    tool_call_id: Optional[str] = None

class LlmOutput(BaseModel):
    content: str
    has_tool_calls: bool
    tool_calls: List[Dict[str, Any]]

class LlmCall(BaseModel):
    iteration: int
    input: List[LlmMessage]
    output: LlmOutput

class Thought(BaseModel):
    iteration: int
    thought: str
    has_tool_calls: bool
    llm_input: Optional[List[LlmMessage]] = None

class QueryResponse(BaseModel):
    status: str
    question: str
    answer: Optional[str]
    iterations: int
    discovered_tables: List[str]
    explored_schemas: List[str]
    sql_results_count: int
    elapsed_ms: Optional[float]
    error: Optional[str]
    tool_calls: List[ToolCall] = []
    thoughts: List[Thought] = []
    llm_calls: List[LlmCall] = []

class ConnectRequest(BaseModel):
    db_type: str

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

@app.post("/api/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    global agent, db_connection
    
    if agent is None:
        try:
            from agent.react_agent import ReactAgent
            agent = ReactAgent(max_iterations=10)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"初始化失败: {str(e)}")
    
    if db_connection is not None:
        agent.set_db_connection(db_connection)
    
    try:
        start_time = time.time()
        
        result = await asyncio.to_thread(agent.run, request.question)
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        state = result.get("state")
        
        # 从 cache 中获取相关数据
        discovered_tables = list(state.cache["retrieved_tables"]) if state and "retrieved_tables" in state.cache else []
        explored_schemas = list(state.cache["schemas"].keys()) if state and "schemas" in state.cache else []
        sql_results_count = len(state.cache["executed_sqls"]) if state and "executed_sqls" in state.cache else 0
        
        converted_result = {
            "status": "success",
            "question": request.question,
            "answer": result.get("answer"),
            "iterations": result.get("iterations"),
            "discovered_tables": discovered_tables,
            "explored_schemas": explored_schemas,
            "sql_results_count": sql_results_count,
            "elapsed_ms": elapsed_ms,
            "error": None,
            "tool_calls": result.get("tool_calls", []),
            "thoughts": result.get("thoughts", []),
            "llm_calls": result.get("llm_calls", [])
        }
        
        converted_result = convert_decimals(converted_result)
        return QueryResponse(**converted_result)
    except Exception as e:
        print(f"Query error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/connect")
async def connect_database(db_type: str):
    global agent, db_connection
    
    try:
        from tools.database_connection import DatabaseConnection
        
        db_connection = DatabaseConnection(db_type=db_type)
        if db_connection.connect():
            if agent is not None:
                agent.set_db_connection(db_connection)
            return {"status": "success", "message": f"成功连接到 {db_type} 数据库"}
        else:
            return {"status": "error", "message": f"连接 {db_type} 数据库失败"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/disconnect")
async def disconnect_database():
    global agent, db_connection
    
    if db_connection is None:
        return {"status": "success", "message": "未连接数据库"}
    
    try:
        db_connection.disconnect()
        db_connection = None
        return {"status": "success", "message": "已断开数据库连接"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/database/status")
async def database_status():
    global db_connection
    if db_connection is None:
        return {"connected": False, "db_type": None}
    return {"connected": True, "db_type": db_connection.db_type}

@app.get("/api/tools")
async def get_tools():
    return {
        "tools": [
            {
                "name": "table_retriever",
                "description": "搜索与问题相关的表",
                "parameters": {
                    "query": "搜索关键词",
                    "top_k": "返回前k个结果 (默认5)"
                }
            },
            {
                "name": "table_explorer",
                "description": "探索表结构和数据样本",
                "parameters": {
                    "table_name": "要探索的表名",
                    "max_rows": "返回的样本行数 (默认5)"
                }
            },
            {
                "name": "sql_executor",
                "description": "执行SQL查询",
                "parameters": {
                    "sql": "要执行的SQL语句"
                }
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)