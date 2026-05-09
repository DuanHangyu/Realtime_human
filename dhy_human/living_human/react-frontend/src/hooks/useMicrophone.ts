import { useRef, useCallback } from 'react';

export function useMicrophone(
  socketRef: React.RefObject<WebSocket | null>,
  isRecognitionActive: React.MutableRefObject<boolean>
) {
  const microphoneStreamRef = useRef<MediaStream | null>(null);

  const startMicrophone = useCallback(() => {
    if (microphoneStreamRef.current) return;

    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then((stream) => {
        microphoneStreamRef.current = stream;

        const audioContext = new window.AudioContext();
        const microphoneSource =
          audioContext.createMediaStreamSource(microphoneStreamRef.current);

        const scriptProcessor = audioContext.createScriptProcessor(4096, 1, 1);

        const biquadFilter = audioContext.createBiquadFilter();
        biquadFilter.type = 'lowpass';
        biquadFilter.frequency.setValueAtTime(8000, audioContext.currentTime);

        microphoneSource.connect(biquadFilter);
        biquadFilter.connect(scriptProcessor);

        scriptProcessor.onaudioprocess = (event) => {
          if (!isRecognitionActive.current) return;
          if (
            !socketRef.current ||
            socketRef.current.readyState !== WebSocket.OPEN
          )
            return;

          const audioData = event.inputBuffer.getChannelData(0);
          const sampleRateRatio = audioContext.sampleRate / 16000;
          const newLength = Math.round(audioData.length / sampleRateRatio);
          const resampledData = new Float32Array(newLength);

          for (let i = 0; i < newLength; i++) {
            resampledData[i] = audioData[Math.round(i * sampleRateRatio)];
          }

          socketRef.current.send(floatTo16BitPCM(resampledData).buffer as ArrayBuffer);
        };

        scriptProcessor.connect(audioContext.destination);
      })
      .catch((error) => {
        console.error('Microphone error:', error);
      });
  }, [socketRef, isRecognitionActive]);

  return { startMicrophone };
}

function floatTo16BitPCM(samples: Float32Array): Int16Array {
  const length = samples.length;
  const int16Array = new Int16Array(length);

  for (let i = 0; i < length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    int16Array[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }

  return int16Array;
}
