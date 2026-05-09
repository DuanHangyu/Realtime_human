import { useRef, useState, useEffect, useCallback } from 'react';
import { BackgroundElements } from './components/BackgroundElements';
import { ChatPanel } from './components/ChatPanel';
import { TextInputBar } from './components/TextInputBar';
import { VoiceInputButton } from './components/VoiceInputButton';
import { CharacterSelector } from './components/CharacterSelector';
import { useWasm } from './hooks/useWasm';
import { useWebGL } from './hooks/useWebGL';
import { useRenderLoop } from './hooks/useRenderLoop';
import { useWebSocket } from './hooks/useWebSocket';
import { useAudio } from './hooks/useAudio';
import { useChat } from './hooks/useChat';
import { useMicrophone } from './hooks/useMicrophone';
import { useCharacter } from './hooks/useCharacter';
import { getCharacterAssets } from './lib/characterPaths';

function base64ToArrayBuffer(base64: string): ArrayBuffer {
  const binaryString = atob(base64);
  const length = binaryString.length;
  const bytes = new Uint8Array(length);
  for (let i = 0; i < length; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes.buffer;
}

type InputMode = 'text' | 'voice';

export default function App() {
  // Refs for DOM elements
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasGlRef = useRef<HTMLCanvasElement>(null);
  const canvasVideoRef = useRef<HTMLCanvasElement>(null);
  const screenRef = useRef<HTMLDivElement>(null);

  // State
  const [inputMode, setInputMode] = useState<InputMode>('text');
  const [textInputAnim, setTextInputAnim] = useState('');
  const [voiceInputAnim, setVoiceInputAnim] = useState('');
  const [webglReady, setWebglReady] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [switching, setSwitching] = useState(false);

  // Recognition control ref (mutable, avoids re-renders)
  const isRecognitionActiveRef = useRef(false);
  const currentBotMsgIdRef = useRef<number | null>(null);

  // Character management
  const { characters, currentCharId, setCurrentCharId, loaded, deleteCharacter } = useCharacter();
  const charactersRef = useRef(characters);
  charactersRef.current = characters;

  // Hooks
  const { moduleRef, ready: wasmReady } = useWasm(screenRef);
  const { glStateRef, initWebGL, loadCharacter, renderImage } = useWebGL(
    canvasGlRef,
    moduleRef.current
  );
  const { start: startRenderLoop, stop: stopRenderLoop } = useRenderLoop({
    videoRef,
    canvasVideoRef,
    canvasGlRef,
    module: moduleRef.current,
    glStateRef,
    renderImage,
  });

  const { messages, addUserMessage, addBotMessage, updateBotMessage } =
    useChat();
  const { initContext, enqueueAudio, clearQueue } = useAudio(moduleRef);
  const { socketRef, connect, send } = useWebSocket({
    onUserMessage: (text) => {
      addUserMessage(text);
    },
    onLLMStart: (text) => {
      addUserMessage(text);
      isRecognitionActiveRef.current = false;
      setIsRecording(false);
      const botId = addBotMessage();
      currentBotMsgIdRef.current = botId;
      clearQueue();
      initContext();
    },
    onTTSData: (audioData, text) => {
      if (currentBotMsgIdRef.current !== null) {
        updateBotMessage(currentBotMsgIdRef.current, text);
      }
      if (audioData && !/^\s*$/.test(audioData)) {
        const audioUint8Array = base64ToArrayBuffer(audioData);
        enqueueAudio(audioUint8Array);
      }
    },
  });

  const { startMicrophone } = useMicrophone(socketRef, isRecognitionActiveRef);

  // Initialize WebGL after WASM is ready, then auto-start video + render loop
  useEffect(() => {
    if (!wasmReady) return;

    // Set initial video source imperatively (avoid React re-render overwriting it)
    const video = videoRef.current;
    if (video) {
      video.src = getCharacterAssets(currentCharId).videoUrl;
    }

    initWebGL(currentCharId)
      .then(async () => {
        setWebglReady(true);

        if (video) {
          await video.play();
          if (moduleRef.current) {
            startRenderLoop();
          }
        }
      })
      .catch((err) => {
        console.error('WebGL init failed:', err);
      });
  }, [wasmReady]);

  // Connect WebSocket once characters are loaded and when character changes
  useEffect(() => {
    if (!loaded) return;
    const char = charactersRef.current.find((c) => c.id === currentCharId);
    if (!char) return;
    connect(char);
    return () => {
      if (socketRef.current) {
        socketRef.current.close();
      }
    };
  }, [connect, currentCharId, loaded]);

  // Add initial greeting message
  const greetingAddedRef = useRef(false);
  useEffect(() => {
    if (greetingAddedRef.current) return;
    greetingAddedRef.current = true;
    const botId = addBotMessage();
    updateBotMessage(botId, '快和我聊天吧！');
  }, []);

  // Input mode switching
  const switchInputMode = useCallback(
    (mode: InputMode) => {
      setInputMode(mode);
      setIsRecording(false);
      isRecognitionActiveRef.current = false;

      if (mode === 'voice') {
        startMicrophone();
        setVoiceInputAnim('show-with-animation');
        setTextInputAnim('hide-with-animation');
      } else {
        setTextInputAnim('show-with-animation');
        setVoiceInputAnim('hide-with-animation');
      }
    },
    [startMicrophone]
  );

  const toggleRecording = useCallback(() => {
    setIsRecording((prev) => {
      const next = !prev;
      isRecognitionActiveRef.current = next;
      return next;
    });
  }, []);

  // Handle text input send
  const handleSend = useCallback(
    (text: string) => {
      if (text.trim() !== '') {
        send(text);
      }
    },
    [send]
  );

  // Handle character switching
  const handleSwitchCharacter = useCallback(
    async (newCharId: string) => {
      if (newCharId === currentCharId || switching) return;
      setSwitching(true);

      try {
        const video = videoRef.current;
        if (!video) return;

        // 1. Stop render loop
        stopRenderLoop();

        // 2. Pause video
        video.pause();

        // 3. Switch video source
        const assets = getCharacterAssets(newCharId);
        video.src = assets.videoUrl;
        video.load();

        // 4. Wait for video to load new data (with timeout + error handling)
        await new Promise<void>((resolve, reject) => {
          const timeout = setTimeout(() => {
            cleanup();
            reject(new Error('Video load timed out'));
          }, 10000);

          const onLoaded = () => {
            cleanup();
            resolve();
          };

          const onError = () => {
            cleanup();
            reject(new Error('Video load failed'));
          };

          const cleanup = () => {
            clearTimeout(timeout);
            video.removeEventListener('loadeddata', onLoaded);
            video.removeEventListener('error', onError);
          };

          video.addEventListener('loadeddata', onLoaded);
          video.addEventListener('error', onError);
        });

        // 5. Load new character GL data
        await loadCharacter(newCharId);

        // 6. Update current character state (UI highlight)
        setCurrentCharId(newCharId);

        // 7. Start playback
        await video.play();

        // 8. Start render loop
        startRenderLoop();
      } catch (err) {
        console.error('Character switch failed:', err);
      } finally {
        setSwitching(false);
      }
    },
    [currentCharId, switching, stopRenderLoop, loadCharacter, setCurrentCharId, startRenderLoop]
  );

  return (
    <>
      <BackgroundElements />

      <video
        id="video"
        ref={videoRef}
        autoPlay
        muted
        loop
        playsInline
        preload="auto"
        disablePictureInPicture
      />

      <canvas id="canvas_video" ref={canvasVideoRef}></canvas>
      <canvas id="canvas_gl" ref={canvasGlRef} width="128" height="128"></canvas>

      <TextInputBar
        visible={inputMode === 'text'}
        animClass={textInputAnim}
        onSend={handleSend}
        onSwitchToVoice={() => switchInputMode('voice')}
      />

      <VoiceInputButton
        visible={inputMode === 'voice'}
        animClass={voiceInputAnim}
        isRecording={isRecording}
        onSwitchToText={() => switchInputMode('text')}
        onToggleRecording={toggleRecording}
      />

      <CharacterSelector
        characters={characters}
        currentCharId={currentCharId}
        switching={switching}
        onSelect={handleSwitchCharacter}
        onDelete={deleteCharacter}
      />

      <div id="screen" ref={screenRef}></div>

      <ChatPanel messages={messages} />
    </>
  );
}
