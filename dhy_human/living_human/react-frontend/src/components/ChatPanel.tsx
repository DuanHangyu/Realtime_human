import { useEffect, useRef } from 'react';
import type { Message } from '../hooks/useChat';
import { ChatBubble } from './ChatBubble';

interface ChatPanelProps {
  messages: Message[];
}

export function ChatPanel({ messages }: ChatPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  }, [messages]);

  return (
    <div className="scroll-container" id="scrollContainer" ref={scrollRef}>
      {messages.map((msg) => (
        <ChatBubble key={msg.id} message={msg} />
      ))}
    </div>
  );
}
