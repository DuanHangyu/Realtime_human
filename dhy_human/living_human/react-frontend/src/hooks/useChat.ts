import { useState, useCallback, useRef } from 'react';

export interface Message {
  id: number;
  side: 'left' | 'right';
  content: string;
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const nextIdRef = useRef(1);

  const addUserMessage = useCallback((text: string) => {
    const id = nextIdRef.current++;
    setMessages((prev) => [...prev, { id, side: 'right', content: text }]);
  }, []);

  const addBotMessage = useCallback((): number => {
    const id = nextIdRef.current++;
    setMessages((prev) => [...prev, { id, side: 'left', content: '' }]);
    return id;
  }, []);

  const updateBotMessage = useCallback((id: number, appendText: string) => {
    setMessages((prev) =>
      prev.map((msg) =>
        msg.id === id ? { ...msg, content: msg.content + appendText } : msg
      )
    );
  }, []);

  return { messages, addUserMessage, addBotMessage, updateBotMessage };
}
