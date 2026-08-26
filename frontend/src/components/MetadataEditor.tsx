import {useState} from 'react';
import {API} from '../lib/api';
import type {Photo} from '../types';

export function MetadataEditor({photo, onSaved}: {photo: Photo; onSaved: (photo: Photo) => void}) {
  const [caption, setCaption] = useState(photo.caption || '');
  const [tags, setTags] = useState((photo.tags || []).join(', '));
  const [capturedAt, setCapturedAt] = useState((photo.captured_at || '')
    .replace(/^(\d{4}):(\d{2}):(\d{2}) /, '$1-$2-$3T').slice(0, 16));
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      const updated = await fetch(`${API}/photos/${photo.id}/metadata`, {
        method: 'PATCH',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
          caption,
          tags: tags.split(',').map(tag => tag.trim()).filter(Boolean),
          captured_at: capturedAt || null,
        }),
      }).then(response => response.json());
      onSaved(updated);
    } finally {
      setSaving(false);
    }
  }

  return <div className="metadata-editor">
    <label>Description<textarea value={caption} onChange={event => setCaption(event.target.value)} placeholder="What is happening in this photo?" maxLength={500}/></label>
    <label>Tags<input value={tags} onChange={event => setTags(event.target.value)} placeholder="travel, family, pets"/></label>
    <label>Capture time<input type="datetime-local" value={capturedAt} onChange={event => setCapturedAt(event.target.value)}/><small>Clear this field to place the photo under Unknown date.</small></label>
    <button onClick={save} disabled={saving}>{saving ? 'Saving…' : 'Save details'}</button>
  </div>;
}
