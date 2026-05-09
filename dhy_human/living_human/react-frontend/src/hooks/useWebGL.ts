import { useRef, useCallback } from 'react';
import pako from 'pako';
import { mat4 } from 'gl-matrix';
import { loadFaceFile } from '../lib/faceLoader';

interface GLState {
  program: WebGLProgram | null;
  positionBuffer: WebGLBuffer | null;
  indexBuffer: WebGLBuffer | null;
  texture_bs: WebGLTexture | null;
  objData: { vertices: number[]; faces: number[] } | null;
  dataSets: any[];
  pixels_fbo: Uint8Array;
  resizedCanvas: HTMLCanvasElement;
  resizedCtx: CanvasRenderingContext2D;
}

const VERTEX_SHADER_SOURCE = `#version 300 es
  layout(location = 0) in vec3 a_position;
  layout(location = 1) in vec2 a_texture;
  uniform float bsVec[12];
  uniform mat4 gProjection;
  uniform mat4 gWorld0;
  uniform sampler2D texture_bs;
  uniform vec2 vertBuffer[209];
  out vec2 v_texture;
  out vec2 v_bias;

  vec4 calculateMorphPosition(vec3 position, vec2 textureCoord) {
      vec4 tmp_Position2 = vec4(position, 1.0);
      if (textureCoord.x < 3.0 && textureCoord.x >= 0.0) {
          vec3 morphSum = vec3(0.0);
          for (int i = 0; i < 6; i++) {
              ivec2 coord = ivec2(int(textureCoord.y), i);
              vec3 morph = texelFetch(texture_bs, coord, 0).xyz * 2.0 - 1.0;
              morphSum += bsVec[i] * morph;
          }
          tmp_Position2.xyz += morphSum;
      }
      else if (textureCoord.x == 4.0) {
          vec3 morphSum = vec3(0.0, (bsVec[0] + bsVec[1]) / 2.7 + 6.0, 0.0);
          tmp_Position2.xyz += morphSum;
      }
      return tmp_Position2;
  }

  void main() {
      mat4 gWorld = gWorld0;

      vec4 tmp_Position2 = calculateMorphPosition(a_position, a_texture);
      vec4 tmp_Position = gWorld * tmp_Position2;

      v_bias = vec2(0.0, 0.0);
      if (a_texture.x == -1.0f) {
          v_bias = vec2(0.0, 0.0);
      }
      else if (a_texture.y < 209.0f) {
          vec4 vert_new = gProjection * vec4(tmp_Position.x, tmp_Position.y, tmp_Position.z, 1.0);
          v_bias = vert_new.xy - (vertBuffer[int(a_texture.y)].xy / 128.0 * 2.0 - 1.0);
      }

      if (a_texture.x >= 3.0f) {
          gl_Position = gProjection * vec4(tmp_Position.x, tmp_Position.y, 500.0, 1.0);
      }
      else {
          gl_Position = gProjection * vec4(tmp_Position.x, tmp_Position.y, tmp_Position.z, 1.0);
      }

      v_texture = a_texture;
  }
`;

const FRAGMENT_SHADER_SOURCE = `#version 300 es
  precision mediump float;
  in mediump vec2 v_texture;
  in mediump vec2 v_bias;
  out vec4 out_color;

  void main() {
      if (v_texture.x == 2.0f) {
          out_color = vec4(1.0, 0.0, 0.0, 1.0);
      }
      else if (v_texture.x > 2.0f && v_texture.x < 2.1f) {
          out_color = vec4(0.5f, 0.0, 0.0f, 1.0);
      }
      else if (v_texture.x == 3.0f) {
          out_color = vec4(0.0, 1.0, 0.0, 1.0);
      }
      else if (v_texture.x == 4.0f) {
          out_color = vec4(0.0, 0.0, 1.0, 1.0);
      }
      else if (v_texture.x > 3.0f && v_texture.x < 4.0f) {
          out_color = vec4(0.0, 0.0, 0.0, 1.0);
      }
      else {
          vec2 wrap = (v_bias.xy + 1.0) / 2.0;
          out_color = vec4(wrap.xy, 0.5, 1.0);
      }
  }
`;

export function useWebGL(
  canvasGlRef: React.RefObject<HTMLCanvasElement | null>,
  module: any
) {
  const glStateRef = useRef<GLState | null>(null);
  const glInitializedRef = useRef(false);

  /** One-time GL setup: context, shaders, program, shared texture, helper canvas */
  const initGL = useCallback(async () => {
    if (glInitializedRef.current) return;
    const gl = canvasGlRef.current?.getContext('webgl2', { antialias: false });
    if (!gl || !module) return;

    const resizedCanvas = document.createElement('canvas');
    const resizedCtx = resizedCanvas.getContext('2d', {
      willReadFrequently: true,
    })!;
    const pixels_fbo = new Uint8Array(128 * 128 * 4);

    // Compile shaders
    const vertexShader = gl.createShader(gl.VERTEX_SHADER)!;
    gl.shaderSource(vertexShader, VERTEX_SHADER_SOURCE);
    gl.compileShader(vertexShader);

    const fragmentShader = gl.createShader(gl.FRAGMENT_SHADER)!;
    gl.shaderSource(fragmentShader, FRAGMENT_SHADER_SOURCE);
    gl.compileShader(fragmentShader);

    const program = gl.createProgram()!;
    gl.attachShader(program, vertexShader);
    gl.attachShader(program, fragmentShader);
    gl.linkProgram(program);
    gl.useProgram(program);

    // Create buffers (data filled later by loadCharacter)
    const positionBuffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 20, 0);
    gl.enableVertexAttribArray(1);
    gl.vertexAttribPointer(1, 2, gl.FLOAT, false, 20, 12);

    const indexBuffer = gl.createBuffer();

    // Load shared bs.png texture
    const texture_bs = gl.createTexture()!;
    const image = new Image();
    image.onload = function () {
      gl.bindTexture(gl.TEXTURE_2D, texture_bs);
      gl.texImage2D(
        gl.TEXTURE_2D,
        0,
        gl.RGBA,
        gl.RGBA,
        gl.UNSIGNED_BYTE,
        image
      );
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.bindTexture(gl.TEXTURE_2D, null);
    };
    image.src = 'share/bs.png';

    glStateRef.current = {
      program,
      positionBuffer,
      indexBuffer,
      texture_bs,
      objData: null,
      dataSets: [],
      pixels_fbo,
      resizedCanvas,
      resizedCtx,
    };

    glInitializedRef.current = true;
  }, [canvasGlRef, module]);

  /** Load character-specific data: fetch data blob, configure WASM, parse mesh, update buffers */
  const loadCharacter = useCallback(async (characterId: string) => {
    const gl = canvasGlRef.current?.getContext('webgl2', { antialias: false });
    const state = glStateRef.current;
    if (!gl || !state) return;

    const dataUrl = `characters/${characterId}/data`;

    const response = await fetch(dataUrl);
    if (!response.ok) {
      throw new Error('Failed to load character data: ' + response.statusText);
    }

    const compressedData = await response.arrayBuffer();
    const decompressedData = pako.inflate(new Uint8Array(compressedData), {
      to: 'string',
    });
    const combinedData = JSON.parse(decompressedData);

    // Pass config to WASM
    const { json_data, ...wasmInputJson } = combinedData;
    const jsonString = JSON.stringify(wasmInputJson);
    const encoder = new TextEncoder();
    const encoded = encoder.encode(jsonString);
    const lengthBytes = encoded.length + 1;
    const stringPointer = module._malloc(lengthBytes);
    module.stringToUTF8(jsonString, stringPointer, lengthBytes);
    module._processJson(stringPointer);
    module._free(stringPointer);

    combinedData.authorized = true;
    combinedData.ref_data = '';

    const dataSets = combinedData.json_data;
    const reversedDataSets = dataSets.concat(dataSets.slice().reverse());
    const objData = loadFaceFile(combinedData.face3D_obj.join('\n'));

    // Update GL buffers with new character mesh data
    gl.bindBuffer(gl.ARRAY_BUFFER, state.positionBuffer);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array(objData.vertices),
      gl.STATIC_DRAW
    );

    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, state.indexBuffer);
    gl.bufferData(
      gl.ELEMENT_ARRAY_BUFFER,
      new Uint16Array(objData.faces),
      gl.STATIC_DRAW
    );

    // Update state immutably
    glStateRef.current = {
      ...state,
      objData,
      dataSets: reversedDataSets,
    };
  }, [canvasGlRef, module]);

  /** Combined init for backward compatibility */
  const initWebGL = useCallback(async (characterId: string = 'default') => {
    await initGL();
    await loadCharacter(characterId);
  }, [initGL, loadCharacter]);

  const renderImage = useCallback(
    (mat_world: number[], subPoints: number[], bsArray: Float32Array) => {
      const gl = canvasGlRef.current?.getContext('webgl2', {
        antialias: false,
      });
      const state = glStateRef.current;
      if (!gl || !state?.program) return;

      gl.useProgram(state.program);
      const worldMatUniformLocation = gl.getUniformLocation(
        state.program,
        'gWorld0'
      );
      gl.uniformMatrix4fv(worldMatUniformLocation, false, mat_world);

      gl.uniform2fv(
        gl.getUniformLocation(state.program, 'vertBuffer'),
        subPoints
      );
      gl.uniform1fv(
        gl.getUniformLocation(state.program, 'bsVec'),
        bsArray
      );

      const projectionUniformLocation = gl.getUniformLocation(
        state.program,
        'gProjection'
      );
      const orthoMatrix = mat4.create();
      mat4.ortho(orthoMatrix, 0, 128, 0, 128, 1000, -1000);
      gl.uniformMatrix4fv(projectionUniformLocation, false, orthoMatrix);

      gl.enable(gl.DEPTH_TEST);
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
      gl.enable(gl.CULL_FACE);
      gl.cullFace(gl.BACK);
      gl.frontFace(gl.CW);
      gl.clearColor(0.5, 0.5, 0.5, 0);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, state.texture_bs);
      gl.uniform1i(
        gl.getUniformLocation(state.program, 'texture_bs'),
        0
      );

      gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, state.indexBuffer);
      gl.bindFramebuffer(gl.FRAMEBUFFER, null);

      gl.drawElements(
        gl.TRIANGLES,
        state.objData!.faces.length,
        gl.UNSIGNED_SHORT,
        0
      );

      const width = gl.drawingBufferWidth;
      const height = gl.drawingBufferHeight;
      gl.readPixels(
        0,
        0,
        width,
        height,
        gl.RGBA,
        gl.UNSIGNED_BYTE,
        state.pixels_fbo
      );
    },
    [canvasGlRef]
  );

  return { glStateRef, initWebGL, initGL, loadCharacter, renderImage };
}
