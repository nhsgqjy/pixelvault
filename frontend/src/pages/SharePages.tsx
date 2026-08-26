import {useEffect, useState} from 'react';
import {Sparkles} from 'lucide-react';
import {API} from '../lib/api';
import type {Photo} from '../types';

export function SharePage({token}: {token: string}) {
  const [photo, setPhoto] = useState<Photo | null>(null);
  useEffect(() => {
    fetch(`${API}/share/${token}`).then(response => response.ok ? response.json() : Promise.reject())
      .then(setPhoto).catch(() => setPhoto(null));
  }, [token]);
  return <main className="share-page"><div className="brand dark"><Sparkles/>PixelVault</div>{photo ? <>
    <p>SHARED MEMORY</p><h1>{photo.name}</h1><img src={`${API}/share/${token}/content`}/>
    <small>Private link · expires {photo.share_expires_at ? new Date(photo.share_expires_at).toLocaleString() : 'on revocation'}</small>
  </> : <div className="empty">This share link is unavailable or has expired.</div>}</main>;
}

type SharedAlbum = {name: string; description: string; photo_count: number; expires_at: string; views: number; photos: Photo[]};

export function AlbumSharePage({token}: {token: string}) {
  const [album, setAlbum] = useState<SharedAlbum | null>(null);
  const [failed, setFailed] = useState(false);
  const [selected, setSelected] = useState<Photo | null>(null);
  useEffect(() => {
    fetch(`${API}/share/albums/${token}`).then(response => response.ok ? response.json() : Promise.reject())
      .then(setAlbum).catch(() => setFailed(true));
  }, [token]);
  if (failed) return <main className="shared-album-page"><div className="brand dark"><Sparkles/>PixelVault</div><div className="empty">This album link is unavailable or has expired.</div></main>;
  return <main className="shared-album-page"><header><div className="brand dark"><Sparkles/>PixelVault</div>{album && <small>{album.views} visits · expires {new Date(album.expires_at).toLocaleDateString()}</small>}</header>{album ? <>
    <section className="shared-album-hero"><p>SHARED COLLECTION</p><h1>{album.name}</h1>{album.description && <em>{album.description}</em>}<span>{album.photo_count} memories, shared privately with one expiring link.</span></section>
    <section className="shared-album-grid">{album.photos.map(photo => <button key={photo.id} onClick={() => setSelected(photo)}><img src={`${API}/share/albums/${token}/photos/${photo.id}/thumbnail`} alt={photo.caption || photo.name}/><span>{photo.caption || photo.name}</span></button>)}</section>
    {selected && <div className="shared-lightbox" onClick={() => setSelected(null)}><button aria-label="Close">×</button><img onClick={event => event.stopPropagation()} src={`${API}/share/albums/${token}/photos/${selected.id}/content`} alt={selected.caption || selected.name}/></div>}
  </> : <div className="empty">Opening shared album…</div>}</main>;
}
