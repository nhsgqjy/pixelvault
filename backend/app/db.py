import json
from pathlib import Path

from .database import backend_name, connect, is_postgres


POSTGRES_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS photos (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, sha256 TEXT NOT NULL, object_name TEXT NOT NULL,
        content_type TEXT NOT NULL, size BIGINT NOT NULL, favorite INTEGER NOT NULL DEFAULT 0,
        trashed INTEGER NOT NULL DEFAULT 0, share_token TEXT, thumbnail_name TEXT, width INTEGER,
        height INTEGER, captured_at TEXT, share_expires_at TEXT, share_views INTEGER NOT NULL DEFAULT 0,
        caption TEXT, perceptual_hash TEXT, sort_id BIGSERIAL UNIQUE)""",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_photos_sha256 ON photos(sha256)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_photos_share_token ON photos(share_token) WHERE share_token IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_photos_state ON photos(trashed, favorite)",
    "CREATE INDEX IF NOT EXISTS idx_photos_captured_at ON photos(captured_at)",
    """CREATE TABLE IF NOT EXISTS albums (
        id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, share_token TEXT,
        share_expires_at TEXT, share_views INTEGER NOT NULL DEFAULT 0, description TEXT, cover_photo_id TEXT)""",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_albums_share_token ON albums(share_token) WHERE share_token IS NOT NULL",
    """CREATE TABLE IF NOT EXISTS album_photos (
        album_id TEXT NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
        photo_id TEXT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
        added_at TEXT NOT NULL, PRIMARY KEY (album_id, photo_id))""",
    "CREATE INDEX IF NOT EXISTS idx_album_photos_photo_id ON album_photos(photo_id)",
    """CREATE TABLE IF NOT EXISTS upload_sessions (
        id TEXT PRIMARY KEY, filename TEXT NOT NULL, sha256 TEXT NOT NULL UNIQUE, size BIGINT NOT NULL,
        content_type TEXT NOT NULL, created_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS auth_sessions (
        token TEXT PRIMARY KEY, created_at TEXT NOT NULL, expires_at TEXT NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires_at ON auth_sessions(expires_at)",
    """CREATE TABLE IF NOT EXISTS api_events (
        id BIGSERIAL PRIMARY KEY, method TEXT NOT NULL, path TEXT NOT NULL, status INTEGER NOT NULL,
        duration_ms DOUBLE PRECISION NOT NULL, created_at TEXT NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS idx_api_events_created_at ON api_events(created_at DESC)",
    "CREATE TABLE IF NOT EXISTS tags (id BIGSERIAL PRIMARY KEY, name TEXT NOT NULL)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_tags_name_lower ON tags(LOWER(name))",
    """CREATE TABLE IF NOT EXISTS photo_tags (
        photo_id TEXT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
        tag_id BIGINT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
        PRIMARY KEY (photo_id, tag_id))""",
    "CREATE INDEX IF NOT EXISTS idx_photo_tags_tag_id ON photo_tags(tag_id)",
    """CREATE TABLE IF NOT EXISTS login_attempts (
        id BIGSERIAL PRIMARY KEY, client_key TEXT NOT NULL, attempted_at TEXT NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS idx_login_attempts_client_time ON login_attempts(client_key, attempted_at)",
    """CREATE TABLE IF NOT EXISTS integrity_jobs (
        id TEXT PRIMARY KEY, status TEXT NOT NULL, total INTEGER NOT NULL DEFAULT 0,
        completed INTEGER NOT NULL DEFAULT 0, current_name TEXT, result_json TEXT, error TEXT,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS idx_integrity_jobs_status_created ON integrity_jobs(status, created_at DESC)",
    """CREATE TABLE IF NOT EXISTS photo_processing_jobs (
        photo_id TEXT PRIMARY KEY REFERENCES photos(id) ON DELETE CASCADE, status TEXT NOT NULL,
        error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS idx_photo_processing_status ON photo_processing_jobs(status, updated_at DESC)",
]


def initialize(data_dir: Path, legacy_index: Path):
    with connect(data_dir) as db:
        if is_postgres():
            for statement in POSTGRES_SCHEMA:
                db.execute(statement)
            db.execute("""UPDATE integrity_jobs SET status='failed', error='Server restarted before completion'
                WHERE status IN ('queued','running')""")
            db.execute("""UPDATE photo_processing_jobs SET status='failed', error='Server restarted before completion'
                WHERE status IN ('queued','running')""")
            count = db.execute("SELECT COUNT(*) AS count FROM photos").fetchone()["count"]
            if count == 0 and legacy_index.exists():
                for item in json.loads(legacy_index.read_text(encoding="utf-8")):
                    upsert(db, item)
            return
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=NORMAL")
        db.executescript("""
        CREATE TABLE IF NOT EXISTS photos (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            object_name TEXT NOT NULL,
            content_type TEXT NOT NULL,
            size INTEGER NOT NULL,
            favorite INTEGER NOT NULL DEFAULT 0,
            trashed INTEGER NOT NULL DEFAULT 0,
            share_token TEXT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_photos_sha256 ON photos(sha256);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_photos_share_token ON photos(share_token) WHERE share_token IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_photos_state ON photos(trashed, favorite);
        CREATE TABLE IF NOT EXISTS albums (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS album_photos (
            album_id TEXT NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
            photo_id TEXT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
            added_at TEXT NOT NULL,
            PRIMARY KEY (album_id, photo_id)
        );
        CREATE INDEX IF NOT EXISTS idx_album_photos_photo_id ON album_photos(photo_id);
        CREATE TABLE IF NOT EXISTS upload_sessions (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            sha256 TEXT NOT NULL UNIQUE,
            size INTEGER NOT NULL,
            content_type TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS auth_sessions (
            token TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires_at ON auth_sessions(expires_at);
        CREATE TABLE IF NOT EXISTS api_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            method TEXT NOT NULL,
            path TEXT NOT NULL,
            status INTEGER NOT NULL,
            duration_ms REAL NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_api_events_created_at ON api_events(created_at DESC);
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL COLLATE NOCASE UNIQUE
        );
        CREATE TABLE IF NOT EXISTS photo_tags (
            photo_id TEXT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,
            tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
            PRIMARY KEY (photo_id, tag_id)
        );
        CREATE INDEX IF NOT EXISTS idx_photo_tags_tag_id ON photo_tags(tag_id);
        CREATE TABLE IF NOT EXISTS login_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_key TEXT NOT NULL,
            attempted_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_login_attempts_client_time ON login_attempts(client_key, attempted_at);
        CREATE TABLE IF NOT EXISTS integrity_jobs (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            total INTEGER NOT NULL DEFAULT 0,
            completed INTEGER NOT NULL DEFAULT 0,
            current_name TEXT,
            result_json TEXT,
            error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_integrity_jobs_status_created
        ON integrity_jobs(status, created_at DESC);
        CREATE TABLE IF NOT EXISTS photo_processing_jobs (
            photo_id TEXT PRIMARY KEY REFERENCES photos(id) ON DELETE CASCADE,
            status TEXT NOT NULL,
            error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_photo_processing_status
        ON photo_processing_jobs(status, updated_at DESC);
        PRAGMA optimize;
        """)
        db.execute("""UPDATE integrity_jobs SET status='failed', error='Server restarted before completion'
            WHERE status IN ('queued','running')""")
        db.execute("""UPDATE photo_processing_jobs SET status='failed', error='Server restarted before completion'
            WHERE status IN ('queued','running')""")
        columns = {row[1] for row in db.execute("PRAGMA table_info(photos)")}
        for name, definition in {
            "thumbnail_name": "TEXT", "width": "INTEGER", "height": "INTEGER", "captured_at": "TEXT",
            "share_expires_at": "TEXT", "share_views": "INTEGER NOT NULL DEFAULT 0", "caption": "TEXT",
            "perceptual_hash": "TEXT"
        }.items():
            if name not in columns:
                db.execute(f"ALTER TABLE photos ADD COLUMN {name} {definition}")
        db.execute("CREATE INDEX IF NOT EXISTS idx_photos_captured_at ON photos(captured_at)")
        album_columns = {row[1] for row in db.execute("PRAGMA table_info(albums)")}
        for name, definition in {
            "share_token": "TEXT", "share_expires_at": "TEXT", "share_views": "INTEGER NOT NULL DEFAULT 0",
            "description": "TEXT", "cover_photo_id": "TEXT"
        }.items():
            if name not in album_columns:
                db.execute(f"ALTER TABLE albums ADD COLUMN {name} {definition}")
        db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_albums_share_token
            ON albums(share_token) WHERE share_token IS NOT NULL""")
        count = db.execute("SELECT COUNT(*) AS count FROM photos").fetchone()["count"]
        if count == 0 and legacy_index.exists():
            for item in json.loads(legacy_index.read_text(encoding="utf-8")):
                upsert(db, item)


def upsert(db, item):
    db.execute("""INSERT INTO photos(id,name,sha256,object_name,content_type,size,favorite,trashed,share_token,thumbnail_name,width,height,captured_at,share_expires_at,share_views,caption)
        VALUES(:id,:name,:sha256,:object_name,:content_type,:size,:favorite,:trashed,:share_token,:thumbnail_name,:width,:height,:captured_at,:share_expires_at,:share_views,:caption)
        ON CONFLICT(id) DO UPDATE SET name=excluded.name, favorite=excluded.favorite,
        trashed=excluded.trashed, share_token=excluded.share_token, thumbnail_name=excluded.thumbnail_name,
        width=excluded.width, height=excluded.height, captured_at=excluded.captured_at,
        share_expires_at=excluded.share_expires_at, share_views=excluded.share_views, caption=excluded.caption""", {
        **item,
        "favorite": int(item.get("favorite", False)),
        "trashed": int(item.get("trashed", False)),
        "share_token": item.get("share_token"),
        "thumbnail_name": item.get("thumbnail_name"), "width": item.get("width"),
        "height": item.get("height"), "captured_at": item.get("captured_at"),
        "share_expires_at": item.get("share_expires_at"), "share_views": item.get("share_views", 0),
        "caption": item.get("caption"),
    })


def all_photos(data_dir: Path):
    with connect(data_dir) as db:
        items = [dict(row) for row in db.execute("""SELECT p.*, GROUP_CONCAT(t.name, char(31)) AS tag_names
            FROM photos p LEFT JOIN photo_tags pt ON pt.photo_id=p.id LEFT JOIN tags t ON t.id=pt.tag_id
            GROUP BY p.id ORDER BY p.rowid DESC""")]
        for item in items:
            item["favorite"], item["trashed"] = bool(item["favorite"]), bool(item["trashed"])
            tag_names = item.pop("tag_names")
            item["tags"] = tag_names.split(chr(31)) if tag_names else []
        return items


def query_photos(data_dir: Path, limit: int, cursor: str, view: str, search: str,
                 album_id: str | None, month: str | None, date_from: str | None = None,
                 date_to: str | None = None, min_size: int = 0, orientation: str = "any",
                 sort: str = "newest"):
    conditions: list[str] = []
    params: list = []
    if view == "favorites":
        conditions.extend(["p.trashed=0", "p.favorite=1"])
    elif view == "trash":
        conditions.append("p.trashed=1")
    elif view == "shared":
        conditions.extend(["p.trashed=0", "p.share_token IS NOT NULL"])
    else:
        conditions.append("p.trashed=0")
    if album_id:
        conditions.append("EXISTS (SELECT 1 FROM album_photos ap WHERE ap.album_id=? AND ap.photo_id=p.id)")
        params.append(album_id)
    if month:
        if month == "unknown":
            conditions.append("(p.captured_at IS NULL OR p.captured_at='')")
        else:
            conditions.append("p.captured_at LIKE ?")
            params.append(month.replace("-", ":") + "%")
    if search:
        pattern = f"%{search.casefold()}%"
        conditions.append("""(LOWER(p.name) LIKE ? OR LOWER(COALESCE(p.caption,'')) LIKE ? OR EXISTS (
            SELECT 1 FROM photo_tags pt JOIN tags t ON t.id=pt.tag_id
            WHERE pt.photo_id=p.id AND LOWER(t.name) LIKE ?))""")
        params.extend([pattern, pattern, pattern])
    if date_from:
        conditions.append("p.captured_at >= ?")
        params.append(date_from.replace("-", ":") + " 00:00:00")
    if date_to:
        conditions.append("p.captured_at <= ?")
        params.append(date_to.replace("-", ":") + " 23:59:59")
    if min_size > 0:
        conditions.append("p.size >= ?")
        params.append(min_size)
    if orientation == "landscape":
        conditions.append("p.width > p.height")
    elif orientation == "portrait":
        conditions.append("p.height > p.width")
    elif orientation == "square":
        conditions.append("p.width = p.height")
    where = " AND ".join(conditions) if conditions else "1=1"
    with connect(data_dir) as db:
        total = db.execute(f"SELECT COUNT(*) AS count FROM photos p WHERE {where}", params).fetchone()["count"]
        page_conditions = list(conditions)
        page_params = list(params)
        sort_value = cursor_rowid = None
        if cursor:
            try:
                sort_value, cursor_rowid = cursor.rsplit("~", 1)
                cursor_rowid = int(cursor_rowid)
            except (ValueError, AttributeError):
                sort_value = cursor_rowid = None
        if cursor_rowid is not None:
            if sort == "size_desc":
                page_conditions.append("(p.size < ? OR (p.size = ? AND p.rowid < ?))")
                page_params.extend([int(sort_value), int(sort_value), cursor_rowid])
            elif sort in {"captured_desc", "captured_asc"}:
                comparison = "<" if sort == "captured_desc" else ">"
                page_conditions.append(f"(COALESCE(p.captured_at,'') {comparison} ? OR (COALESCE(p.captured_at,'') = ? AND p.rowid < ?))")
                page_params.extend([sort_value, sort_value, cursor_rowid])
            else:
                page_conditions.append("p.rowid < ?")
                page_params.append(cursor_rowid)
        page_where = " AND ".join(page_conditions) if page_conditions else "1=1"
        order_by = {"size_desc": "p.size DESC, p.rowid DESC",
                    "captured_desc": "COALESCE(p.captured_at,'') DESC, p.rowid DESC",
                    "captured_asc": "COALESCE(p.captured_at,'') ASC, p.rowid DESC"}.get(sort, "p.rowid DESC")
        rows = db.execute(f"""SELECT p.*, p.rowid AS page_cursor,
            COALESCE((SELECT status FROM photo_processing_jobs j WHERE j.photo_id=p.id), 'ready') AS processing_status,
            (SELECT GROUP_CONCAT(t.name, char(31)) FROM photo_tags pt JOIN tags t ON t.id=pt.tag_id
             WHERE pt.photo_id=p.id) AS tag_names
            FROM photos p WHERE {page_where} ORDER BY {order_by} LIMIT ?""", (*page_params, limit + 1)).fetchall()
        has_more = len(rows) > limit
        items = [dict(row) for row in rows[:limit]]
        next_cursor = None
        if has_more and items:
            last = items[-1]
            cursor_value = (last["size"] if sort == "size_desc" else
                            (last.get("captured_at") or "") if sort in {"captured_desc", "captured_asc"} else "")
            next_cursor = f"{cursor_value}~{last['page_cursor']}"
        for item in items:
            item["favorite"], item["trashed"] = bool(item["favorite"]), bool(item["trashed"])
            tag_names = item.pop("tag_names")
            item["tags"] = tag_names.split(chr(31)) if tag_names else []
            item.pop("page_cursor", None)
        return {"items": items, "next_cursor": next_cursor, "total": total}


def save_all(data_dir: Path, items):
    with connect(data_dir) as db:
        for item in items:
            upsert(db, item)


def update_fields(data_dir: Path, photo_id: str, changes: dict):
    allowed = {"name", "favorite", "trashed", "share_token", "thumbnail_name", "width", "height", "captured_at", "share_expires_at", "share_views", "caption", "perceptual_hash"}
    fields = {key: value for key, value in changes.items() if key in allowed}
    if not fields:
        return
    assignments = ", ".join(f"{key}=?" for key in fields)
    with connect(data_dir) as db:
        cursor = db.execute(f"UPDATE photos SET {assignments} WHERE id=?", (*fields.values(), photo_id))
        if cursor.rowcount == 0:
            raise KeyError(photo_id)


def set_photos_trashed(data_dir: Path, photo_ids: list[str], trashed: bool):
    unique_ids = list(dict.fromkeys(photo_ids))
    if not unique_ids:
        return 0
    placeholders = ",".join("?" for _ in unique_ids)
    with connect(data_dir) as db:
        found = db.execute(f"SELECT COUNT(*) AS count FROM photos WHERE id IN ({placeholders})", unique_ids).fetchone()["count"]
        if found != len(unique_ids):
            raise KeyError("One or more photos were not found")
        cursor = db.execute(f"UPDATE photos SET trashed=? WHERE id IN ({placeholders})",
                            (int(trashed), *unique_ids))
        return cursor.rowcount


def get_photo(data_dir: Path, photo_id: str):
    with connect(data_dir) as db:
        row = db.execute("""SELECT p.*, GROUP_CONCAT(t.name, char(31)) AS tag_names FROM photos p
            LEFT JOIN photo_tags pt ON pt.photo_id=p.id LEFT JOIN tags t ON t.id=pt.tag_id
            WHERE p.id=? GROUP BY p.id""", (photo_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["favorite"], item["trashed"] = bool(item["favorite"]), bool(item["trashed"])
        tag_names = item.pop("tag_names")
        item["tags"] = tag_names.split(chr(31)) if tag_names else []
        return item


def set_photo_metadata(data_dir: Path, photo_id: str, caption: str, tags: list[str]):
    with connect(data_dir) as db:
        cursor = db.execute("UPDATE photos SET caption=? WHERE id=?", (caption, photo_id))
        if cursor.rowcount == 0:
            raise KeyError(photo_id)
        db.execute("DELETE FROM photo_tags WHERE photo_id=?", (photo_id,))
        for tag in tags:
            db.execute("INSERT OR IGNORE INTO tags(name) VALUES(?)", (tag,))
            tag_id = db.execute("SELECT id FROM tags WHERE LOWER(name)=LOWER(?)", (tag,)).fetchone()["id"]
            db.execute("INSERT OR IGNORE INTO photo_tags(photo_id,tag_id) VALUES(?,?)", (photo_id, tag_id))
        db.execute("DELETE FROM tags WHERE id NOT IN (SELECT DISTINCT tag_id FROM photo_tags)")


def delete_photo(data_dir: Path, photo_id: str):
    with connect(data_dir) as db:
        db.execute("DELETE FROM photo_processing_jobs WHERE photo_id=?", (photo_id,))
        db.execute("DELETE FROM album_photos WHERE photo_id=?", (photo_id,))
        db.execute("DELETE FROM photo_tags WHERE photo_id=?", (photo_id,))
        db.execute("DELETE FROM photos WHERE id=?", (photo_id,))
        db.execute("DELETE FROM tags WHERE id NOT IN (SELECT DISTINCT tag_id FROM photo_tags)")


def queue_photo_processing(data_dir: Path, photo_id: str, now: str):
    with connect(data_dir) as db:
        current = db.execute("SELECT * FROM photo_processing_jobs WHERE photo_id=?", (photo_id,)).fetchone()
        if current and current["status"] in {"queued", "running"}:
            return dict(current), False
        db.execute("""INSERT INTO photo_processing_jobs(photo_id,status,error,created_at,updated_at)
            VALUES(?,'queued',NULL,?,?)
            ON CONFLICT(photo_id) DO UPDATE SET status='queued',error=NULL,updated_at=excluded.updated_at""",
                   (photo_id, now, now))
        return dict(db.execute("SELECT * FROM photo_processing_jobs WHERE photo_id=?", (photo_id,)).fetchone()), True


def update_photo_processing(data_dir: Path, photo_id: str, now: str, status: str, error: str | None = None):
    with connect(data_dir) as db:
        db.execute("UPDATE photo_processing_jobs SET status=?,error=?,updated_at=? WHERE photo_id=?",
                   (status, error, now, photo_id))


def get_photo_processing(data_dir: Path, photo_id: str):
    with connect(data_dir) as db:
        row = db.execute("SELECT * FROM photo_processing_jobs WHERE photo_id=?", (photo_id,)).fetchone()
        return dict(row) if row else None


def list_albums(data_dir: Path):
    with connect(data_dir) as db:
        return [dict(row) for row in db.execute("""SELECT a.id,a.name,a.created_at,a.description,
            a.share_token,a.share_expires_at,a.share_views,
            COUNT(CASE WHEN member_p.trashed=0 THEN 1 END) AS photo_count,
            COALESCE(
                CASE WHEN EXISTS (SELECT 1 FROM album_photos custom_ap JOIN photos custom_p ON custom_p.id=custom_ap.photo_id
                    WHERE custom_ap.album_id=a.id AND custom_ap.photo_id=a.cover_photo_id AND custom_p.trashed=0)
                    THEN a.cover_photo_id END,
                (SELECT ap2.photo_id FROM album_photos ap2 JOIN photos p2 ON p2.id=ap2.photo_id
                 WHERE ap2.album_id=a.id AND p2.trashed=0 ORDER BY ap2.added_at DESC LIMIT 1)
            ) AS cover_photo_id
            FROM albums a LEFT JOIN album_photos ap ON ap.album_id=a.id
            LEFT JOIN photos member_p ON member_p.id=ap.photo_id
            GROUP BY a.id ORDER BY a.created_at DESC""")]


def create_album(data_dir: Path, album_id: str, name: str, created_at: str):
    with connect(data_dir) as db:
        db.execute("INSERT INTO albums(id,name,created_at) VALUES(?,?,?)", (album_id, name, created_at))


def add_photos_to_album(data_dir: Path, album_id: str, photo_ids: list[str], added_at: str):
    with connect(data_dir) as db:
        if not db.execute("SELECT 1 FROM albums WHERE id=?", (album_id,)).fetchone():
            raise KeyError(album_id)
        db.executemany("INSERT OR IGNORE INTO album_photos(album_id,photo_id,added_at) VALUES(?,?,?)",
                       [(album_id, photo_id, added_at) for photo_id in photo_ids])


def album_photo_ids(data_dir: Path, album_id: str):
    with connect(data_dir) as db:
        return {row["photo_id"] for row in db.execute("SELECT photo_id FROM album_photos WHERE album_id=?", (album_id,))}


def rename_album(data_dir: Path, album_id: str, name: str):
    with connect(data_dir) as db:
        cursor = db.execute("UPDATE albums SET name=? WHERE id=?", (name, album_id))
        if cursor.rowcount == 0:
            raise KeyError(album_id)


def update_album_presentation(data_dir: Path, album_id: str, description: str, cover_photo_id: str | None):
    with connect(data_dir) as db:
        if not db.execute("SELECT 1 FROM albums WHERE id=?", (album_id,)).fetchone():
            raise KeyError(album_id)
        if cover_photo_id and not db.execute("""SELECT 1 FROM album_photos ap JOIN photos p ON p.id=ap.photo_id
            WHERE ap.album_id=? AND ap.photo_id=? AND p.trashed=0""", (album_id, cover_photo_id)).fetchone():
            raise ValueError(cover_photo_id)
        db.execute("UPDATE albums SET description=?,cover_photo_id=? WHERE id=?",
                   (description, cover_photo_id, album_id))


def remove_photos_from_album(data_dir: Path, album_id: str, photo_ids: list[str]):
    with connect(data_dir) as db:
        db.executemany("DELETE FROM album_photos WHERE album_id=? AND photo_id=?",
                       [(album_id, photo_id) for photo_id in photo_ids])


def delete_album(data_dir: Path, album_id: str):
    with connect(data_dir) as db:
        db.execute("DELETE FROM album_photos WHERE album_id=?", (album_id,))
        cursor = db.execute("DELETE FROM albums WHERE id=?", (album_id,))
        if cursor.rowcount == 0:
            raise KeyError(album_id)


def get_upload_by_hash(data_dir: Path, sha256: str):
    with connect(data_dir) as db:
        row = db.execute("SELECT * FROM upload_sessions WHERE sha256=?", (sha256,)).fetchone()
        return dict(row) if row else None


def create_upload(data_dir: Path, item: dict):
    with connect(data_dir) as db:
        db.execute("""INSERT INTO upload_sessions(id,filename,sha256,size,content_type,created_at)
            VALUES(:id,:filename,:sha256,:size,:content_type,:created_at)""", item)


def delete_upload(data_dir: Path, upload_id: str):
    with connect(data_dir) as db:
        db.execute("DELETE FROM upload_sessions WHERE id=?", (upload_id,))


def create_auth_session(data_dir: Path, token: str, created_at: str, expires_at: str):
    with connect(data_dir) as db:
        db.execute("DELETE FROM auth_sessions WHERE expires_at <= ?", (created_at,))
        db.execute("INSERT INTO auth_sessions(token,created_at,expires_at) VALUES(?,?,?)",
                   (token, created_at, expires_at))


def auth_session_valid(data_dir: Path, token: str, now: str):
    with connect(data_dir) as db:
        return db.execute("SELECT 1 FROM auth_sessions WHERE token=? AND expires_at>?", (token, now)).fetchone() is not None


def delete_auth_session(data_dir: Path, token: str):
    with connect(data_dir) as db:
        db.execute("DELETE FROM auth_sessions WHERE token=?", (token,))


def record_login_failure(data_dir: Path, client_key: str, attempted_at: str):
    with connect(data_dir) as db:
        db.execute("INSERT INTO login_attempts(client_key,attempted_at) VALUES(?,?)", (client_key, attempted_at))


def recent_login_failures(data_dir: Path, client_key: str, since: str):
    with connect(data_dir) as db:
        return db.execute("SELECT COUNT(*) AS count FROM login_attempts WHERE client_key=? AND attempted_at>=?",
                          (client_key, since)).fetchone()["count"]


def clear_login_failures(data_dir: Path, client_key: str):
    with connect(data_dir) as db:
        db.execute("DELETE FROM login_attempts WHERE client_key=?", (client_key,))


def security_stats(data_dir: Path, now: str, failure_since: str):
    with connect(data_dir) as db:
        db.execute("DELETE FROM auth_sessions WHERE expires_at<=?", (now,))
        return {
            "active_sessions": db.execute("SELECT COUNT(*) AS count FROM auth_sessions WHERE expires_at>?", (now,)).fetchone()["count"],
            "recent_failed_logins": db.execute("SELECT COUNT(*) AS count FROM login_attempts WHERE attempted_at>=?", (failure_since,)).fetchone()["count"],
        }


def delete_all_auth_sessions(data_dir: Path):
    with connect(data_dir) as db:
        db.execute("DELETE FROM auth_sessions")


def record_api_event(data_dir: Path, method: str, path: str, status: int, duration_ms: float, created_at: str):
    with connect(data_dir) as db:
        event_id = db.execute(
            """INSERT INTO api_events(method,path,status,duration_ms,created_at)
                VALUES(?,?,?,?,?) RETURNING id""",
            (method, path, status, duration_ms, created_at),
        ).fetchone()["id"]
        # Keep request logging cheap: bounded cleanup is maintenance work, not
        # something every API request should repeat.
        if event_id % 100 == 0:
            db.execute("""DELETE FROM api_events WHERE id < COALESCE(
                (SELECT id FROM api_events ORDER BY id DESC LIMIT 1 OFFSET 999), 0)""")


def recent_api_events(data_dir: Path, limit: int = 20):
    with connect(data_dir) as db:
        return [dict(row) for row in db.execute("""SELECT method,path,status,ROUND(duration_ms,1) AS duration_ms,created_at
            FROM api_events WHERE method != 'GET' ORDER BY created_at DESC LIMIT ?""", (limit,))]


def api_metrics(data_dir: Path):
    with connect(data_dir) as db:
        row = db.execute("""SELECT COUNT(*) AS request_count, ROUND(AVG(duration_ms),1) AS average_ms,
            SUM(CASE WHEN status >= 400 THEN 1 ELSE 0 END) AS error_count FROM api_events""").fetchone()
        return dict(row)


def increment_share_views(data_dir: Path, photo_id: str):
    with connect(data_dir) as db:
        db.execute("UPDATE photos SET share_views=share_views+1 WHERE id=?", (photo_id,))


def set_album_share(data_dir: Path, album_id: str, token: str | None, expires_at: str | None):
    with connect(data_dir) as db:
        cursor = db.execute("""UPDATE albums SET share_token=?, share_expires_at=?,
            share_views=CASE WHEN ? IS NULL THEN share_views ELSE 0 END WHERE id=?""",
                            (token, expires_at, token, album_id))
        if cursor.rowcount == 0:
            raise KeyError(album_id)


def get_shared_album(data_dir: Path, token: str):
    with connect(data_dir) as db:
        row = db.execute("SELECT * FROM albums WHERE share_token=?", (token,)).fetchone()
        return dict(row) if row else None


def increment_album_share_views(data_dir: Path, album_id: str):
    with connect(data_dir) as db:
        db.execute("UPDATE albums SET share_views=share_views+1 WHERE id=?", (album_id,))


def create_integrity_job(data_dir: Path, job_id: str, created_at: str):
    with connect(data_dir) as db:
        active = db.execute("""SELECT * FROM integrity_jobs WHERE status IN ('queued','running')
            ORDER BY created_at DESC LIMIT 1""").fetchone()
        if active:
            return dict(active), False
        db.execute("""INSERT INTO integrity_jobs(id,status,created_at,updated_at)
            VALUES(?,'queued',?,?)""", (job_id, created_at, created_at))
        return dict(db.execute("SELECT * FROM integrity_jobs WHERE id=?", (job_id,)).fetchone()), True


def update_integrity_job(data_dir: Path, job_id: str, updated_at: str, **changes):
    allowed = {"status", "total", "completed", "current_name", "result_json", "error"}
    fields = {key: value for key, value in changes.items() if key in allowed}
    fields["updated_at"] = updated_at
    assignments = ", ".join(f"{key}=?" for key in fields)
    with connect(data_dir) as db:
        db.execute(f"UPDATE integrity_jobs SET {assignments} WHERE id=?", (*fields.values(), job_id))


def get_integrity_job(data_dir: Path, job_id: str | None = None):
    with connect(data_dir) as db:
        row = (db.execute("SELECT * FROM integrity_jobs WHERE id=?", (job_id,)).fetchone() if job_id else
               db.execute("SELECT * FROM integrity_jobs ORDER BY created_at DESC LIMIT 1").fetchone())
        if not row:
            return None
        item = dict(row)
        item["result"] = json.loads(item.pop("result_json")) if item.get("result_json") else None
        return item
