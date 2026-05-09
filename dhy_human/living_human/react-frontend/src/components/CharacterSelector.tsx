import { useState } from 'react';
import type { CharacterConfig } from '../types/character';

interface CharacterSelectorProps {
  characters: CharacterConfig[];
  currentCharId: string;
  switching: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => Promise<boolean>;
}

export function CharacterSelector({
  characters,
  currentCharId,
  switching,
  onSelect,
  onDelete,
}: CharacterSelectorProps) {
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  if (characters.length <= 1) return null;

  const handleDelete = async (charId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirmDeleteId === charId) {
      await onDelete(charId);
      setConfirmDeleteId(null);
    } else {
      setConfirmDeleteId(charId);
      setTimeout(() => setConfirmDeleteId(null), 3000);
    }
  };

  return (
    <div className="character-selector">
      {characters.map((char) => (
        <div key={char.id} className="character-item">
          {char.id !== 'default' && (
            <button
              className={`character-delete${confirmDeleteId === char.id ? ' confirm' : ''}`}
              onClick={(e) => handleDelete(char.id, e)}
              disabled={switching || char.id === currentCharId}
              title={confirmDeleteId === char.id ? '再次点击确认删除' : '删除角色'}
            >
              {confirmDeleteId === char.id ? '✕' : '×'}
            </button>
          )}
          <button
            className={`character-thumb${char.id === currentCharId ? ' active' : ''}`}
            disabled={switching || char.id === currentCharId}
            onClick={() => onSelect(char.id)}
            title={char.name}
          >
            <img src={char.preview} alt={char.name} />
            <span>{char.name}</span>
          </button>
        </div>
      ))}
    </div>
  );
}
