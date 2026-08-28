import {useRef, useState} from 'react';
import {api} from '../lib/api';
import {sha256} from '../lib/format';

export type UploadStatus = 'uploading' | 'paused' | 'retrying' | 'complete' | 'deduplicated' | 'failed';

export function useChunkedUpload(onComplete: () => void | Promise<void>) {
  const [progress, setProgress] = useState<Record<string, number>>({});
  const [uploadState, setUploadState] = useState<Record<string, UploadStatus>>({});
  const [speeds, setSpeeds] = useState<Record<string, string>>({});
  const [uploadErrors, setUploadErrors] = useState<Record<string, string>>({});
  const paused = useRef<Record<string, boolean>>({});

  async function upload(file: File) {
    const started = Date.now();
    const hash = await sha256(file);
    paused.current[file.name] = false;
    setProgress(current => ({...current, [file.name]: 2}));
    setUploadState(current => ({...current, [file.name]: 'uploading'}));
    setUploadErrors(current => ({...current, [file.name]: ''}));
    try {
      const init = await api.post<{instant: boolean; upload_id: string; chunk_size: number; uploaded_chunks?: number[]}>('/uploads/init', {query: {filename: file.name, sha256: hash, size: file.size, content_type: file.type}});
      if (init.instant) {
        setProgress(current => ({...current, [file.name]: 100}));
        setUploadState(current => ({...current, [file.name]: 'deduplicated'}));
        await onComplete();
        return;
      }
      const chunkSize = init.chunk_size;
      const total = Math.ceil(file.size / chunkSize);
      const completedChunks = new Set<number>(init.uploaded_chunks || []);
      const missing = Array.from({length: total}, (_, index) => index).filter(index => !completedChunks.has(index));
      let cursor = 0;
      let completed = completedChunks.size;
      let uploadedBytes = Math.min(file.size, completedChunks.size * chunkSize);
      setProgress(current => ({...current, [file.name]: Math.round(completedChunks.size / total * 92)}));

      const worker = async () => {
        while (cursor < missing.length) {
          while (paused.current[file.name]) await new Promise(resolve => setTimeout(resolve, 120));
          const index = missing[cursor++];
          const form = new FormData();
          form.append('chunk', file.slice(index * chunkSize, Math.min((index + 1) * chunkSize, file.size)));
          for (let attempt = 1; attempt <= 3; attempt++) {
            try {
              await api.put(`/uploads/${init.upload_id}/chunks/${index}`, {body: form});
              break;
            } catch (error) {
              if (attempt === 3) throw error;
              setUploadState(current => ({...current, [file.name]: 'retrying'}));
              await new Promise(resolve => setTimeout(resolve, attempt * 400));
            }
          }
          completed++;
          uploadedBytes += Math.min(chunkSize, file.size - index * chunkSize);
          setProgress(current => ({...current, [file.name]: Math.round(completed / total * 92)}));
          setSpeeds(current => ({...current, [file.name]: `${(uploadedBytes / 1048576 / Math.max((Date.now() - started) / 1000, .1)).toFixed(1)} MB/s`}));
          setUploadState(current => ({...current, [file.name]: 'uploading'}));
        }
      };
      await Promise.all([worker(), worker(), worker()]);
      const form = new FormData();
      form.append('filename', file.name);
      form.append('sha256', hash);
      form.append('content_type', file.type || 'application/octet-stream');
      await api.post(`/uploads/${init.upload_id}/complete`, {body: form});
      setProgress(current => ({...current, [file.name]: 100}));
      setUploadState(current => ({...current, [file.name]: 'complete'}));
      await onComplete();
    } catch (error) {
      setUploadState(current => ({...current, [file.name]: 'failed'}));
      setUploadErrors(current => ({
        ...current,
        [file.name]: error instanceof Error ? error.message : 'Upload failed',
      }));
    }
  }

  function toggleUpload(name: string) {
    paused.current[name] = !paused.current[name];
    setUploadState(current => ({...current, [name]: paused.current[name] ? 'paused' : 'uploading'}));
  }

  function accept(files: FileList | null) {
    if (!files) return;
    [...files].filter(file => file.type.startsWith('image/')).forEach(file => void upload(file));
  }

  return {progress, uploadState, speeds, uploadErrors, accept, toggleUpload};
}
