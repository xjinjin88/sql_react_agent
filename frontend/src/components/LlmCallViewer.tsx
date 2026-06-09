import { useState } from 'react';
import { ChevronDown, ChevronRight, MessageSquare, Send } from 'lucide-react';
import type { LlmCall } from '@/types';

interface LlmCallViewerProps {
  llmCalls: LlmCall[];
}

function MessageContent({ role, content, tool_calls }: { role: string; content?: string; tool_calls?: Array<{ name: string; arguments: Record<string, unknown> }> }) {
  return (
    <div className="mb-2 pb-2 border-b border-gray-100 last:border-0">
      <div className={`font-medium capitalize ${
        role === 'system' ? 'text-green-600' :
        role === 'user' ? 'text-blue-600' :
        role === 'assistant' ? 'text-purple-600' :
        role === 'tool' ? 'text-orange-600' : 'text-gray-600'
      }`}>
        {role}
      </div>
      {content && (
        <pre className="mt-1 whitespace-pre-wrap text-sm text-gray-700 font-sans overflow-x-auto max-h-64">
          {content.length > 3000 ? content.slice(0, 3000) + '...' : content}
        </pre>
      )}
      {tool_calls && tool_calls.length > 0 && (
        <div className="mt-1">
          <span className="text-purple-600 text-xs">工具调用:</span>
          {tool_calls.map((tc, tcIdx) => (
            <div key={tcIdx} className="ml-2 text-xs text-purple-500">
              {tc.name}({JSON.stringify(tc.arguments)})
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function LlmCallViewer({ llmCalls }: LlmCallViewerProps) {
  const [expanded, setExpanded] = useState(false);
  const [expandedIteration, setExpandedIteration] = useState<number | null>(null);

  return (
    <div className="mt-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 transition-colors"
      >
        {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        <MessageSquare className="w-4 h-4" />
        <span>查看 LLM 调用记录 ({llmCalls.length} 次)</span>
      </button>

      {expanded && (
        <div className="mt-2 space-y-3">
          {llmCalls.map((llmCall) => (
            <div key={llmCall.iteration} className="border border-blue-100 rounded-lg overflow-hidden">
              <button
                onClick={() => setExpandedIteration(
                  expandedIteration === llmCall.iteration ? null : llmCall.iteration
                )}
                className="w-full flex items-center justify-between px-4 py-2 bg-blue-50 hover:bg-blue-100 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-blue-700">
                    迭代 #{llmCall.iteration}
                  </span>
                  {llmCall.output.has_tool_calls && (
                    <span className="text-xs px-2 py-0.5 bg-purple-100 text-purple-600 rounded">
                      工具调用
                    </span>
                  )}
                </div>
                {expandedIteration === llmCall.iteration ? (
                  <ChevronDown className="w-4 h-4 text-blue-500" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-blue-500" />
                )}
              </button>

              {expandedIteration === llmCall.iteration && (
                <div className="p-4 space-y-4">
                  <div className="border-l-2 border-blue-400 pl-3">
                    <div className="flex items-center gap-2 mb-2">
                      <Send className="w-4 h-4 text-blue-500" />
                      <span className="text-xs font-medium text-blue-600">发送给 LLM 的输入</span>
                    </div>
                    <div className="bg-white rounded border border-blue-100 p-3 text-xs">
                      {llmCall.input.map((msg, idx) => (
                        <MessageContent key={idx} {...msg} />
                      ))}
                    </div>
                  </div>

                  <div className="border-l-2 border-green-400 pl-3">
                    <div className="flex items-center gap-2 mb-2">
                      <MessageSquare className="w-4 h-4 text-green-500" />
                      <span className="text-xs font-medium text-green-600">LLM 的输出</span>
                    </div>
                    <div className="bg-white rounded border border-green-100 p-3">
                      {llmCall.output.content && (
                        <pre className="text-sm text-gray-700 whitespace-pre-wrap">
                          {llmCall.output.content}
                        </pre>
                      )}
                      {llmCall.output.tool_calls && llmCall.output.tool_calls.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-gray-100">
                          <span className="text-xs text-purple-600 font-medium">工具调用:</span>
                          {llmCall.output.tool_calls.map((tc, tcIdx) => (
                            <div key={tcIdx} className="ml-2 mt-1 text-xs">
                              <span className="text-purple-500 font-medium">{tc.name}</span>
                              <span className="text-gray-500 ml-1">
                                ({JSON.stringify(tc.arguments)})
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
