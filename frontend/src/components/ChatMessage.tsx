import type { ChatMessage as ChatMessageType } from '@/types';
import ToolCallCard from './ToolCallCard';
import ThoughtCard from './ThoughtCard';
import LlmCallViewer from './LlmCallViewer';

interface ChatMessageProps {
  message: ChatMessageType;
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex gap-3 mb-4 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      <div
        className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
          isUser ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'
        }`}
      >
        {isUser ? 'U' : 'AI'}
      </div>
      <div
        className={`max-w-[75%] ${
          isUser
            ? 'bg-blue-500 text-white rounded-2xl rounded-tr-sm px-4 py-3'
            : 'bg-gray-100 text-gray-800 rounded-2xl rounded-tl-sm px-4 py-3'
        }`}
      >
        <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        
        {!isUser && message.thoughts && message.thoughts.length > 0 && (
          <div className="mt-3 space-y-2">
            {message.thoughts.map((thought, index) => (
              <ThoughtCard key={index} thought={thought} />
            ))}
          </div>
        )}

        {!isUser && message.tool_calls && message.tool_calls.length > 0 && (
          <div className="mt-3 space-y-2">
            {message.tool_calls.map((toolCall, index) => (
              <ToolCallCard key={index} toolCall={toolCall} />
            ))}
          </div>
        )}

        {!isUser && message.llm_calls && message.llm_calls.length > 0 && (
          <LlmCallViewer llmCalls={message.llm_calls} />
        )}
      </div>
    </div>
  );
}
