from config import Config
from typing import Optional, List, Dict, Any, Union
import dashscope
from http import HTTPStatus
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import concurrent.futures


class MessageRole(Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class LLMProvider(Enum):
    DASHSCOPE = "dashscope"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]


@dataclass
class LLMResponse:
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    finish_reason: Optional[str] = None

    def has_tool_calls(self) -> bool:
        return self.tool_calls is not None and len(self.tool_calls) > 0


@dataclass
class Message:
    role: str
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


class LLMClient:
    def __init__(
        self,
        model: str = None,
        provider: str = None
    ):
        self.provider_name = provider or Config.LLM_PROVIDER
        self.model = model or Config.LLM_MODEL
        self._tool_call_id_counter = 0
        
        try:
            self.provider = LLMProvider(self.provider_name)
        except ValueError:
            raise ValueError(f"Unsupported LLM provider: {self.provider_name}. Supported: dashscope, openai, anthropic")
        
        self._init_llm()
    
    def _init_llm(self):
        if self.provider == LLMProvider.DASHSCOPE:
            import dashscope
            dashscope.api_key = Config.DASHSCOPE_API_KEY
            self.llm = None
            
        elif self.provider == LLMProvider.OPENAI:
            from langchain_openai import ChatOpenAI
            self.llm = ChatOpenAI(
                model=self.model,
                api_key=Config.OPENAI_API_KEY
            )
            
        elif self.provider == LLMProvider.ANTHROPIC:
            from langchain_anthropic import ChatAnthropic
            self.llm = ChatAnthropic(
                model=self.model,
                anthropic_api_key=Config.ANTHROPIC_API_KEY
            )

    def _generate_tool_call_id(self) -> str:
        self._tool_call_id_counter += 1
        return f"call_{self._tool_call_id_counter}"

    def generate(self, prompt: str, model: str = None) -> Optional[str]:
        try:
            messages = [{'role': 'user', 'content': prompt}]
            response = dashscope.Generation.call(
                model=model or self.model,
                messages=messages,
                result_format='message'
            )

            if response.status_code == HTTPStatus.OK:
                return response.output.choices[0].message.content
            else:
                print(f"API调用失败: {response}")
                return None
        except Exception as e:
            print(f"LLM调用失败: {e}")
            return None

    def chat(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        model: str = None
    ) -> LLMResponse:
        try:
            if self.provider == LLMProvider.DASHSCOPE:
                return self._chat_dashscope(messages, tools, model)
            elif self.provider == LLMProvider.OPENAI:
                return self._chat_openai(messages, tools, model)
            elif self.provider == LLMProvider.ANTHROPIC:
                return self._chat_anthropic(messages, tools, model)
        except Exception as e:
            print(f"LLM调用失败: {e}")
            return LLMResponse(content=f"LLM调用失败: {e}")

    def _chat_dashscope(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        model: str = None
    ) -> LLMResponse:
        import dashscope
        from http import HTTPStatus
        
        dashscope_messages = self._convert_messages(messages)

        call_params = {
            'model': model or self.model,
            'messages': dashscope_messages,
            'result_format': 'message',
        }

        if tools:
            call_params['tools'] = tools

        response = dashscope.Generation.call(**call_params)

        if response.status_code == HTTPStatus.OK:
            return self._parse_response(response)
        else:
            print(f"API调用失败: {response}")
            return LLMResponse(content=f"API调用失败: {response}")

    def _chat_openai(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        model: str = None
    ) -> LLMResponse:
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
        
        langchain_messages = self._convert_to_langchain_messages(messages)
        
        call_params = {
            'messages': langchain_messages,
        }
        
        if tools:
            from langchain_core.utils.function_calling import convert_to_openai_function
            call_params['tools'] = [convert_to_openai_function(tool) for tool in tools]
        
        if model:
            call_params['model'] = model
        
        response = self.llm.invoke(**call_params)
        
        return LLMResponse(
            content=response.content if hasattr(response, 'content') else str(response),
            tool_calls=None,
            finish_reason=response.response_metadata.get('finish_reason') if hasattr(response, 'response_metadata') else None
        )

    def _chat_anthropic(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        model: str = None
    ) -> LLMResponse:
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
        
        langchain_messages = self._convert_to_langchain_messages(messages)
        
        call_params = {
            'messages': langchain_messages,
        }
        
        if tools:
            from langchain_core.utils.function_calling import convert_to_openai_function
            call_params['tools'] = [convert_to_openai_function(tool) for tool in tools]
        
        if model:
            call_params['model'] = model
        
        response = self.llm.invoke(**call_params)
        
        return LLMResponse(
            content=response.content if hasattr(response, 'content') else str(response),
            tool_calls=None,
            finish_reason=response.response_metadata.get('finish_reason') if hasattr(response, 'response_metadata') else None
        )

    def _convert_to_langchain_messages(self, messages: List[Message]) -> List:
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
        
        result = []
        for msg in messages:
            if msg.role == MessageRole.SYSTEM.value:
                result.append(SystemMessage(content=msg.content or ''))
            elif msg.role == MessageRole.USER.value:
                result.append(HumanMessage(content=msg.content or ''))
            elif msg.role == MessageRole.ASSISTANT.value:
                if msg.tool_calls:
                    result.append(AIMessage(content=msg.content or '', additional_kwargs={'tool_calls': [
                        {'id': tc.id, 'function': {'name': tc.name, 'arguments': tc.arguments}} 
                        for tc in msg.tool_calls
                    ]}))
                else:
                    result.append(AIMessage(content=msg.content or ''))
            elif msg.role == MessageRole.TOOL.value:
                result.append(ToolMessage(content=msg.content or '', tool_call_id=msg.tool_call_id))
        return result

    async def async_chat(
        self,
        messages: List[Message],
        tools: Optional[List[Dict[str, Any]]] = None,
        model: str = None,
        timeout: int = 60
    ) -> LLMResponse:
        try:
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                result = await asyncio.wait_for(
                    loop.run_in_executor(executor, self.chat, messages, tools, model),
                    timeout=timeout
                )
                return result
        except asyncio.TimeoutError:
            print(f"LLM调用超时 ({timeout}秒)")
            return LLMResponse(content=f"LLM调用超时，请稍后重试")
        except Exception as e:
            print(f"异步LLM调用失败: {e}")
            return LLMResponse(content=f"LLM调用失败: {e}")

    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        result = []
        for msg in messages:
            if msg.role == MessageRole.TOOL.value:
                result.append({
                    'role': 'tool',
                    'content': msg.content or '',
                    'tool_call_id': msg.tool_call_id
                })
            elif msg.tool_calls:
                tool_calls = []
                for tc in msg.tool_calls:
                    import json
                    tool_calls.append({
                        'id': tc.id,
                        'function': {
                            'name': tc.name,
                            'arguments': json.dumps(tc.arguments)
                        },
                        'type': 'function'
                    })
                result.append({
                    'role': 'assistant',
                    'content': msg.content or '',
                    'tool_calls': tool_calls
                })
            else:
                result.append({
                    'role': msg.role,
                    'content': msg.content or ''
                })
        return result

    def _parse_response(self, response) -> LLMResponse:
        print(f"[_parse_response] response type: {type(response)}")
        print(f"[_parse_response] response.output type: {type(response.output)}")
        print(f"[_parse_response] response.output: {response.output}")
        
        if isinstance(response.output, dict):
            choice = response.output['choices'][0]
            message = choice['message']
        else:
            choice = response.output.choices[0]
            message = choice.message

        content = message.content if isinstance(message, dict) else message.content
        tool_calls = None

        msg_tool_calls = message.get('tool_calls') if isinstance(message, dict) else (message.tool_calls if hasattr(message, 'tool_calls') else None)
        if msg_tool_calls:
            tool_calls = []
            for tc in msg_tool_calls:
                if isinstance(tc, dict):
                    func = tc.get('function', {})
                    tc_id = tc.get('id', self._generate_tool_call_id())
                    func_name = func.get('name', 'unknown')
                    func_args = func.get('arguments', '{}')
                elif hasattr(tc, 'function'):
                    func = tc.function
                    tc_id = tc.id
                    func_name = func.name
                    func_args = func.arguments
                else:
                    continue

                import json
                if isinstance(func_args, str):
                    try:
                        args = json.loads(func_args)
                    except:
                        try:
                            import ast
                            args = ast.literal_eval(func_args)
                        except:
                            args = {"raw": func_args}
                elif isinstance(func_args, dict):
                    args = func_args
                else:
                    args = {"raw": str(func_args)}

                tool_calls.append(ToolCall(
                    id=tc_id,
                    name=func_name,
                    arguments=args
                ))

        if not tool_calls and content:
            tool_calls = self._parse_text_tool_calls(content)

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=choice.get('finish_reason') if isinstance(choice, dict) else (choice.finish_reason if hasattr(choice, 'finish_reason') else None)
        )
    
    def _parse_text_tool_calls(self, content: str) -> Optional[List[ToolCall]]:
        import re
        import json
        
        # 模式1: Action/Arguments 格式
        action_pattern = r'Action:\s*(\w+)'
        args_pattern = r'Arguments:\s*(\{.*?\})'
        
        action_match = re.search(action_pattern, content)
        args_match = re.search(args_pattern, content, re.DOTALL)
        
        if action_match and args_match:
            tool_name = action_match.group(1)
            args_str = args_match.group(1)
            
            try:
                args = json.loads(args_str)
            except:
                try:
                    import ast
                    args = ast.literal_eval(args_str)
                except:
                    args = {"raw": args_str}
            
            return [ToolCall(
                id=self._generate_tool_call_id(),
                name=tool_name,
                arguments=args
            )]
        
        # 模式2: markdown 代码块格式 ```json {...} ```
        code_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        code_block_match = re.search(code_block_pattern, content, re.DOTALL)
        
        if code_block_match:
            json_str = code_block_match.group(1).strip()
            try:
                tool_call_data = json.loads(json_str)
                if isinstance(tool_call_data, dict) and 'name' in tool_call_data and 'arguments' in tool_call_data:
                    return [ToolCall(
                        id=self._generate_tool_call_id(),
                        name=tool_call_data['name'],
                        arguments=tool_call_data['arguments']
                    )]
            except json.JSONDecodeError:
                print(f"[LLM Client] 解析JSON代码块失败: {json_str[:100]}")
        
        # 模式3: 直接JSON格式（没有反引号）
        try:
            tool_call_data = json.loads(content.strip())
            if isinstance(tool_call_data, dict) and 'name' in tool_call_data and 'arguments' in tool_call_data:
                return [ToolCall(
                    id=self._generate_tool_call_id(),
                    name=tool_call_data['name'],
                    arguments=tool_call_data['arguments']
                )]
        except json.JSONDecodeError:
            pass
        
        return None

    def chat_with_prompt(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> LLMResponse:
        messages = []
        if system_prompt:
            messages.append(Message(role=MessageRole.SYSTEM.value, content=system_prompt))
        messages.append(Message(role=MessageRole.USER.value, content=prompt))
        return self.chat(messages, tools=tools)


class EmbeddingsClient:
    def __init__(self):
        self.api_key = Config.DASHSCOPE_API_KEY
        dashscope.api_key = self.api_key

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        try:
            response = dashscope.TextEmbedding.call(
                model=dashscope.TextEmbedding.Models.text_embedding_v1,
                input=texts
            )

            if response.status_code == HTTPStatus.OK:
                embeddings = []
                for item in response.output['embeddings']:
                    embeddings.append(item['embedding'])
                return embeddings
            else:
                print(f"Embedding API调用失败: {response}")
                return [[0.0] * 1536 for _ in texts]
        except Exception as e:
            print(f"Embedding调用失败: {e}")
            return [[0.0] * 1536 for _ in texts]

    def embed_query(self, text: str) -> List[float]:
        try:
            response = dashscope.TextEmbedding.call(
                model=dashscope.TextEmbedding.Models.text_embedding_v1,
                input=text
            )

            if response.status_code == HTTPStatus.OK:
                return response.output['embeddings'][0]['embedding']
            else:
                print(f"Embedding API调用失败: {response}")
                return [0.0] * 1536
        except Exception as e:
            print(f"Embedding调用失败: {e}")
            return [0.0] * 1536
