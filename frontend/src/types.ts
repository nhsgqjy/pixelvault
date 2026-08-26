export type Photo = {
  id: string;
  name: string;
  size: number;
  favorite: boolean;
  trashed?: boolean;
  share_token?: string | null;
  share_expires_at?: string | null;
  share_views?: number;
  width?: number;
  height?: number;
  captured_at?: string;
  caption?: string | null;
  tags?: string[];
  processing_status?: 'queued' | 'running' | 'ready' | 'failed';
};

export type Album = {
  id: string;
  name: string;
  description?: string | null;
  photo_count: number;
  cover_photo_id?: string | null;
  share_token?: string | null;
  share_expires_at?: string | null;
  share_views?: number;
};

export type TimelineGroup = {month: string; photo_count: number; cover_photo_id: string};
export type Stats = {photos: number; albums: number; original_bytes: number; thumbnail_bytes: number; bandwidth_saved_percent: number; request_count: number; average_ms: number; error_count: number};
export type Security = {active_sessions: number; recent_failed_logins: number; session_ttl_hours: number; failure_limit: number; failure_window_minutes: number; cookie_http_only: boolean; same_site: string; network_scope: string};
export type ApiEvent = {method: string; path: string; status: number; duration_ms: number; created_at: string};
export type View = 'photos' | 'favorites' | 'shared' | 'trash' | 'albums' | 'timeline' | 'duplicates' | 'insights';
export type IntegrityIssue = {photo_id: string | null; name: string; kind: 'missing_original' | 'hash_mismatch' | 'missing_thumbnail' | 'orphan_object'};
export type IntegrityReport = {status: 'healthy' | 'degraded'; checked_photos: number; verified_hashes: number; missing_thumbnails: number; orphan_objects: number; blocking_issues: number; issues: IntegrityIssue[]; scanned_at: string; duration_ms: number};
export type IntegrityJob = {id?: string; status: 'idle' | 'queued' | 'running' | 'completed' | 'failed'; total?: number; completed?: number; current_name?: string | null; result?: IntegrityReport | null; error?: string | null; reused?: boolean};
export type DuplicateGroup = {id: string; similarity_percent: number; potential_savings: number; photos: Photo[]};
export type DuplicateReport = {scanned_photos: number; group_count: number; potential_savings: number; groups: DuplicateGroup[]; policy: string};
export type DeleteIntent = {id: string; kind: 'trash' | 'delete'};
