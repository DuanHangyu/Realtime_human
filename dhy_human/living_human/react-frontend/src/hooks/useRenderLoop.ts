import { useCallback, useRef } from 'react';
import { mat4 } from 'gl-matrix';
import { allocateMemory, freeMemory } from '../lib/wasmMemory';

interface RenderLoopDeps {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  canvasVideoRef: React.RefObject<HTMLCanvasElement | null>;
  canvasGlRef: React.RefObject<HTMLCanvasElement | null>;
  module: any;
  glStateRef: React.MutableRefObject<any>;
  renderImage: (
    mat_world: number[],
    subPoints: number[],
    bsArray: Float32Array
  ) => void;
}

export function useRenderLoop(deps: RenderLoopDeps) {
  const rafRef = useRef<number>(0);
  const activeRef = useRef(false);

  const start = useCallback(() => {
    if (activeRef.current) return;
    activeRef.current = true;

    const {
      videoRef,
      canvasVideoRef,
      canvasGlRef,
      module,
      glStateRef,
      renderImage,
    } = deps;

    const video = videoRef.current!;
    const canvas_video = canvasVideoRef.current!;
    const ctx_video = canvas_video.getContext('2d')!;

    canvas_video.width = video.videoWidth;
    canvas_video.height = video.videoHeight;

    let lastDataSetIndex = -1;
    let isProcessing = false;
    let lastVideoTime = 0;

    const frameCallback = async () => {
      if (!video.paused && !video.ended && !isProcessing) {
        isProcessing = true;

        try {
          const currentDataSetIndex = Math.floor(video.currentTime * 25);
          lastVideoTime = video.currentTime;

          const state = glStateRef.current;
          if (
            lastDataSetIndex !== currentDataSetIndex &&
            currentDataSetIndex < state.dataSets.length - 1
          ) {
            lastDataSetIndex = currentDataSetIndex;

            ctx_video.clearRect(
              0,
              0,
              canvas_video.width,
              canvas_video.height
            );
            ctx_video.drawImage(
              video,
              0,
              0,
              canvas_video.width,
              canvas_video.height
            );

            if (currentDataSetIndex < state.dataSets.length - 1) {
              const floatArraySize = 12;
              const floatArrayBytes = floatArraySize * 4;

              const bsPtr = allocateMemory(module, floatArrayBytes);
              module._updateBlendShape(bsPtr, floatArrayBytes);
              const bsArray = new Float32Array(
                module.HEAPU8.buffer,
                bsPtr,
                floatArraySize
              );

              const dataSet = state.dataSets[currentDataSetIndex];
              const rect = dataSet.rect;

              const currentTimeStamp = 0.04 * currentDataSetIndex;
              const nextTimeStamp = 0.04 * (currentDataSetIndex + 1);
              const currentpoints =
                state.dataSets[currentDataSetIndex].points;
              const nextpoints =
                state.dataSets[currentDataSetIndex + 1].points;

              const t =
                (video.currentTime - currentTimeStamp) /
                (nextTimeStamp - currentTimeStamp);
              const points = currentpoints.map(
                (xi: number, index: number) =>
                  (1 - t) * xi + t * nextpoints[index]
              );

              const matrix = mat4.create();
              mat4.set(
                matrix,
                points[0],
                points[1],
                points[2],
                points[3],
                points[4],
                points[5],
                points[6],
                points[7],
                points[8],
                points[9],
                points[10],
                points[11],
                points[12],
                points[13],
                points[14],
                points[15]
              );
              const subPoints = points.slice(16);
              renderImage(
                Array.from(matrix),
                subPoints,
                bsArray
              );

              // Create temp canvas for cropping
              const tempCanvas = document.createElement('canvas');
              const tempCtx = tempCanvas.getContext('2d')!;

              tempCanvas.width = rect[2] - rect[0];
              tempCanvas.height = rect[3] - rect[1];
              tempCtx.drawImage(
                video,
                rect[0],
                rect[1],
                rect[2] - rect[0],
                rect[3] - rect[1],
                0,
                0,
                tempCanvas.width,
                tempCanvas.height
              );

              // Resize to 128x128
              state.resizedCanvas.width = 128;
              state.resizedCanvas.height = 128;
              state.resizedCtx.drawImage(tempCanvas, 0, 0, 128, 128);

              const imageData = state.resizedCtx.getImageData(0, 0, 128, 128);
              const data = imageData.data;

              const imageDataPtr = allocateMemory(module, data.length);
              module.HEAPU8.set(data, imageDataPtr);

              const imageDataGlPtr = allocateMemory(
                module,
                state.pixels_fbo.length
              );
              module.HEAPU8.set(state.pixels_fbo, imageDataGlPtr);

              module._processImage(
                imageDataPtr,
                128,
                128,
                imageDataGlPtr,
                128,
                128
              );
              const result = module.HEAPU8.subarray(
                imageDataPtr,
                imageDataPtr + data.length
              );

              imageData.data.set(result);

              state.resizedCtx.putImageData(imageData, 0, 0);
              tempCtx.clearRect(
                0,
                0,
                tempCanvas.width,
                tempCanvas.height
              );
              tempCtx.drawImage(
                state.resizedCanvas,
                0,
                0,
                tempCanvas.width,
                tempCanvas.height
              );

              ctx_video.drawImage(tempCanvas, rect[0], rect[1]);

              freeMemory(module, imageDataPtr);
              freeMemory(module, imageDataGlPtr);
              freeMemory(module, bsPtr);
            }
          }

          isProcessing = false;
        } catch (error) {
          console.error('Error processing frame:', error);
          isProcessing = false;
        }

        rafRef.current = requestAnimationFrame(frameCallback);
      } else {
        rafRef.current = requestAnimationFrame(frameCallback);
      }
    };

    rafRef.current = requestAnimationFrame(frameCallback);
  }, [deps]);

  const stop = useCallback(() => {
    activeRef.current = false;
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = 0;
    }
  }, []);

  return { start, stop };
}
