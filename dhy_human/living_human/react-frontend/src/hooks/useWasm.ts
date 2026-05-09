import { useEffect, useRef, useState } from 'react';
import { loadEmscriptenModule } from '../lib/emscriptenLoader';

export function useWasm(screenRef: React.RefObject<HTMLDivElement | null>) {
  const moduleRef = useRef<any>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!screenRef.current) return;

    loadEmscriptenModule(screenRef.current)
      .then((instance) => {
        moduleRef.current = instance;
        setReady(true);
      })
      .catch((err) => {
        console.error('Failed to load WASM module:', err);
      });
  }, []);

  return { moduleRef, ready };
}
