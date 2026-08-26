import {ChevronLeft, ChevronRight, Pause, Play} from 'lucide-react';
import {API} from '../../lib/api';
import {bytes} from '../../lib/format';
import type {Photo} from '../../types';
import {MetadataEditor} from '../MetadataEditor';

type Props = {photo: Photo; photoCount: number; playing: boolean; onClose: () => void; onMove: (step: number) => void; onTogglePlay: () => void; onSaved: (photo: Photo) => void};

export function PhotoDetail({photo, photoCount, playing, onClose, onMove, onTogglePlay, onSaved}: Props) {
  return <div className="detail" onClick={onClose}><button aria-label="Close">×</button>{photoCount > 1 && <><button className="slide-nav prev" aria-label="Previous photo" onClick={event => {event.stopPropagation(); onMove(-1);}}><ChevronLeft/></button><button className="slide-nav next" aria-label="Next photo" onClick={event => {event.stopPropagation(); onMove(1);}}><ChevronRight/></button></>}<div onClick={event => event.stopPropagation()}><img src={`${API}/photos/${photo.id}/content`}/><section><p>PHOTO DETAILS</p><h2>{photo.name}</h2><button className="slideshow" onClick={onTogglePlay}>{playing ? <><Pause/>Pause slideshow</> : <><Play/>Start slideshow</>}</button><dl><dt>Dimensions</dt><dd>{photo.width && photo.height ? `${photo.width} x ${photo.height}` : 'Reading metadata...'}</dd><dt>File size</dt><dd>{bytes(photo.size)}</dd>{photo.captured_at && <><dt>Captured</dt><dd>{photo.captured_at}</dd></>}</dl>{photo.tags && photo.tags.length > 0 && <div className="tag-list">{photo.tags.map(tag => <span key={tag}>#{tag}</span>)}</div>}<MetadataEditor photo={photo} onSaved={onSaved}/></section></div></div>;
}
