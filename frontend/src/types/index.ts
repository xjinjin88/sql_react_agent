export interface ToolCall {
  tool: string;
  arguments: Record<string, unknown>;
  result: ToolResult;
  elapsed_ms: number;
  success: boolean;
}

export interface ToolResult {
  success: boolean;
  data?: unknown;
  error?: string;
  metadata?: Record<string, unknown>;
}

export interface Thought {
  iteration: number;
  thought: string;
  has_tool_calls: boolean;
  llm_input?: LlmMessage[];
}

export interface LlmMessage {
  role: string;
  content?: string;
  tool_calls?: Array<{
    name: string;
    arguments: Record<string, unknown>;
  }>;
  name?: string;
  tool_call_id?: string;
}

export interface LlmCall {
  iteration: number;
  input: LlmMessage[];
  output: {
    content: string;
    has_tool_calls: boolean;
    tool_calls: Array<{
      name: string;
      arguments: Record<string, unknown>;
      id: string;
    }>;
  };
}

export interface QueryResponse {
  status: string;
  question: string;
  answer: string | null;
  tool_calls: ToolCall[];
  thoughts: Thought[];
  iterations: number;
  elapsed_ms?: number;
  error?: string;
  llm_calls: LlmCall[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  tool_calls?: ToolCall[];
  thoughts?: Thought[];
  llm_calls?: LlmCall[];
  timestamp: Date;
}

export interface DatabaseStatus {
  connected: boolean;
  db_type: string | null;
}
