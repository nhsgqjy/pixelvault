import {Pause, Play} from 'lucide-react';
import type {UploadStatus} from '../hooks/useChunkedUpload';

type Props = {
  progress: Record<string, number>;
  uploadState: Record<string, UploadStatus>;
  speeds: Record<string, string>;
  uploadErrors: Record<string, string>;
  onToggle: (name: string) => void;
};

export function UploadQueue({progress, uploadState, speeds, uploadErrors, onToggle}: Props) {
  if (!Object.keys(progress).length) return null;
  return <section className="queue">{Object.entries(progress).map(([name, value]) => <div key={name}>
    <span><b>{name}</b><small>{uploadState[name]} {speeds[name] && `· ${speeds[name]}`}</small>{uploadErrors[name] && <small className="upload-error">{uploadErrors[name]}</small>}</span>
    <progress value={value} max="100"/><b>{value}%</b>
    {value < 100 && uploadState[name] !== 'failed' && <button aria-label={`${uploadState[name] === 'paused' ? 'Resume' : 'Pause'} ${name}`} onClick={() => onToggle(name)}>{uploadState[name] === 'paused' ? <Play/> : <Pause/>}</button>}
  </div>)}</section>;
}
