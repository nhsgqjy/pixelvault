import type {Dispatch, SetStateAction} from 'react';
import {api} from '../lib/api';
import type {Album, DeleteIntent, Photo} from '../types';

type Options = {
  checked: string[];
  setChecked: Dispatch<SetStateAction<string[]>>;
  activeAlbum: Album | null;
  setActiveAlbum: Dispatch<SetStateAction<Album | null>>;
  setConfirming: Dispatch<SetStateAction<DeleteIntent | null>>;
  setNotice: Dispatch<SetStateAction<string>>;
  setPhotos: Dispatch<SetStateAction<Photo[]>>;
  load: () => Promise<void>;
  loadAlbums: () => Promise<void>;
};

export function useVaultActions(options: Options) {
  const {checked, setChecked, activeAlbum, setActiveAlbum, setConfirming, setNotice, setPhotos, load, loadAlbums} = options;

  async function performAction(id: string, kind: DeleteIntent['kind'] | 'favorite' | 'restore' | 'share' | 'unshare') {
    let suffix = '';
    if (kind === 'share') {
      const raw = prompt('Share link duration in days', '7');
      if (raw === null) return;
      suffix = `?expires_hours=${Math.min(365, Math.max(1, Number(raw) || 7)) * 24}`;
    }
    const path = (kind === 'unshare' ? `/photos/${id}/share` : `/photos/${id}${kind === 'delete' ? '' : `/${kind}`}`) + suffix;
    const method = kind === 'share' ? 'POST' : kind === 'unshare' || kind === 'delete' ? 'DELETE' : 'PATCH';
    const result = await api.raw(path, {method}).then(response => response.json());
    if (kind === 'share') {
      await navigator.clipboard?.writeText(`${location.origin}${result.url}`);
      setNotice('Expiring share link copied');
    }
    await load();
  }

  async function action(id: string, kind: DeleteIntent['kind'] | 'favorite' | 'restore' | 'share' | 'unshare') {
    if (kind === 'trash' || kind === 'delete') {setConfirming({id, kind}); return;}
    await performAction(id, kind);
  }

  async function batch(actionName: string, albumId?: string, capturedAt?: string | null) {
    await api.patch('/photos/batch', {json: {photo_ids: checked, action: actionName, album_id: albumId, captured_at: capturedAt}});
    setNotice(`${checked.length} photos updated`); setChecked([]); await load(); await loadAlbums();
  }
  async function batchCaptureDate() {const value = prompt('Set capture time (YYYY-MM-DD HH:MM). Leave blank to clear.', '2026-01-01 12:00'); if (value !== null) await batch('set_captured_at', undefined, value.trim() ? value.trim().replace(' ', 'T') : null);}
  async function createNewAlbum() {const name = prompt('Name your new album'); if (!name) return; const response = await api.raw('/albums', {method: 'POST', json: {name}}); if (response.ok) {setNotice('Album created'); await loadAlbums();}}
  async function renameCurrent(album: Album) {const name = prompt('Rename album', album.name)?.trim(); if (!name || name === album.name) return; const response = await api.raw(`/albums/${album.id}`, {method: 'PATCH', json: {name}}); if (response.ok) {const updated = await response.json(); setActiveAlbum(current => current?.id === album.id ? {...current, name: updated.name} : current); setNotice('Album renamed'); await loadAlbums();} else setNotice('That album name is already in use');}
  async function editAlbumDescription(album: Album) {const description = prompt('Album description', album.description || ''); if (description === null) return; const updated = await api.patch<Partial<Album>>(`/albums/${album.id}/presentation`, {json: {description, cover_photo_id: album.cover_photo_id || null}}); setActiveAlbum(current => current?.id === album.id ? {...current, ...updated} : current); setNotice('Album description saved'); await loadAlbums();}
  async function setAlbumCover(photoId: string) {if (!activeAlbum) return; const updated = await api.patch<Partial<Album>>(`/albums/${activeAlbum.id}/presentation`, {json: {description: activeAlbum.description || '', cover_photo_id: photoId}}); setActiveAlbum(current => current ? {...current, ...updated} : current); setNotice('Album cover updated'); await loadAlbums();}
  async function removeFromCurrentAlbum(photoId: string) {if (!activeAlbum) return; const response = await api.raw(`/albums/${activeAlbum.id}/photos/${photoId}`, {method: 'DELETE'}); if (!response.ok) {setNotice('Photo could not be removed from this album'); return;} setNotice('Removed from album · original kept in library'); setActiveAlbum(current => current ? {...current, photo_count: Math.max(0, current.photo_count - 1)} : current); await load(); await loadAlbums();}
  async function retryProcessing(photoId: string) {const response = await api.raw(`/photos/${photoId}/processing/retry`, {method: 'POST'}); if (!response.ok) {setNotice('Photo processing could not be restarted'); return;} setPhotos(items => items.map(item => item.id === photoId ? {...item, processing_status: 'queued'} : item)); setNotice('Photo processing restarted');}
  async function deleteCurrent(album: Album) {if (!confirm(`Delete album “${album.name}”? Photos will stay in your library.`)) return; const response = await api.raw(`/albums/${album.id}`, {method: 'DELETE'}); if (response.ok) {setActiveAlbum(null); setNotice('Album deleted'); await loadAlbums();}}
  async function saveDownload(response: Response, filename: string) {if (!response.ok) {setNotice('Export could not be created'); return;} const url = URL.createObjectURL(await response.blob()); const link = document.createElement('a'); link.href = url; link.download = filename; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);}
  async function exportSelection() {await saveDownload(await api.raw('/photos/export', {method: 'POST', json: {photo_ids: checked}}), 'pixelvault-selection.zip'); setNotice(`${checked.length} originals exported`);}
  async function exportAlbum(album: Album) {await saveDownload(await api.raw(`/albums/${album.id}/export`), `${album.name}.zip`); setNotice('Album export ready');}
  async function shareAlbum(album: Album) {if (album.share_token) {await navigator.clipboard?.writeText(`${location.origin}/album-share/${album.share_token}`); setNotice(`Album link copied · ${album.share_views || 0} visits`); return;} const raw = prompt('Share album for how many days?', '7'); if (raw === null) return; const days = Math.min(365, Math.max(1, Number(raw) || 7)); const result = await api.post<{token:string;expires_at:string;url:string}>(`/albums/${album.id}/share`, {query: {expires_hours: days * 24}}); setActiveAlbum(current => current?.id === album.id ? {...current, share_token: result.token, share_expires_at: result.expires_at, share_views: 0} : current); await navigator.clipboard?.writeText(`${location.origin}${result.url}`); setNotice('Expiring album link copied'); await loadAlbums();}
  async function revokeAlbumShare(album: Album) {if (!confirm('Revoke this public album link?')) return; await api.delete(`/albums/${album.id}/share`); setActiveAlbum(current => current?.id === album.id ? {...current, share_token: null, share_expires_at: null} : current); setNotice('Album link revoked'); await loadAlbums();}

  return {performAction, action, batch, batchCaptureDate, createNewAlbum, renameCurrent, editAlbumDescription, setAlbumCover, removeFromCurrentAlbum, retryProcessing, deleteCurrent, exportSelection, exportAlbum, shareAlbum, revokeAlbumShare};
}
