interface VoiceInputButtonProps {
  visible: boolean;
  animClass: string;
  isRecording: boolean;
  onSwitchToText: () => void;
  onToggleRecording: () => void;
}

const WAVE_DELAYS = [0, 0.15, 0.3, 0.45, 0.6];

export function VoiceInputButton({
  visible,
  animClass,
  isRecording,
  onSwitchToText,
  onToggleRecording,
}: VoiceInputButtonProps) {
  if (!visible && !animClass) return null;

  return (
    <div className={`voice-bar ${animClass}`}>
      <div className="voice-waves">
        {WAVE_DELAYS.map((delay, i) => (
          <span
            key={i}
            className={`wave-bar ${isRecording ? 'wave-bar-active' : ''}`}
            style={{ animationDelay: `${delay}s` }}
          />
        ))}
      </div>
      <button
        className={`voice-record-btn ${isRecording ? 'recording' : ''}`}
        onClick={onToggleRecording}
      >
        <img src="image/voice.svg" alt="麦克风" />
        <span>{isRecording ? '录音中...' : '点击录音'}</span>
      </button>
      <button
        className="switch-text-btn"
        onClick={onSwitchToText}
        aria-label="切换到文字输入"
      >
        <img src="image/text.svg" alt="文字输入" />
      </button>
    </div>
  );
}
