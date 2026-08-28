from __future__ import annotations

import hashlib
import hmac
import json
import os
import asyncio
import shutil
import tempfile
import time
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask, BackgroundTasks as StarletteBackgroundTasks
from PIL import Image, ImageOps
from pydantic import BaseModel
from .db import (add_photos_to_album, album_photo_ids, all_photos, create_album,
                 api_metrics, auth_session_valid, clear_login_failures, create_auth_session, create_integrity_job, create_upload,
                 delete_album, delete_all_auth_sessions, delete_auth_session, delete_photo, delete_upload, get_photo,
                 get_upload_by_hash, increment_share_views, initialize, list_albums, remove_photos_from_album,
                 get_integrity_job, get_photo_processing, get_shared_album, increment_album_share_views, query_photos,
                 queue_photo_processing, recent_api_events, recent_login_failures,
                 record_api_event, record_login_failure, rename_album, save_all, security_stats, set_album_share,
                 set_photo_metadata, set_photos_trashed, update_album_presentation, update_fields, update_integrity_job,
                 update_photo_processing)
from .database import backend_name
from .storage import create_storage

app = FastAPI(title="PixelVault API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

DATA = Path(os.getenv("DATA_DIR", "data"))
CHUNKS = DATA / "chunks"
INDEX = DATA / "photos.json"
CHUNKS.mkdir(parents=True, exist_ok=True)
STORAGE = create_storage(DATA)
initialize(DATA, INDEX)
VAULT_PASSWORD = os.getenv("PIXELVAULT_DEMO_PASSWORD", "demo1234")
ENVIRONMENT = os.getenv("PIXELVAULT_ENV", "development").lower()
COOKIE_SECURE = os.getenv("PIXELVAULT_COOKIE_SECURE", "false").lower() == "true"
if ENVIRONMENT == "production" and VAULT_PASSWORD == "demo1234":
    raise RuntimeError("PIXELVAULT_DEMO_PASSWORD must be changed in production")


@app.middleware("http")
async def require_vault_session(request: Request, call_next):
    path = request.url.path
    public = path in {"/api/health", "/api/auth/login"} or path.startswith("/api/share/")
    if request.method != "OPTIONS" and path.startswith("/api/") and not public:
        token = request.cookies.get("pixelvault_session", "")
        now = datetime.now(timezone.utc).isoformat()
        if not token or not await asyncio.to_thread(auth_session_valid, DATA, token, now):
            return JSONResponse({"detail": "Vault is locked"}, status_code=401)
    return await call_next(request)


@app.middleware("http")
async def observe_api_requests(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        audit_task = BackgroundTask(
            record_api_event, DATA, request.method, request.url.path, response.status_code,
            (time.perf_counter() - started) * 1000, datetime.now(timezone.utc).isoformat())
        response.background = (StarletteBackgroundTasks([response.background, audit_task])
                               if response.background else audit_task)
    return response


def records() -> list[dict]:
    return all_photos(DATA)


def save(items: list[dict]) -> None:
    save_all(DATA, items)


def original_key(name: str) -> str:
    return f"objects/{name}"


def thumbnail_key(name: str) -> str:
    return f"thumbnails/{name}"


def media_response(key: str, content_type: str):
    try:
        handle = STORAGE.open(key)
    except FileNotFoundError:
        raise HTTPException(404, "Stored media was not found")
    blocks = iter(lambda: handle.read(1024 * 1024), b"")
    return StreamingResponse(blocks, media_type=content_type, background=BackgroundTask(handle.close))


def enrich_image(item: dict):
    thumb_name = f"{item['sha256']}.webp"
    thumb = tempfile.NamedTemporaryFile(prefix="pixelvault-thumb-", suffix=".webp", delete=False)
    thumb_path = Path(thumb.name)
    thumb.close()
    try:
        with STORAGE.local_file(original_key(item["object_name"])) as source:
            with Image.open(source) as image:
                image = ImageOps.exif_transpose(image)
                item["width"], item["height"] = image.size
                exif = image.getexif()
                item["captured_at"] = exif.get(36867) or exif.get(306)
                image.thumbnail((640, 640))
                image.convert("RGB").save(thumb_path, "WEBP", quality=82, method=6)
        STORAGE.put_file(thumbnail_key(thumb_name), thumb_path, "image/webp")
        item["thumbnail_name"] = thumb_name
    except Exception:
        item["thumbnail_name"] = None
    finally:
        thumb_path.unlink(missing_ok=True)
    return item


def image_difference_hash(path: Path):
    with Image.open(path) as image:
        sample = ImageOps.exif_transpose(image).convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        pixels = list(sample.getdata())
    bits = 0
    for row in range(8):
        for column in range(8):
            bits = (bits << 1) | int(pixels[row * 9 + column] > pixels[row * 9 + column + 1])
    return f"{bits:016x}"


def hamming_distance(first: str, second: str):
    return (int(first, 16) ^ int(second, 16)).bit_count()


def run_photo_processing(photo_id: str):
    now = lambda: datetime.now(timezone.utc).isoformat()
    update_photo_processing(DATA, photo_id, now(), "running")
    try:
        item = get_photo(DATA, photo_id)
        if not item:
            raise RuntimeError("Photo no longer exists")
        processed = enrich_image(dict(item))
        if not processed.get("thumbnail_name"):
            raise RuntimeError("The uploaded file could not be decoded as an image")
        update_fields(DATA, photo_id, {"thumbnail_name": processed["thumbnail_name"],
                      "width": processed.get("width"), "height": processed.get("height"),
                      "captured_at": processed.get("captured_at")})
        update_photo_processing(DATA, photo_id, now(), "ready")
    except Exception as error:
        update_photo_processing(DATA, photo_id, now(), "failed", str(error)[:500])


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "pixelvault", "database": backend_name(), "storage": STORAGE.name}


class AlbumCreate(BaseModel):
    name: str

class AlbumPresentation(BaseModel):
    description: str = ""
    cover_photo_id: str | None = None

class BatchAction(BaseModel):
    photo_ids: list[str]
    action: str
    album_id: str | None = None
    captured_at: str | None = None

class LoginRequest(BaseModel):
    password: str

class PhotoMetadata(BaseModel):
    caption: str = ""
    tags: list[str] = []
    captured_at: str | None = None

class ExportRequest(BaseModel):
    photo_ids: list[str]

class DuplicateCleanup(BaseModel):
    keep_id: str
    trash_ids: list[str]


def normalized_capture_time(value: str | None):
    if value is None or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as error:
        raise HTTPException(422, "Capture time must be a valid ISO date and time") from error
    return parsed.strftime("%Y:%m:%d %H:%M:%S")


def build_photo_archive(items: list[dict], archive_name: str):
    if not items: raise HTTPException(422, "No photos to export")
    handle = tempfile.NamedTemporaryFile(prefix="pixelvault-", suffix=".zip", delete=False)
    target = Path(handle.name); handle.close()
    manifest = []
    used_names: set[str] = set()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for index, item in enumerate(items, 1):
            safe_name = Path(item["name"]).name or f"photo-{index}"
            if safe_name.casefold() in used_names:
                safe_name = f"{index}-{safe_name}"
            used_names.add(safe_name.casefold())
            with STORAGE.local_file(original_key(item["object_name"])) as source:
                archive.write(source, f"photos/{safe_name}")
            manifest.append({key: item.get(key) for key in
                             ("id", "name", "sha256", "size", "content_type", "width", "height",
                              "captured_at", "caption", "tags")})
        archive.writestr("manifest.json", json.dumps({"exported_at": datetime.now(timezone.utc).isoformat(),
                                                       "photo_count": len(items), "photos": manifest},
                                                      ensure_ascii=False, indent=2))
    return FileResponse(target, media_type="application/zip", filename=f"{archive_name}.zip",
                        background=BackgroundTask(target.unlink, missing_ok=True))


@app.post("/api/auth/login")
def login(payload: LoginRequest, request: Request, response: Response):
    client_key = request.client.host if request.client else "local"
    now = datetime.now(timezone.utc)
    since = (now - timedelta(minutes=5)).isoformat()
    if recent_login_failures(DATA, client_key, since) >= 5:
        raise HTTPException(429, "Too many failed attempts. Try again in five minutes.", headers={"Retry-After": "300"})
    if not hmac.compare_digest(payload.password, VAULT_PASSWORD):
        record_login_failure(DATA, client_key, now.isoformat())
        raise HTTPException(401, "Incorrect password")
    clear_login_failures(DATA, client_key)
    token = uuid.uuid4().hex + uuid.uuid4().hex
    create_auth_session(DATA, token, now.isoformat(), (now + timedelta(hours=8)).isoformat())
    response.set_cookie("pixelvault_session", token, max_age=28800, httponly=True,
                        samesite="lax", secure=COOKIE_SECURE, path="/")
    return {"authenticated": True, "expires_in": 28800}


@app.get("/api/auth/me")
def auth_me():
    return {"authenticated": True, "owner": "Personal vault"}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get("pixelvault_session", "")
    if token: delete_auth_session(DATA, token)
    response.delete_cookie("pixelvault_session", path="/")
    return {"authenticated": False}


@app.get("/api/security")
def security_overview():
    now = datetime.now(timezone.utc)
    return {**security_stats(DATA, now.isoformat(), (now - timedelta(hours=24)).isoformat()),
            "session_ttl_hours": 8, "failure_limit": 5, "failure_window_minutes": 5,
            "cookie_http_only": True, "same_site": "lax", "network_scope": "localhost only"}


@app.post("/api/security/revoke-all")
def revoke_all_sessions(response: Response):
    delete_all_auth_sessions(DATA)
    response.delete_cookie("pixelvault_session", path="/")
    return {"revoked": True}


@app.get("/api/photos")
def list_photos(limit: int = 60, cursor: str = "", view: str = "photos", search: str = "",
                album_id: str | None = None, month: str | None = None, date_from: str | None = None,
                date_to: str | None = None, min_size_mb: float = 0, orientation: str = "any",
                sort: str = "newest"):
    if orientation not in {"any", "landscape", "portrait", "square"}:
        raise HTTPException(422, "Unsupported orientation filter")
    if sort not in {"newest", "captured_desc", "captured_asc", "size_desc"}:
        raise HTTPException(422, "Unsupported photo sort")
    if min_size_mb < 0 or min_size_mb > 1024 * 100:
        raise HTTPException(422, "Minimum size is outside the supported range")
    for value in (date_from, date_to):
        if value:
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError as error:
                raise HTTPException(422, "Dates must use YYYY-MM-DD") from error
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "Start date must not be after end date")
    return query_photos(DATA, min(max(limit, 1), 100), cursor, view, search.strip(), album_id, month,
                        date_from, date_to, int(min_size_mb * 1024 * 1024), orientation, sort)


@app.get("/api/photos/{photo_id}/processing")
def photo_processing(photo_id: str):
    if not get_photo(DATA, photo_id):
        raise HTTPException(404, "Photo not found")
    return get_photo_processing(DATA, photo_id) or {"photo_id": photo_id, "status": "ready", "error": None}


@app.post("/api/photos/{photo_id}/processing/retry")
def retry_photo_processing(photo_id: str, background_tasks: BackgroundTasks):
    if not get_photo(DATA, photo_id):
        raise HTTPException(404, "Photo not found")
    job, created = queue_photo_processing(DATA, photo_id, datetime.now(timezone.utc).isoformat())
    if created:
        background_tasks.add_task(run_photo_processing, photo_id)
    return {**job, "reused": not created}


@app.get("/api/timeline")
def timeline():
    grouped: dict[str, dict] = {}
    for item in records():
        if item.get("trashed"): continue
        raw = item.get("captured_at") or ""
        key = raw[:7].replace(":", "-") if len(raw) >= 7 else "unknown"
        if key not in grouped:
            grouped[key] = {"month": key, "photo_count": 0, "cover_photo_id": item["id"]}
        grouped[key]["photo_count"] += 1
    return {"items": sorted(grouped.values(), key=lambda item: item["month"], reverse=True)}


@app.get("/api/albums")
def albums():
    return {"items": list_albums(DATA)}


@app.post("/api/albums")
def new_album(payload: AlbumCreate):
    name = payload.name.strip()
    if not name: raise HTTPException(422, "Album name is required")
    item = {"id": uuid.uuid4().hex, "name": name, "created_at": datetime.now(timezone.utc).isoformat()}
    try:
        create_album(DATA, item["id"], item["name"], item["created_at"])
    except Exception as error:
        raise HTTPException(409, "Album name already exists") from error
    return item


@app.patch("/api/albums/{album_id}")
def edit_album(album_id: str, payload: AlbumCreate):
    name = payload.name.strip()
    if not name: raise HTTPException(422, "Album name is required")
    try:
        rename_album(DATA, album_id, name)
    except KeyError:
        raise HTTPException(404, "Album not found")
    except Exception as error:
        raise HTTPException(409, "Album name already exists") from error
    return next(item for item in list_albums(DATA) if item["id"] == album_id)


@app.patch("/api/albums/{album_id}/presentation")
def edit_album_presentation(album_id: str, payload: AlbumPresentation):
    try:
        update_album_presentation(DATA, album_id, payload.description.strip()[:500], payload.cover_photo_id)
    except KeyError:
        raise HTTPException(404, "Album not found")
    except ValueError:
        raise HTTPException(422, "Cover photo must be a visible member of this album")
    return next(item for item in list_albums(DATA) if item["id"] == album_id)


@app.delete("/api/albums/{album_id}")
def remove_album(album_id: str):
    try: delete_album(DATA, album_id)
    except KeyError: raise HTTPException(404, "Album not found")
    return {"deleted": True}


@app.delete("/api/albums/{album_id}/photos/{photo_id}")
def remove_photo_from_album(album_id: str, photo_id: str):
    if not any(album["id"] == album_id for album in list_albums(DATA)):
        raise HTTPException(404, "Album not found")
    if photo_id not in album_photo_ids(DATA, album_id):
        raise HTTPException(404, "Photo is not part of this album")
    remove_photos_from_album(DATA, album_id, [photo_id])
    return {"removed": True, "album_id": album_id, "photo_id": photo_id,
            "photo_deleted": False}


@app.get("/api/albums/{album_id}/export")
def export_album(album_id: str):
    album = next((item for item in list_albums(DATA) if item["id"] == album_id), None)
    if not album: raise HTTPException(404, "Album not found")
    ids = album_photo_ids(DATA, album_id)
    items = [item for item in records() if item["id"] in ids and not item.get("trashed")]
    safe_name = "".join(char for char in album["name"] if char.isalnum() or char in " -_").strip() or "album"
    return build_photo_archive(items, safe_name)


@app.post("/api/albums/{album_id}/share")
def share_album(album_id: str, expires_hours: int = 168):
    if expires_hours < 1 or expires_hours > 24 * 365:
        raise HTTPException(422, "Share duration must be between 1 hour and 1 year")
    token = uuid.uuid4().hex[:16]
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=expires_hours)).isoformat()
    try:
        set_album_share(DATA, album_id, token, expires_at)
    except KeyError:
        raise HTTPException(404, "Album not found")
    return {"token": token, "url": f"/album-share/{token}", "expires_at": expires_at}


@app.delete("/api/albums/{album_id}/share")
def revoke_album_share(album_id: str):
    try:
        set_album_share(DATA, album_id, None, None)
    except KeyError:
        raise HTTPException(404, "Album not found")
    return {"revoked": True}


def public_album(token: str):
    album = get_shared_album(DATA, token)
    if not album:
        raise HTTPException(404, "Shared album not found")
    if album.get("share_expires_at") and album["share_expires_at"] <= datetime.now(timezone.utc).isoformat():
        raise HTTPException(410, "Shared album expired")
    return album


@app.get("/api/share/albums/{token}")
def shared_album(token: str):
    album = public_album(token)
    ids = album_photo_ids(DATA, album["id"])
    photos = [{key: item.get(key) for key in ("id", "name", "width", "height", "captured_at", "caption")}
              for item in records() if item["id"] in ids and not item.get("trashed")]
    increment_album_share_views(DATA, album["id"])
    return {"id": album["id"], "name": album["name"], "description": album.get("description") or "",
            "cover_photo_id": album.get("cover_photo_id"), "photo_count": len(photos), "photos": photos,
            "expires_at": album.get("share_expires_at"), "views": album.get("share_views", 0) + 1}


def shared_album_photo(token: str, photo_id: str):
    album = public_album(token)
    if photo_id not in album_photo_ids(DATA, album["id"]):
        raise HTTPException(404, "Photo is not part of this shared album")
    item = get_photo(DATA, photo_id)
    if not item or item.get("trashed"):
        raise HTTPException(404, "Photo not found")
    return item


@app.get("/api/share/albums/{token}/photos/{photo_id}/thumbnail")
def shared_album_thumbnail(token: str, photo_id: str):
    item = shared_album_photo(token, photo_id)
    if not item.get("thumbnail_name") or not STORAGE.exists(thumbnail_key(item["thumbnail_name"])):
        item = enrich_image(item)
        if item.get("thumbnail_name"):
            update_photo(photo_id, thumbnail_name=item["thumbnail_name"], width=item.get("width"),
                         height=item.get("height"), captured_at=item.get("captured_at"))
    key = thumbnail_key(item["thumbnail_name"]) if item.get("thumbnail_name") else original_key(item["object_name"])
    return media_response(key, "image/webp" if item.get("thumbnail_name") else item["content_type"])


@app.get("/api/share/albums/{token}/photos/{photo_id}/content")
def shared_album_content(token: str, photo_id: str):
    item = shared_album_photo(token, photo_id)
    return media_response(original_key(item["object_name"]), item["content_type"])


@app.post("/api/photos/export")
def export_photos(payload: ExportRequest):
    wanted = set(payload.photo_ids)
    items = [item for item in records() if item["id"] in wanted and not item.get("trashed")]
    if len(items) != len(wanted): raise HTTPException(404, "One or more photos were not found")
    return build_photo_archive(items, "pixelvault-selection")


@app.get("/api/backups/export")
def export_vault_backup():
    items, albums = records(), list_albums(DATA)
    handle = tempfile.NamedTemporaryFile(prefix="pixelvault-backup-", suffix=".zip", delete=False)
    target = Path(handle.name); handle.close()
    manifest_photos = []
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for item in items:
            archive_path = f"objects/{item['id']}/{Path(item['name']).name or 'photo'}"
            with STORAGE.local_file(original_key(item["object_name"])) as source:
                archive.write(source, archive_path)
            manifest_photos.append({**{key: item.get(key) for key in
                                      ("id", "name", "sha256", "size", "content_type", "favorite", "trashed",
                                       "width", "height", "captured_at", "caption", "tags")},
                                    "archive_path": archive_path})
        manifest_albums = [{"id": album["id"], "name": album["name"], "description": album.get("description") or "",
                            "cover_photo_id": album.get("cover_photo_id"),
                            "photo_ids": sorted(album_photo_ids(DATA, album["id"]))} for album in albums]
        archive.writestr("backup.json", json.dumps({"format": "pixelvault-backup", "version": 1,
                         "created_at": datetime.now(timezone.utc).isoformat(), "photos": manifest_photos,
                         "albums": manifest_albums}, ensure_ascii=False, indent=2))
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return FileResponse(target, media_type="application/zip", filename=f"pixelvault-backup-{stamp}.zip",
                        background=BackgroundTask(target.unlink, missing_ok=True))


@app.post("/api/backups/import")
def import_vault_backup(backup: UploadFile = File(...)):
    backup.file.seek(0, 2); compressed_size = backup.file.tell(); backup.file.seek(0)
    if compressed_size > 5 * 1024 * 1024 * 1024:
        raise HTTPException(413, "Backup exceeds the 5 GB import limit")
    try:
        archive = zipfile.ZipFile(backup.file)
    except zipfile.BadZipFile as error:
        raise HTTPException(422, "Backup is not a valid ZIP archive") from error
    with archive:
        infos = archive.infolist()
        if len(infos) > 10000 or sum(info.file_size for info in infos) > 20 * 1024 * 1024 * 1024:
            raise HTTPException(422, "Backup expands beyond safe limits")
        try:
            manifest = json.loads(archive.read("backup.json"))
        except (KeyError, json.JSONDecodeError) as error:
            raise HTTPException(422, "Backup manifest is missing or invalid") from error
        if manifest.get("format") != "pixelvault-backup" or manifest.get("version") != 1:
            raise HTTPException(422, "Unsupported backup format")
        existing = {item["sha256"]: item for item in records()}
        id_map: dict[str, str] = {}
        imported = duplicates = restored_objects = 0
        for source_item in manifest.get("photos", []):
            sha = source_item.get("sha256", "")
            path = PurePosixPath(source_item.get("archive_path", ""))
            if len(sha) != 64 or not path.parts or path.parts[0] != "objects" or ".." in path.parts or path.is_absolute():
                raise HTTPException(422, "Backup contains an unsafe photo entry")
            existing_item = existing.get(sha)
            if existing_item and STORAGE.exists(original_key(existing_item["object_name"])):
                id_map[source_item["id"]] = existing_item["id"]
                duplicates += 1
                continue
            try:
                source = archive.open(path.as_posix())
            except KeyError as error:
                raise HTTPException(422, f"Backup photo is missing: {source_item.get('name', 'unknown')}") from error
            suffix = Path(source_item.get("name", "")).suffix.lower()
            object_name = existing_item["object_name"] if existing_item else f"{sha}{suffix}"
            temporary = tempfile.NamedTemporaryFile(prefix="pixelvault-import-", dir=DATA, delete=False)
            digest = hashlib.sha256()
            with source, temporary:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(block); temporary.write(block)
            temporary_path = Path(temporary.name)
            if digest.hexdigest() != sha:
                temporary_path.unlink(missing_ok=True)
                raise HTTPException(422, f"Checksum mismatch: {source_item.get('name', 'unknown')}")
            content_type = source_item.get("content_type") or "application/octet-stream"
            object_key = original_key(object_name)
            existed = STORAGE.exists(object_key)
            try:
                STORAGE.put_file(object_key, temporary_path, content_type)
            finally:
                temporary_path.unlink(missing_ok=True)
            if existing_item:
                id_map[source_item["id"]] = existing_item["id"]
                duplicates += 1
                restored_objects += 1
                continue
            new_id = uuid.uuid4().hex
            item = {"id": new_id, "name": Path(source_item.get("name", "photo")).name, "sha256": sha,
                    "object_name": object_name, "content_type": content_type,
                    "size": int(source_item.get("size") or STORAGE.size(original_key(object_name))),
                    "favorite": bool(source_item.get("favorite")),
                    "trashed": bool(source_item.get("trashed")), "share_token": None, "thumbnail_name": None,
                    "width": source_item.get("width"), "height": source_item.get("height"),
                    "captured_at": source_item.get("captured_at"), "share_expires_at": None, "share_views": 0,
                    "caption": source_item.get("caption") or ""}
            try:
                save([item]); set_photo_metadata(DATA, new_id, item["caption"], source_item.get("tags") or [])
            except Exception:
                if not existed:
                    STORAGE.delete(object_key)
                raise
            existing[sha] = item; id_map[source_item["id"]] = new_id; imported += 1
        existing_albums = {album["name"].casefold(): album for album in list_albums(DATA)}
        restored_albums = 0
        for source_album in manifest.get("albums", []):
            name = str(source_album.get("name", "")).strip()[:120]
            if not name: continue
            album = existing_albums.get(name.casefold())
            created_album = False
            if not album:
                album = {"id": uuid.uuid4().hex, "name": name}
                create_album(DATA, album["id"], name, datetime.now(timezone.utc).isoformat())
                existing_albums[name.casefold()] = album; restored_albums += 1; created_album = True
            member_ids = [id_map[old_id] for old_id in source_album.get("photo_ids", []) if old_id in id_map]
            add_photos_to_album(DATA, album["id"], member_ids, datetime.now(timezone.utc).isoformat())
            restored_cover = id_map.get(source_album.get("cover_photo_id"))
            if created_album:
                update_album_presentation(DATA, album["id"], str(source_album.get("description") or "")[:500],
                                          restored_cover if restored_cover in member_ids else None)
    return {"imported_photos": imported, "duplicate_photos": duplicates,
            "restored_missing_objects": restored_objects, "created_albums": restored_albums,
            "mode": "merge", "deleted_existing": 0}


@app.patch("/api/photos/batch")
def batch(payload: BatchAction):
    ids = list(dict.fromkeys(payload.photo_ids))
    if not ids: raise HTTPException(422, "Select at least one photo")
    if payload.action == "add_album":
        if not payload.album_id: raise HTTPException(422, "album_id is required")
        try: add_photos_to_album(DATA, payload.album_id, ids, datetime.now(timezone.utc).isoformat())
        except KeyError: raise HTTPException(404, "Album not found")
    elif payload.action == "remove_album":
        if not payload.album_id: raise HTTPException(422, "album_id is required")
        remove_photos_from_album(DATA, payload.album_id, ids)
    elif payload.action in {"favorite", "trash", "restore"}:
        field, value = ("favorite", True) if payload.action == "favorite" else ("trashed", payload.action == "trash")
        for photo_id in ids: update_photo(photo_id, **{field: value})
    elif payload.action == "set_captured_at":
        captured_at = normalized_capture_time(payload.captured_at)
        for photo_id in ids: update_photo(photo_id, captured_at=captured_at)
    else: raise HTTPException(422, "Unsupported batch action")
    return {"updated": len(ids), "action": payload.action}


@app.get("/api/stats")
def stats():
    items = records()
    original_bytes = sum(item["size"] for item in items)
    thumbnail_sizes = STORAGE.list_sizes("thumbnails")
    thumbnail_bytes = sum(thumbnail_sizes.get(thumbnail_key(item["thumbnail_name"]), 0) for item in items
                          if item.get("thumbnail_name"))
    return {"photos": len(items), "albums": len(list_albums(DATA)), "original_bytes": original_bytes,
            "thumbnail_bytes": thumbnail_bytes,
            "bandwidth_saved_percent": round((1 - thumbnail_bytes / original_bytes) * 100, 1) if original_bytes else 0,
            **api_metrics(DATA)}


@app.post("/api/duplicates/scan")
def scan_near_duplicates(max_distance: int = 8):
    if max_distance < 1 or max_distance > 16:
        raise HTTPException(422, "Similarity distance must be between 1 and 16")
    items = [item for item in records() if not item.get("trashed")]
    usable: list[dict] = []
    for item in items:
        fingerprint = item.get("perceptual_hash")
        if not fingerprint:
            try:
                with STORAGE.local_file(original_key(item["object_name"])) as source:
                    fingerprint = image_difference_hash(source)
                update_fields(DATA, item["id"], {"perceptual_hash": fingerprint})
            except Exception:
                continue
        usable.append({**item, "perceptual_hash": fingerprint})

    parent = list(range(len(usable)))
    def root(index: int):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index
    def join(left: int, right: int):
        left_root, right_root = root(left), root(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left in range(len(usable)):
        for right in range(left + 1, len(usable)):
            if hamming_distance(usable[left]["perceptual_hash"], usable[right]["perceptual_hash"]) <= max_distance:
                join(left, right)

    clusters: dict[int, list[dict]] = {}
    for index, item in enumerate(usable):
        clusters.setdefault(root(index), []).append(item)
    groups = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        members.sort(key=lambda item: item["size"], reverse=True)
        largest_distance = max(hamming_distance(left["perceptual_hash"], right["perceptual_hash"])
                               for position, left in enumerate(members) for right in members[position + 1:])
        groups.append({"id": members[0]["id"], "similarity_percent": round((64 - largest_distance) / 64 * 100),
                       "potential_savings": sum(item["size"] for item in members[1:]),
                       "photos": [{key: item.get(key) for key in ("id", "name", "size", "width", "height", "captured_at")}
                                  for item in members]})
    groups.sort(key=lambda group: group["potential_savings"], reverse=True)
    return {"scanned_photos": len(usable), "group_count": len(groups),
            "potential_savings": sum(group["potential_savings"] for group in groups), "groups": groups,
            "policy": "Review only; no photo was changed or deleted"}


@app.post("/api/duplicates/cleanup")
def cleanup_near_duplicates(payload: DuplicateCleanup):
    trash_ids = list(dict.fromkeys(payload.trash_ids))
    if not trash_ids:
        raise HTTPException(422, "Choose at least one alternate copy")
    if payload.keep_id in trash_ids:
        raise HTTPException(422, "The retained photo cannot also be moved to trash")
    keep = get_photo(DATA, payload.keep_id)
    candidates = [get_photo(DATA, photo_id) for photo_id in trash_ids]
    if not keep or keep.get("trashed") or any(not item or item.get("trashed") for item in candidates):
        raise HTTPException(404, "One or more visible photos were not found")
    try:
        moved = set_photos_trashed(DATA, trash_ids, True)
    except KeyError:
        raise HTTPException(404, "One or more photos were not found")
    return {"kept_photo_id": payload.keep_id, "moved_to_trash": moved,
            "recoverable_bytes": sum(item["size"] for item in candidates if item),
            "permanently_deleted": 0, "affected_all_albums": True}


@app.get("/api/events")
def events(limit: int = 20):
    return {"items": recent_api_events(DATA, min(max(limit, 1), 50))}


def scan_storage_integrity(job_id: str | None = None):
    started = time.perf_counter()
    items = records()
    issues: list[dict] = []
    verified_hashes = 0
    missing_thumbnails = 0
    referenced_objects = {original_key(item["object_name"]) for item in items}

    if job_id:
        update_integrity_job(DATA, job_id, datetime.now(timezone.utc).isoformat(),
                             status="running", total=len(items), completed=0, current_name=None)
    for index, item in enumerate(items, 1):
        if job_id:
            update_integrity_job(DATA, job_id, datetime.now(timezone.utc).isoformat(),
                                 total=len(items), completed=index - 1, current_name=item["name"])
        key = original_key(item["object_name"])
        if not STORAGE.exists(key):
            issues.append({"photo_id": item["id"], "name": item["name"], "kind": "missing_original"})
            if job_id:
                update_integrity_job(DATA, job_id, datetime.now(timezone.utc).isoformat(), completed=index)
            continue
        digest = hashlib.sha256()
        with STORAGE.local_file(key) as source:
            with source.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
        if digest.hexdigest() != item["sha256"]:
            issues.append({"photo_id": item["id"], "name": item["name"], "kind": "hash_mismatch"})
        else:
            verified_hashes += 1
        thumb_name = item.get("thumbnail_name")
        if not thumb_name or not STORAGE.exists(thumbnail_key(thumb_name)):
            missing_thumbnails += 1
            issues.append({"photo_id": item["id"], "name": item["name"], "kind": "missing_thumbnail"})
        if job_id:
            update_integrity_job(DATA, job_id, datetime.now(timezone.utc).isoformat(), completed=index)

    orphan_objects = sorted(key.removeprefix("objects/") for key in STORAGE.list("objects")
                            if key not in referenced_objects)
    issues.extend({"photo_id": None, "name": name, "kind": "orphan_object"}
                  for name in orphan_objects)
    blocking_issues = sum(issue["kind"] in {"missing_original", "hash_mismatch"} for issue in issues)
    return {
        "status": "healthy" if blocking_issues == 0 else "degraded",
        "checked_photos": len(items),
        "verified_hashes": verified_hashes,
        "missing_thumbnails": missing_thumbnails,
        "orphan_objects": len(orphan_objects),
        "blocking_issues": blocking_issues,
        "issues": issues[:100],
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
    }


def run_integrity_job(job_id: str):
    try:
        report = scan_storage_integrity(job_id)
        update_integrity_job(DATA, job_id, datetime.now(timezone.utc).isoformat(), status="completed",
                             completed=report["checked_photos"], current_name=None,
                             result_json=json.dumps(report, ensure_ascii=False))
    except Exception as error:
        update_integrity_job(DATA, job_id, datetime.now(timezone.utc).isoformat(), status="failed",
                             current_name=None, error=str(error)[:500])


@app.post("/api/integrity/jobs")
def start_integrity_job(background_tasks: BackgroundTasks):
    now = datetime.now(timezone.utc).isoformat()
    job, created = create_integrity_job(DATA, uuid.uuid4().hex, now)
    if created:
        background_tasks.add_task(run_integrity_job, job["id"])
    return {**job, "result": None, "reused": not created}


@app.get("/api/integrity/jobs/latest")
def latest_integrity_job():
    return get_integrity_job(DATA) or {"status": "idle"}


@app.get("/api/integrity/jobs/{job_id}")
def integrity_job(job_id: str):
    job = get_integrity_job(DATA, job_id)
    if not job:
        raise HTTPException(404, "Integrity job not found")
    return job


@app.post("/api/integrity/repair")
def repair_storage_integrity():
    before = scan_storage_integrity()
    by_id = {item["id"]: item for item in records()}
    regenerated_thumbnails = 0
    quarantined_objects = 0
    quarantine = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    for issue in before["issues"]:
        if issue["kind"] == "missing_thumbnail" and issue["photo_id"] in by_id:
            item = enrich_image(dict(by_id[issue["photo_id"]]))
            if item.get("thumbnail_name"):
                update_photo(item["id"], thumbnail_name=item["thumbnail_name"], width=item.get("width"),
                             height=item.get("height"), captured_at=item.get("captured_at"))
                regenerated_thumbnails += 1
        elif issue["kind"] == "orphan_object":
            source_key = original_key(issue["name"])
            if STORAGE.exists(source_key):
                STORAGE.move(source_key, f"quarantine/{quarantine}/{issue['name']}")
                quarantined_objects += 1

    after = scan_storage_integrity()
    return {
        "regenerated_thumbnails": regenerated_thumbnails,
        "quarantined_objects": quarantined_objects,
        "unresolved_blocking_issues": after["blocking_issues"],
        "report": after,
        "recovery_policy": "Orphan objects were quarantined, never deleted",
    }

def update_photo(photo_id: str, **changes):
    try:
        update_fields(DATA, photo_id, changes)
    except KeyError:
        raise HTTPException(404, "Photo not found")
    return get_photo(DATA, photo_id)


@app.patch("/api/photos/{photo_id}/metadata")
def photo_metadata(photo_id: str, payload: PhotoMetadata):
    caption = payload.caption.strip()[:500]
    tags = list(dict.fromkeys(tag.strip().lower()[:30] for tag in payload.tags if tag.strip()))[:12]
    try: set_photo_metadata(DATA, photo_id, caption, tags)
    except KeyError: raise HTTPException(404, "Photo not found")
    if "captured_at" in payload.model_fields_set:
        update_photo(photo_id, captured_at=normalized_capture_time(payload.captured_at))
    return get_photo(DATA, photo_id)

@app.patch("/api/photos/{photo_id}/favorite")
def favorite(photo_id: str):
    item = next((x for x in records() if x["id"] == photo_id), None)
    if not item: raise HTTPException(404, "Photo not found")
    return update_photo(photo_id, favorite=not item.get("favorite", False))

@app.patch("/api/photos/{photo_id}/trash")
def trash(photo_id: str): return update_photo(photo_id, trashed=True)

@app.patch("/api/photos/{photo_id}/restore")
def restore(photo_id: str): return update_photo(photo_id, trashed=False)

@app.post("/api/photos/{photo_id}/share")
def share(photo_id: str, expires_hours: int = 168):
    if expires_hours < 1 or expires_hours > 24 * 365:
        raise HTTPException(422, "Share duration must be between 1 hour and 1 year")
    token = uuid.uuid4().hex[:12]
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=expires_hours)).isoformat()
    return {"token": token, "url": f"/share/{token}", "expires_at": expires_at,
            "photo": update_photo(photo_id, share_token=token, share_expires_at=expires_at, share_views=0)}

@app.delete("/api/photos/{photo_id}/share")
def revoke_share(photo_id: str): return update_photo(photo_id, share_token=None, share_expires_at=None)

@app.get("/api/share/{token}")
def shared_photo(token: str):
    item = next((x for x in records() if x.get("share_token") == token and not x.get("trashed")), None)
    if not item: raise HTTPException(404, "Share link not found")
    if item.get("share_expires_at") and item["share_expires_at"] <= datetime.now(timezone.utc).isoformat():
        raise HTTPException(410, "Share link expired")
    return item

@app.get("/api/share/{token}/content")
def shared_content(token: str):
    item = shared_photo(token)
    increment_share_views(DATA, item["id"])
    return media_response(original_key(item["object_name"]), item["content_type"])

@app.delete("/api/photos/{photo_id}")
def permanent_delete(photo_id: str):
    item = next((x for x in records() if x["id"] == photo_id), None)
    if not item or not item.get("trashed"): raise HTTPException(409, "Photo must be in trash")
    delete_photo(DATA, photo_id)
    if not any(x["object_name"] == item["object_name"] and x["id"] != photo_id for x in records()):
        STORAGE.delete(original_key(item["object_name"]))
        if item.get("thumbnail_name"):
            STORAGE.delete(thumbnail_key(item["thumbnail_name"]))
    return {"deleted": True}


@app.get("/api/photos/{photo_id}/content")
def content(photo_id: str):
    item = next((x for x in records() if x["id"] == photo_id), None)
    if not item:
        raise HTTPException(404, "Photo not found")
    return media_response(original_key(item["object_name"]), item["content_type"])

@app.get("/api/photos/{photo_id}/thumbnail")
def thumbnail(photo_id: str):
    item = next((x for x in records() if x["id"] == photo_id), None)
    if not item: raise HTTPException(404, "Photo not found")
    if not item.get("thumbnail_name") or not STORAGE.exists(thumbnail_key(item["thumbnail_name"])):
        item = enrich_image(item)
        item = update_photo(photo_id, thumbnail_name=item.get("thumbnail_name"), width=item.get("width"), height=item.get("height"), captured_at=item.get("captured_at"))
    if item.get("thumbnail_name"):
        return media_response(thumbnail_key(item["thumbnail_name"]), "image/webp")
    return media_response(original_key(item["object_name"]), item["content_type"])


@app.post("/api/uploads/init")
def init_upload(filename: str, sha256: str, size: int, content_type: str = "image/jpeg"):
    existing = next((x for x in records() if x["sha256"] == sha256), None)
    if existing:
        return {"instant": True, "photo": existing}
    session = get_upload_by_hash(DATA, sha256)
    if session and (CHUNKS / session["id"]).exists():
        uploaded = [int(part.stem) for part in (CHUNKS / session["id"]).glob("*.part")]
        return {"instant": False, "resumed": True, "upload_id": session["id"],
                "chunk_size": 1024 * 1024, "uploaded_chunks": uploaded}
    upload_id = uuid.uuid4().hex
    (CHUNKS / upload_id).mkdir()
    create_upload(DATA, {"id": upload_id, "filename": filename, "sha256": sha256, "size": size,
                         "content_type": content_type, "created_at": datetime.now(timezone.utc).isoformat()})
    return {"instant": False, "resumed": False, "upload_id": upload_id,
            "chunk_size": 1024 * 1024, "uploaded_chunks": []}


@app.get("/api/uploads/{upload_id}")
def upload_status(upload_id: str):
    folder = CHUNKS / upload_id
    if not folder.exists(): raise HTTPException(404, "Upload session not found")
    chunks = sorted(int(part.stem) for part in folder.glob("*.part"))
    return {"upload_id": upload_id, "uploaded_chunks": chunks}


@app.delete("/api/uploads/{upload_id}")
def cancel_upload(upload_id: str):
    folder = CHUNKS / upload_id
    if folder.exists(): shutil.rmtree(folder)
    delete_upload(DATA, upload_id)
    return {"cancelled": True}


@app.put("/api/uploads/{upload_id}/chunks/{index}")
async def upload_chunk(upload_id: str, index: int, chunk: UploadFile = File(...)):
    folder = CHUNKS / upload_id
    if not folder.exists():
        raise HTTPException(404, "Upload session not found")
    target = folder / f"{index:08d}.part"
    with target.open("wb") as out:
        shutil.copyfileobj(chunk.file, out)
    return {"index": index, "bytes": target.stat().st_size}


@app.post("/api/uploads/{upload_id}/complete")
def complete(upload_id: str, background_tasks: BackgroundTasks, filename: str = Form(...), sha256: str = Form(...), content_type: str = Form(...)):
    folder = CHUNKS / upload_id
    parts = sorted(folder.glob("*.part")) if folder.exists() else []
    if not parts:
        raise HTTPException(400, "No chunks uploaded")
    object_name = f"{sha256}{Path(filename).suffix.lower()}"
    temporary = tempfile.NamedTemporaryFile(prefix="pixelvault-upload-", dir=DATA, delete=False)
    target = Path(temporary.name)
    temporary.close()
    digest = hashlib.sha256()
    with target.open("wb") as out:
        for part in parts:
            data = part.read_bytes()
            digest.update(data)
            out.write(data)
    if digest.hexdigest() != sha256:
        target.unlink(missing_ok=True)
        raise HTTPException(422, "SHA-256 mismatch")
    item = {"id": uuid.uuid4().hex, "name": filename, "sha256": sha256, "object_name": object_name,
            "content_type": content_type, "size": target.stat().st_size, "favorite": False,
            "trashed": False, "share_token": None, "thumbnail_name": None, "width": None,
            "height": None, "captured_at": None, "share_expires_at": None, "share_views": 0,
            "caption": ""}
    key = original_key(object_name)
    existed = STORAGE.exists(key)
    try:
        STORAGE.put_file(key, target, content_type)
        items = records(); items.insert(0, item); save(items)
    except Exception:
        if not existed:
            STORAGE.delete(key)
        raise
    finally:
        target.unlink(missing_ok=True)
    job, created = queue_photo_processing(DATA, item["id"], datetime.now(timezone.utc).isoformat())
    if created:
        background_tasks.add_task(run_photo_processing, item["id"])
    shutil.rmtree(folder)
    delete_upload(DATA, upload_id)
    return {**item, "processing_status": job["status"]}


# Production serves the compiled React application from the same origin.
# API routes are registered first, so this fallback cannot shadow them.
STATIC_DIR = Path(os.getenv("PIXELVAULT_STATIC_DIR", "")).resolve() if os.getenv("PIXELVAULT_STATIC_DIR") else None
if STATIC_DIR and (STATIC_DIR / "index.html").is_file():
    assets_dir = STATIC_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def frontend_app(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404, "API route not found")
        requested = (STATIC_DIR / full_path).resolve()
        if requested != STATIC_DIR and STATIC_DIR in requested.parents and requested.is_file():
            return FileResponse(requested)
        return FileResponse(STATIC_DIR / "index.html")
