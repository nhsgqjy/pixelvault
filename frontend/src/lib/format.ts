export const bytes = (value: number) => value > 1048576
  ? `${(value / 1048576).toFixed(1)} MB`
  : `${Math.round(value / 1024)} KB`;

export async function sha256(file: File) {
  const buffer = await file.arrayBuffer();
  const hash = await crypto.subtle.digest('SHA-256', buffer);
  return [...new Uint8Array(hash)].map(value => value.toString(16).padStart(2, '0')).join('');
}
