import { useRef, useEffect } from 'react';
import { Bot, Trash2 } from 'lucide-react';
import ChatMessage from '@/components/ChatMessage';
import ChatInput from '@/components/ChatInput';
import DatabaseStatus from '@/components/DatabaseStatus';
import { useChat } from '@/hooks/useChat';

export default function App() {
  const { messages, isLoading, sendMessage, clearMessages } = useChat();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="max-w-4xl mx-auto h-screen flex flex-col">
        <header className="bg-white shadow-sm border-b border-gray-200">
          <div className="px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-500 rounded-xl">
                  <Bot className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h1 className="text-xl font-bold text-gray-800">SQL Agent</h1>
                  <p className="text-sm text-gray-500">智能数据库查询助手</p>
                </div>
              </div>
              <button
                onClick={clearMessages}
                className="flex items-center gap-2 px-4 py-2 text-gray-500 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
              >
                <Trash2 className="w-4 h-4" />
                <span className="text-sm">清空对话</span>
              </button>
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-hidden flex flex-col">
          <div className="p-4">
            <DatabaseStatus />
          </div>

          <div className="flex-1 overflow-y-auto px-4 pb-4">
            {messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-gray-400">
                <Bot className="w-16 h-16 mb-4 opacity-50" />
                <p className="text-lg">欢迎使用 SQL Agent</p>
                <p className="text-sm">输入问题，我会帮您查询数据库</p>
              </div>
            ) : (
              <div className="max-w-3xl mx-auto">
                {messages.map((message) => (
                  <ChatMessage key={message.id} message={message} />
                ))}
                <div ref={messagesEndRef} />
              </div>
            )}

            {isLoading && (
              <div className="flex justify-center mt-4">
                <div className="flex items-center gap-2 text-gray-500">
                  <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
                  <span className="text-sm">正在思考...</span>
                </div>
              </div>
            )}
          </div>
        </main>

        <ChatInput onSend={sendMessage} isLoading={isLoading} />
      </div>
    </div>
  );
}