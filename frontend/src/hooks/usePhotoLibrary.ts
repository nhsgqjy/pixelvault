import {useCallback, useEffect, useMemo, useState} from 'react';
import {API} from '../lib/api';
import type {Photo, View} from '../types';

export type LibraryFilters = {
  dateFrom: string;
  dateTo: string;
  minSize: string;
  orientation: string;
  sort: string;
};

type Options = LibraryFilters & {
  enabled: boolean;
  view: View;
  search: string;
  albumId?: string;
  month?: string;
};

export function usePhotoLibrary(options: Options) {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [total, setTotal] = useState(0);
  const query = useMemo(() => ({...options}), [options.enabled, options.view, options.search, options.albumId,
    options.month, options.dateFrom, options.dateTo, options.minSize, options.orientation, options.sort]);

  const photoUrl = useCallback((cursor = '') => `${API}/photos?limit=24&cursor=${encodeURIComponent(cursor)}` +
    `&view=${query.view === 'albums' || query.view === 'timeline' ? 'photos' : query.view}` +
    `&search=${encodeURIComponent(query.search)}` +
    `${query.albumId ? `&album_id=${query.albumId}` : ''}${query.month ? `&month=${query.month}` : ''}` +
    `&date_from=${query.dateFrom}&date_to=${query.dateTo}&min_size_mb=${encodeURIComponent(query.minSize || '0')}` +
    `&orientation=${query.orientation}&sort=${query.sort}`, [query]);

  const load = useCallback(async () => {
    if (!query.enabled) {
      setPhotos([]); setNextCursor(null); setTotal(0); return;
    }
    const response = await fetch(photoUrl());
    if (!response.ok) return;
    const payload = await response.json();
    setPhotos(payload.items); setNextCursor(payload.next_cursor); setTotal(payload.total);
  }, [query.enabled, photoUrl]);

  const loadMore = useCallback(async () => {
    if (nextCursor === null) return;
    const response = await fetch(photoUrl(nextCursor));
    if (!response.ok) return;
    const payload = await response.json();
    setPhotos(current => [...current, ...payload.items]);
    setNextCursor(payload.next_cursor); setTotal(payload.total);
  }, [nextCursor, photoUrl]);

  useEffect(() => {
    const timer = setTimeout(() => { void load(); }, 150);
    return () => clearTimeout(timer);
  }, [load]);

  const processingActive = photos.some(photo => photo.processing_status === 'queued' || photo.processing_status === 'running');
  useEffect(() => {
    if (!processingActive || !query.enabled) return;
    const timer = setInterval(() => { void load(); }, 900);
    return () => clearInterval(timer);
  }, [processingActive, query.enabled, load]);

  return {photos, setPhotos, nextCursor, total, load, loadMore};
}
