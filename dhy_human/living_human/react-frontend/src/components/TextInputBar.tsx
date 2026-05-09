interface TextInputBarProps {
  visible: boolean;
  animClass: string;
  onSend: (text: string) => void;
  onSwitchToVoice: () => void;
}

import { useRef } from 'react';

export function TextInputBar({
  visible,
  animClass,
  onSend,
  onSwitchToVoice,
}: TextInputBarProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  if (!visible && !animClass) return null;

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      const value = inputRef.current?.value ?? '';
      if (value.trim() !== '') {
        onSend(value);
        if (inputRef.current) inputRef.current.value = '';
      }
    }
  };

  const handleSubmit = () => {
    const value = inputRef.current?.value ?? '';
    if (value.trim() !== '') {
      onSend(value);
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  return (
    <div
      className={`container ${animClass}`}
      id="TextInputDiv"
      style={{ display: 'flex' }}
    >
      <button id="switchMode" name="switchVoice" onClick={onSwitchToVoice}>
        <img src="image/voice.svg" alt="语音输入" width="40" height="40" />
      </button>
      <input
        ref={inputRef}
        type="text"
        id="userInput"
        placeholder="请输入..."
        onKeyDown={handleKeyDown}
      />
      <button id="submitButton" onClick={handleSubmit}>
        发送
      </button>
    </div>
  );
}
