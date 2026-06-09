import { useState } from 'react';
import { Code2, CheckCircle, XCircle, ChevronDown, ChevronUp } from 'lucide-react';
import type { ToolCall } from '@/types';

interface ToolCallCardProps {
  toolCall: ToolCall;
}

export default function ToolCallCard({ toolCall }: ToolCallCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const formatResult = (result: unknown): string => {
    if (typeof result === 'object' && result !== null) {
      return JSON.stringify(result, null, 2);
    }
    return String(result);
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg mt-2 overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-3 hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Code2 className="w-4 h-4 text-purple-500" />
          <span className="font-medium text-sm text-gray-700">
            工具调用: {toolCall.tool}
          </span>
          {toolCall.success ? (
            <CheckCircle className="w-4 h-4 text-green-500" />
          ) : (
            <XCircle className="w-4 h-4 text-red-500" />
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">
            {toolCall.elapsed_ms !== undefined ? toolCall.elapsed_ms.toFixed(2) : '0.00'}ms
          </span>
          {isExpanded ? (
            <ChevronUp className="w-4 h-4 text-gray-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-gray-400" />
          )}
        </div>
      </button>

      {isExpanded && (
        <div className="px-3 pb-3 space-y-2 text-xs border-t border-gray-100">
          <div className="pt-3">
            <span className="text-gray-500">参数:</span>
            <pre className="bg-gray-50 rounded p-2 mt-1 overflow-x-auto">
              <code className="text-gray-700">
                {JSON.stringify(toolCall.arguments, null, 2)}
              </code>
            </pre>
          </div>

          <div>
            <span className="text-gray-500">结果:</span>
            <pre
              className={`rounded p-2 mt-1 overflow-x-auto ${
                toolCall.success ? 'bg-green-50' : 'bg-red-50'
              }`}
            >
              <code className={toolCall.success ? 'text-green-700' : 'text-red-700'}>
                {formatResult(toolCall.result)}
              </code>
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}