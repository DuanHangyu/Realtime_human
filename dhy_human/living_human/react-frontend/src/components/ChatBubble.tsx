import type { Message } from '../hooks/useChat';

interface ChatBubbleProps {
  message: Message;
}

export function ChatBubble({ message }: ChatBubbleProps) {
  return (
    <div className="item">
      <div
        className={`${message.side} ${
          message.side === 'left' ? 'align-left' : 'align-right'
        }`}
        style={{
          alignSelf: message.side === 'right' ? 'flex-end' : 'flex-start',
        }}
      >
        {message.content}
      </div>
    </div>
  );
}
