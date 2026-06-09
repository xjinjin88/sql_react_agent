# Agent-SQL 📊

一个基于 LLM 的智能 SQL Agent 系统，支持自然语言查询数据库。通过 ReAct 思维链和向量检索，实现从自然语言到 SQL 执行的全流程自动化。

## 🚀 特性

- **多 LLM 支持**：支持 OpenAI、Anthropic、DashScope 等多个 LLM 提供商
- **多数据库支持**：兼容 MySQL、PostgreSQL、SQLite 等关系型数据库
- **向量检索**：使用 ChromaDB + Sentence-Transformers 进行表和列的语义检索
- **ReAct Agent**：采用 ReAct 思维链进行任务分解和执行
- **实时可视化**：前端展示 LLM 思考过程、工具调用和执行结果
- **完整的工具链**：包括 SQL 生成、验证、执行、表探索等工具

## 📁 项目结构

```
.
├── agent/                          # Agent 核心模块
│   ├── react_agent.py             # ReAct 思维链实现
│   └── sql_agent.py               # SQL Agent 具体实现
├── core/                          # 核心服务
│   ├── lifecycle.py               # 生命周期管理
│   ├── observability.py           # 可观测性/监控
│   └── workflow.py                # 工作流编排
├── tools/                         # 工具模块
│   ├── llm_client.py             # LLM 客户端
│   ├── sql_generator.py          # SQL 生成工具
│   ├── sql_validator.py          # SQL 验证工具
│   ├── sql_executor.py           # SQL 执行工具
│   ├── table_retriever.py        # 表检索工具
│   ├── table_explorer.py         # 表探索工具
│   ├── embeddings.py             # 嵌入向量生成
│   ├── chroma_vector_retriever.py # 向量检索工具
│   └── database_connection.py     # 数据库连接
├── frontend/                      # React 前端 UI
│   ├── src/
│   │   ├── components/            # React 组件
│   │   ├── hooks/                # 自定义 Hook
│   │   ├── services/             # API 服务
│   │   └── types/                # TypeScript 类型定义
│   └── ...
├── main.py                        # FastAPI 主程序
├── config.py                      # 配置管理
└── requirements.txt               # Python 依赖
```

## 🔧 安装

### 环境要求
- Python 3.8+
- Node.js 16+（前端开发）
- 数据库连接（MySQL/PostgreSQL/SQLite）

### 后端安装

1. 克隆项目
```bash
git clone https://github.com/xjinjin88/sql_react_agent.git
cd sql_react_agent
```

2. 创建虚拟环境
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

3. 安装依赖
```bash
pip install -r requirements.txt
```

4. 配置环境变量
```bash
cp .env.example .env
```

编辑 `.env` 文件，填写以下信息：
```
# LLM 配置
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
DASHSCOPE_API_KEY=your_key_here
LLM_PROVIDER=dashscope
LLM_MODEL=qwen_plus

# 数据库配置（选择一个）
# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=password
MYSQL_DATABASE=your_db

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DATABASE=your_db

# SQLite
SQLITE_PATH=./example.db
```

### 前端安装

```bash
cd frontend
npm install
```

## 🎯 使用

### 启动后端服务
```bash
python main.py
```
API 服务将在 `http://localhost:8000` 启动

### 启动前端开发服务器
```bash
cd frontend
npm run dev
```
前端将在 `http://localhost:5173` 打开

### API 文档
访问 `http://localhost:8000/docs` 查看 OpenAPI 交互式文档

## 📝 使用示例

### 通过 API 查询

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "统计2024年销售额前5的产品"}'
```

### 响应格式

```json
{
  "answer": "根据数据，2024年销售额前5的产品是...",
  "sql_generated": "SELECT ... FROM ... ORDER BY sales DESC LIMIT 5",
  "tool_calls": [
    {
      "tool": "table_retriever",
      "arguments": {...},
      "result": {...},
      "elapsed_ms": 125.3
    },
    {
      "tool": "sql_generator",
      "arguments": {...},
      "result": {...},
      "elapsed_ms": 2345.6
    }
  ],
  "thoughts": "我需要...",
  "success": true
}
```

## 🏗️ 架构设计

### 工作流程

```
自然语言查询
    ↓
LLM 思维链（ReAct）
    ├─→ 理解问题
    ├─→ 检索相关表和列
    ├─→ 生成 SQL 查询
    ├─→ 验证 SQL
    └─→ 执行 SQL
    ↓
返回结果和可视化信息
```

### 核心组件

| 模块 | 功能 |
|------|------|
| **ReAct Agent** | 思维链推理和工具调用 |
| **LLM Client** | 与各 LLM 提供商通信 |
| **SQL Generator** | 从自然语言生成 SQL |
| **SQL Validator** | SQL 语法和语义检查 |
| **Vector Retriever** | 向量相似度搜索表/列 |
| **Database Handler** | 多数据库连接和执行 |

## 🧪 开发

### 生成表向量嵌入

```bash
python generate_table_embeddings.py
```

### 导出表元数据

在将表信息向量化之前，你可以先从数据库导出 `tables_metadata.json`：

```bash
python export_metadata.py.py
```


### 运行测试
```bash
python test_react_verify.py
python test_react.py
```

### 查看示例
```bash
python examples/demo.py
```

## 📦 依赖说明

### 主要依赖
- **FastAPI**: 高性能 Web 框架
- **LangChain**: LLM 应用开发框架
- **ChromaDB**: 向量数据库
- **SQLAlchemy**: SQL 工具库
- **Pydantic**: 数据验证
- **Sentence-Transformers**: 文本向量化

### 数据库驱动
- **mysql-connector-python**: MySQL 连接
- **psycopg2-binary**: PostgreSQL 连接

## 🔐 安全建议

1. 不要提交 `.env` 文件到版本控制
2. 定期轮换 API Key
3. 为敏感操作添加权限控制
4. 验证 SQL 查询避免注入攻击
5. 使用 HTTPS 在生产环境

## 📝 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📧 联系方式

如有问题，请通过以下方式联系：
- 提交 Issue
- 发送邮件

---

**开发中...** ⚙️
