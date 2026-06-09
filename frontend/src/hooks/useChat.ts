import { useState, useCallback } from 'react';
import type { ChatMessage, QueryResponse } from '@/types';
import { queryAgent } from '@/services/api';

export const useChat = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = useCallback(async (question: string) => {
    if (!question.trim()) return;

    setIsLoading(true);
    setError(null);

    const userMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: question,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);

    try {
      const response: QueryResponse = await queryAgent(question);

      const assistantMessage: ChatMessage = {
        id: `msg-${Date.now()}-assistant`,
        role: 'assistant',
        content: response.answer || response.error || '未获取到回答',
        tool_calls: response.tool_calls,
        thoughts: response.thoughts,
        llm_calls: response.llm_calls,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : '请求失败';
      setError(errorMessage);

      const errorMessageItem: ChatMessage = {
        id: `msg-${Date.now()}-error`,
        role: 'assistant',
        content: `错误: ${errorMessage}`,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, errorMessageItem]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setError(null);
  }, []);

  return {
    messages,
    isLoading,
    error,
    sendMessage,
    clearMessages,
  };
};
