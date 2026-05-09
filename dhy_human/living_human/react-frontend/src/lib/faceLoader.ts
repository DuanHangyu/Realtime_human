// OBJ file parser for 3D face mesh data

export interface FaceData {
  vertices: number[];
  faces: number[];
}

export function loadFaceFile(text: string): FaceData {
  const vertices: number[] = [];
  const faces: number[] = [];
  const lines = text.split('\n');

  lines.forEach(line => {
    const parts = line.trim().split(/\s+/);
    if (parts[0] === 'v') {
      vertices.push(
        parseFloat(parts[1]), parseFloat(parts[2]), parseFloat(parts[3]),
        parseFloat(parts[4]), parseFloat(parts[5])
      );
    } else if (parts[0] === 'f') {
      const face = parts.slice(1).map(part => {
        const indices = part.split('/').map(index => parseInt(index, 10) - 1);
        return indices[0];
      });
      faces.push(...face);
    }
  });

  return { vertices, faces };
}
