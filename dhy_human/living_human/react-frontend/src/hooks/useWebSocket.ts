import { useRef, useCallback } from 'react';
import type { CharacterConfig } from '../types/character';

interface WebSocketCallbacks {
  onUserMessage: (text: string) => void;
  onLLMStart: (text: string) => void;
  onTTSData: (audioData: string, text: string) => void;
}

export function useWebSocket(callbacks: WebSocketCallbacks) {
  const socketRef = useRef<WebSocket | null>(null);
  const callbacksRef = useRef(callbacks);
  callbacksRef.current = callbacks;

  const connect = useCallback((charConfig?: CharacterConfig) => {
    // Close existing connection if any
    if (socketRef.current) {
      socketRef.current.close();
    }

    const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const socket = new WebSocket(
      `${wsProtocol}//${location.hostname}:19465/recognition?isSendConfig=true`
    );

    socket.addEventListener('open', () => {
      console.log('WebSocket connected');
      const systemMessage = charConfig?.systemMessage ?? '';
      const voiceType = charConfig?.voiceType ?? 'BV007_streaming';
      const data = { systemMessage, voiceType };
      socket.send(JSON.stringify(data));
    });

    socket.addEventListener('message', (event) => {
      try {
        const jsonData = JSON.parse(event.data);
        const cb = callbacksRef.current;

        if (jsonData.DataType === 'TTS') {
          const dataJson = JSON.parse(jsonData.Data);
          const audioData = dataJson.AudioData;
          const text = dataJson.Text;
          if (!/^\s*$/.test(audioData)) {
            cb.onTTSData(audioData, text);
          } else {
            // Still update text even if no audio
            cb.onTTSData('', text);
          }
        } else if (jsonData.DataType === 'StartLLM') {
          cb.onLLMStart(jsonData.Data);
        }
      } catch (error) {
        console.error('解析 JSON 失败:', error);
      }
    });

    socket.addEventListener('error', (event) => {
      console.error('WebSocket error:', event);
    });

    socketRef.current = socket;
  }, []);

  const send = useCallback((data: string | ArrayBuffer | Blob) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(data);
    } else {
      console.warn('WebSocket not open, readyState:', socketRef.current?.readyState);
    }
  }, []);

  const getReadyState = useCallback(() => {
    return socketRef.current?.readyState;
  }, []);

  return { socketRef, connect, send, getReadyState };
}
