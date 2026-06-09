import { useState } from 'react';
import { Lightbulb, ArrowRight, ChevronDown, ChevronRight, Send } from 'lucide-react';
import type { Thought, LlmMessage } from '@/types';

interface ThoughtCardProps {
  thought: Thought;
}

function LlmInputViewer({ messages }: { messages: LlmMessage[] }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="mt-3 border-t border-amber-200 pt-2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800"
      >
        {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        <Send className="w-3 h-3" />
        查看发送给 LLM 的输入
      </button>
      {expanded && (
        <div className="mt-2 bg-white rounded border border-blue-100 p-2 text-xs max-h-96 overflow-y-auto">
          {messages.map((msg, idx) => (
            <div key={idx} className="mb-2 pb-2 border-b border-gray-100 last:border-0">
              <div className="font-medium text-blue-600 capitalize">{msg.role}</div>
              {msg.content && (
                <pre className="mt-1 whitespace-pre-wrap text-gray-600 font-sans overflow-x-auto">
                  {msg.content.length > 500 ? msg.content.slice(0, 500) + '...' : msg.content}
                </pre>
              )}
              {msg.tool_calls && msg.tool_calls.length > 0 && (
                <div className="mt-1">
                  <span className="text-purple-600">工具调用: </span>
                  {msg.tool_calls.map((tc, tcIdx) => (
                    <div key={tcIdx} className="ml-2 text-purple-500">
                      {tc.name}({JSON.stringify(tc.arguments)})
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ThoughtCard({ thought }: ThoughtCardProps) {
  return (
    <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mt-2">
      <div className="flex items-center gap-2 mb-1">
        <Lightbulb className="w-4 h-4 text-amber-500" />
        <span className="text-xs font-medium text-amber-700">
          思考 #{thought.iteration}
        </span>
        {thought.has_tool_calls && (
          <ArrowRight className="w-3 h-3 text-amber-500" />
        )}
      </div>
      <p className="text-sm text-amber-800">{thought.thought}</p>
      {thought.llm_input && thought.llm_input.length > 0 && (
        <LlmInputViewer messages={thought.llm_input} />
      )}
    </div>
  );
}