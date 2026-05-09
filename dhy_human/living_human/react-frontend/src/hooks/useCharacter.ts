import { useState, useEffect, useCallback } from 'react';
import type { CharacterConfig } from '../types/character';

const API_BASE = 'http://localhost:8000';

export function useCharacter() {
  const [characters, setCharacters] = useState<CharacterConfig[]>([]);
  const [currentCharId, setCurrentCharId] = useState<string>('default');
  const [loaded, setLoaded] = useState(false);

  const fetchCharacters = useCallback(() => {
    return fetch('characters/index.json')
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load characters/index.json');
        return res.json();
      })
      .then((data: CharacterConfig[]) => {
        setCharacters(data);
        setCurrentCharId((prev) => {
          if (data.length > 0 && !data.find((c) => c.id === prev)) {
            return data[0].id;
          }
          return prev;
        });
        setLoaded(true);
        return data;
      })
      .catch((err) => {
        console.error('Failed to load character list:', err);
        setLoaded(true);
        return [] as CharacterConfig[];
      });
  }, []);

  useEffect(() => {
    fetchCharacters();

    const interval = setInterval(() => {
      fetchCharacters();
    }, 10_000);

    return () => clearInterval(interval);
  }, [fetchCharacters]);

  const deleteCharacter = useCallback(
    async (charId: string): Promise<boolean> => {
      try {
        const res = await fetch(`${API_BASE}/api/characters/${encodeURIComponent(charId)}`, {
          method: 'DELETE',
        });
        if (!res.ok) {
          const data = await res.json();
          console.error('Delete failed:', data.detail);
          return false;
        }
        // Immediately refresh the character list
        await fetchCharacters();
        return true;
      } catch (err) {
        console.error('Delete failed:', err);
        return false;
      }
    },
    [fetchCharacters]
  );

  return { characters, currentCharId, setCurrentCharId, loaded, refresh: fetchCharacters, deleteCharacter };
}
