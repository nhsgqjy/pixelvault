import {Check, Heart, Share2, Sparkles, Trash2, X} from 'lucide-react';
import {API} from '../../lib/api';
import {bytes} from '../../lib/format';
import type {Photo, View} from '../../types';

type Action = 'favorite' | 'trash' | 'restore' | 'share' | 'unshare' | 'delete';
type Props = {
  photos: Photo[]; checked: string[]; view: View; inAlbum: boolean;
  onOpen: (photo: Photo) => void; onToggle: (id: string) => void;
  onAction: (id: string, action: Action) => void; onRemoveFromAlbum: (id: string) => void;
  onRetryProcessing: (id: string) => void;
};

export function PhotoGallery({photos, checked, view, inAlbum, onOpen, onToggle, onAction, onRemoveFromAlbum, onRetryProcessing}: Props) {
  return <section className="gallery">{photos.map(photo => <article key={photo.id} className={checked.includes(photo.id) ? 'checked' : ''}>
    <div className="photo">{photo.processing_status === 'failed' ? <div className="processing-placeholder failed"><X/><b>Processing failed</b><small>The original is safe in your vault.</small><button onClick={() => onRetryProcessing(photo.id)}>Try again</button></div>
      : photo.processing_status === 'queued' || photo.processing_status === 'running' ? <div className="processing-placeholder"><Sparkles/><b>{photo.processing_status === 'queued' ? 'Waiting to process' : 'Creating preview'}</b><small>Extracting dimensions and photo metadata…</small></div>
      : <img src={`${API}/photos/${photo.id}/thumbnail`} alt={photo.caption || photo.name} role="button" tabIndex={0} onClick={() => onOpen(photo)} onKeyDown={event => {if (event.key === 'Enter') onOpen(photo);}}/>}
      <button className="picker" aria-label={`Select ${photo.name}`} onClick={() => onToggle(photo.id)}>{checked.includes(photo.id) ? <Check/> : null}</button>
      <div className="actions">{view === 'trash' ? <><button onClick={() => onAction(photo.id, 'restore')}>Restore</button><button onClick={() => onAction(photo.id, 'delete')}>Delete</button></>
        : view === 'shared' ? <button onClick={() => onAction(photo.id, 'unshare')}>Revoke</button>
        : <><button aria-label={`${photo.favorite ? 'Remove from' : 'Add to'} favorites`} className={photo.favorite ? 'selected' : ''} onClick={() => onAction(photo.id, 'favorite')}><Heart/></button>
          {!inAlbum && <button aria-label={`Share ${photo.name}`} onClick={() => onAction(photo.id, 'share')}><Share2/></button>}
          {inAlbum ? <><button className="remove-album" title="Remove from this album" aria-label={`Remove ${photo.name} from this album`} onClick={() => onRemoveFromAlbum(photo.id)}><X/></button><button className="delete-global" title="Delete from library" aria-label={`Delete ${photo.name} from the library`} onClick={() => onAction(photo.id, 'trash')}><Trash2/></button></>
            : <button aria-label={`Move ${photo.name} to global trash`} onClick={() => onAction(photo.id, 'trash')}><Trash2/></button>}</>}
      </div>
    </div><div className="meta"><b>{photo.name}</b>{view === 'shared' ? <small>{photo.share_views || 0} views · {photo.share_expires_at ? `${Math.max(0, Math.ceil((new Date(photo.share_expires_at).getTime() - Date.now()) / 86400000))}d left` : 'no expiry'}</small> : <small>{bytes(photo.size)}</small>}</div>
  </article>)}{!photos.length && <div className="empty">No photos here yet.</div>}</section>;
}
