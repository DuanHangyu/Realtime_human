// WASM memory management utilities

interface WasmModule {
  _malloc(size: number): number;
  _free(ptr: number): void;
  HEAPU8: Uint8Array;
}

export function allocateMemory(module: WasmModule, size: number): number {
  const ptr = module._malloc(size);
  if (ptr === 0) throw new Error('Failed to allocate memory');
  return ptr;
}

export function freeMemory(module: WasmModule, ptr: number): void {
  if (ptr !== null && ptr !== 0) {
    module._free(ptr);
  }
}

export function playWavAudio(module: WasmModule, arrayBuffer: ArrayBuffer): void {
  const view = new Uint8Array(arrayBuffer);
  const arrayBufferPtr = module._malloc(arrayBuffer.byteLength);
  module.HEAPU8.set(view, arrayBufferPtr);
  (module as any)._setAudioBuffer(arrayBufferPtr, arrayBuffer.byteLength);
  module._free(arrayBufferPtr);
}
