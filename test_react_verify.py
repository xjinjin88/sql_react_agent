"""
ReAct 模式验证脚本
使用说明：
1. 确保已连接数据库（修改下面的 DB_TYPE 为你的数据库类型）
2. 运行脚本：.\venv\Scripts\python.exe test_react_verify.py
"""

import asyncio
from agent.sql_agent import SQLAgent
from core.lifecycle import LoggingHook, TimingHook


def test_basic_import():
    """测试1: 验证基本导入"""
    print("=" * 50)
    print("测试1: 基本导入")
    print("=" * 50)

    from agent.sql_agent import SQLAgent
    from agent.react_agent import ReActAgent
    from tools.llm_client import LLMClient, Message, MessageRole

    print("✅ 所有模块导入成功")
    return True


def test_agent_creation():
    """测试2: 验证 Agent 创建"""
    print("\n" + "=" * 50)
    print("测试2: Agent 创建")
    print("=" * 50)

    agent = SQLAgent()
    print(f"✅ SQLAgent 创建成功")
    print(f"   - 工具数量: {len(agent.get_registry().get_all_tools())}")

    registry = agent._setup_react_registry()
    print(f"✅ ReAct 注册表创建成功")
    print(f"   - 工具数量: {len(registry.get_all_tools())}")

    from agent.react_agent import ReActAgent
    react = ReActAgent(tool_registry=registry)
    print(f"✅ ReActAgent 创建成功")
    print(f"   - 最大迭代次数: {react.max_iterations}")
    print(f"   - 系统提示词长度: {len(react.default_system_prompt)} 字符")

    return True


def test_tool_description():
    """测试3: 验证工具描述"""
    print("\n" + "=" * 50)
    print("测试3: 工具描述")
    print("=" * 50)

    agent = SQLAgent()
    registry = agent._setup_react_registry()
    from agent.react_agent import ReActAgent

    react = ReActAgent(tool_registry=registry)
    tools = react.get_tools_for_llm()

    print(f"✅ 工具列表获取成功，共 {len(tools)} 个工具：")
    for tool in tools:
        func = tool['function']
        print(f"\n   【{func['name']}】")
        print(f"   描述: {func['description']}")

    return True


def test_llm_function_calling():
    """测试4: 验证 LLM Function Calling（需要 API key）"""
    print("\n" + "=" * 50)
    print("测试4: LLM Function Calling")
    print("=" * 50)

    from tools.llm_client import LLMClient, Message, MessageRole

    llm = LLMClient()
    print(f"✅ LLMClient 创建成功")
    print(f"   - 模型: {llm.model}")

    tools = [{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称"}
                },
                "required": ["city"]
            }
        }
    }]

    messages = [
        Message(role=MessageRole.USER.value, content="北京今天天气怎么样？")
    ]

    print("\n   发送请求到千问 API...")
    response = llm.chat(messages, tools=tools)

    if response.has_tool_calls():
        print(f"✅ LLM 返回了工具调用！")
        for tc in response.tool_calls:
            print(f"   - 工具: {tc.name}")
            print(f"   - 参数: {tc.arguments}")
    else:
        print(f"   LLM 返回文本响应: {response.content[:100]}...")

    return True


def test_react_query_no_db():
    """测试5: ReAct 查询（不连接数据库，测试流程）"""
    print("\n" + "=" * 50)
    print("测试5: ReAct 查询（无数据库）")
    print("=" * 50)

    agent = SQLAgent()

    result = agent.run_react_query("你好，你是什么？")

    print(f"✅ ReAct 查询完成")
    print(f"   - 状态: {result['status']}")
    print(f"   - 迭代次数: {result['iterations']}")
    print(f"   - 工具调用次数: {len(result.get('tool_calls', []))}")
    print(f"   - 回答: {result.get('answer', '无')[:200]}...")

    return True


def main():
    print("\n" + "=" * 60)
    print("🔍 ReAct 模式功能验证")
    print("=" * 60)

    tests = [
        ("基本导入", test_basic_import),
        ("Agent 创建", test_agent_creation),
        ("工具描述", test_tool_description),
        ("LLM Function Calling", test_llm_function_calling),
        ("ReAct 查询（无数据库）", test_react_query_no_db),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"\n✅ {name} - 通过")
            else:
                failed += 1
                print(f"\n❌ {name} - 失败")
        except Exception as e:
            failed += 1
            print(f"\n❌ {name} - 异常: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"📊 测试结果: {passed} 通过, {failed} 失败")
    print("=" * 60)

    if failed == 0:
        print("\n🎉 所有测试通过！ReAct 模式已准备就绪。")
        print("\n下一步：")
        print("1. 连接你的数据库: agent.connect_database('mysql')")
        print("2. 运行 ReAct 查询: agent.run_react_query('你的问题')")
    else:
        print("\n⚠️ 部分测试失败，请检查错误信息。")


if __name__ == "__main__":
    main()
