import {useCallback, useEffect, useState} from 'react';
import {api} from '../lib/api';
import type {Album} from '../types';

export function useAlbums() {
  const [albums, setAlbums] = useState<Album[]>([]);
  const loadAlbums = useCallback(async () => {
    const response = await api.raw('/albums');
    if (!response.ok) return;
    const payload = await response.json();
    setAlbums(payload.items);
  }, []);
  useEffect(() => { void loadAlbums(); }, [loadAlbums]);
  return {albums, setAlbums, loadAlbums};
}
