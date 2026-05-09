import { useRef, useCallback } from 'react';
import { playWavAudio } from '../lib/wasmMemory';

export function useAudio(moduleRef: React.MutableRefObject<any>) {
  const audioContextRef = useRef<AudioContext | null>(null);
  const isPlayingRef = useRef(false);
  const audioQueueRef = useRef<ArrayBuffer[]>([]);

  const initContext = useCallback(() => {
    if (
      !audioContextRef.current ||
      audioContextRef.current.state === 'closed'
    ) {
      audioContextRef.current = new (window.AudioContext ||
        (window as any).webkitAudioContext)({
        latencyHint: 'interactive',
      });
    } else if (audioContextRef.current.state === 'suspended') {
      audioContextRef.current.resume();
    }
  }, []);

  const enqueueAudio = useCallback(
    (arrayBuffer: ArrayBuffer) => {
      audioQueueRef.current.push(arrayBuffer);
      playNext();
    },
    []
  );

  const clearQueue = useCallback(() => {
    audioQueueRef.current = [];
  }, []);

  const playNext = useCallback(() => {
    if (isPlayingRef.current) return;
    if (audioQueueRef.current.length === 0) return;

    isPlayingRef.current = true;

    const audioUint8Array = audioQueueRef.current.shift()!;
    const module = moduleRef.current;
    if (module) {
      playWavAudio(module, audioUint8Array);
    }

    const ctx = audioContextRef.current;
    if (!ctx) {
      isPlayingRef.current = false;
      return;
    }

    // Decode a fresh copy since the original was consumed by WASM
    ctx.decodeAudioData(audioUint8Array.slice(0), (audioBuffer) => {
      const source = ctx.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(ctx.destination);
      source.start(0);
      source.onended = () => {
        isPlayingRef.current = false;
        if (audioQueueRef.current.length > 0) {
          playNext();
        }
      };
    });
  }, [moduleRef]);

  const getIsPlaying = useCallback(() => isPlayingRef.current, []);

  return { initContext, enqueueAudio, clearQueue, getIsPlaying };
}
