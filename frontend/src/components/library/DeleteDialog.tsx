import {Trash2} from 'lucide-react';
import type {DeleteIntent} from '../../types';

export function DeleteDialog({intent, onCancel, onConfirm}: {intent: DeleteIntent; onCancel: () => void; onConfirm: () => void}) {
  const permanent = intent.kind === 'delete';
  return <div className="confirm-backdrop" onMouseDown={onCancel}><section role="alertdialog" aria-modal="true" aria-labelledby="delete-dialog-title" onMouseDown={event => event.stopPropagation()}><div className="confirm-icon"><Trash2/></div><p>{permanent ? 'PERMANENT ACTION' : 'AFFECTS ALL ALBUMS'}</p><h2 id="delete-dialog-title">{permanent ? 'Permanently delete original?' : 'Delete photo from library?'}</h2><span>{permanent ? 'The original file and every album reference will be removed. This cannot be recovered.' : 'This photo will disappear from this album and every other album. You can restore it later from Trash.'}</span><div><button onClick={onCancel}>Cancel</button><button className="confirm-danger" autoFocus onClick={onConfirm}>{permanent ? 'Delete permanently' : 'Move to Trash'}</button></div></section></div>;
}
