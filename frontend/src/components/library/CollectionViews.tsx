import {FolderOpen, Pencil} from 'lucide-react';
import {API} from '../../lib/api';
import type {Album, TimelineGroup} from '../../types';

export function TimelineGrid({groups, monthLabel, onOpen}: {groups: TimelineGroup[]; monthLabel: (month: string) => string; onOpen: (month: string) => void}) {
  return <section className="timeline-grid">{groups.map(group => <button key={group.month} onClick={() => onOpen(group.month)}><img src={`${API}/photos/${group.cover_photo_id}/thumbnail`} alt=""/><span><b>{monthLabel(group.month)}</b><small>{group.photo_count} photos</small></span></button>)}{!groups.length && <div className="empty">Upload photos with capture dates to build your timeline.</div>}</section>;
}

export function AlbumGrid({albums, onOpen, onRename}: {albums: Album[]; onOpen: (album: Album) => void; onRename: (album: Album) => void}) {
  return <section className="album-grid">{albums.map(album => <article key={album.id} role="button" tabIndex={0} aria-label={`Open ${album.name}`} onClick={() => onOpen(album)} onKeyDown={event => {if (event.key === 'Enter') onOpen(album);}}>{album.cover_photo_id ? <img src={`${API}/photos/${album.cover_photo_id}/thumbnail`} alt=""/> : <div className="album-placeholder"><FolderOpen/></div>}<span><b>{album.name}</b><small>{album.photo_count} photos</small></span><button aria-label={`Rename ${album.name}`} onClick={event => {event.stopPropagation(); onRename(album);}}><Pencil/></button></article>)}{!albums.length && <div className="empty">Create your first album to organize memories.</div>}</section>;
}
