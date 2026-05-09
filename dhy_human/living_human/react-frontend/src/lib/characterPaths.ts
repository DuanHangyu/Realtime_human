import type { CharacterConfig } from '../types/character';

export interface CharacterAssets {
  videoUrl: string;
  dataUrl: string;
}

export function getCharacterAssets(characterId: string): CharacterAssets {
  return {
    videoUrl: `characters/${characterId}/01.mp4`,
    dataUrl: `characters/${characterId}/data`,
  };
}

export function getPreviewUrl(character: CharacterConfig): string {
  return character.preview;
}
