import json
import io
import os
import time
import zipfile
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

BASE = os.getenv("PIXELVAULT_TEST_BASE", "http://127.0.0.1:8000/api")
TEST_PASSWORD = os.getenv("PIXELVAULT_TEST_PASSWORD", "demo1234")
opener = build_opener(HTTPCookieProcessor(CookieJar()))

def call(path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    with opener.open(Request(BASE + path, method=method, data=data,
                             headers={"Content-Type": "application/json"} if data else {})) as response:
        return json.load(response)

def fetch(path):
    with opener.open(BASE + path) as response:
        return response.headers.get_content_type(), response.read()

def fetch_binary(path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = Request(BASE + path, method=method, data=data,
                      headers={"Content-Type": "application/json"} if data else {})
    with opener.open(request) as response:
        return response.headers.get_content_type(), response.read()

def anonymous_call(path):
    with urlopen(BASE + path) as response:
        return json.load(response)

def anonymous_fetch(path):
    with urlopen(BASE + path) as response:
        return response.headers.get_content_type(), response.read()

def import_backup(payload):
    boundary = "pixelvault-smoke-boundary"
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"backup\"; filename=\"backup.zip\"\r\n"
            "Content-Type: application/zip\r\n\r\n").encode() + payload + f"\r\n--{boundary}--\r\n".encode()
    request = Request(BASE + "/backups/import", method="POST", data=body,
                      headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with opener.open(request) as response:
        return json.load(response)

def editable_capture(value):
    if not value:
        return None
    if len(value) >= 16 and value[4] == ":":
        return value[:10].replace(":", "-") + "T" + value[11:16]
    return value

assert call("/health")["status"] == "ok"
try:
    call("/photos")
    raise AssertionError("Protected endpoint accepted an anonymous request")
except HTTPError as error:
    assert error.code == 401
try:
    call("/auth/login", "POST", {"password": "wrong-password"})
    raise AssertionError("Invalid password was accepted")
except HTTPError as error:
    assert error.code == 401
assert call("/auth/login", "POST", {"password": TEST_PASSWORD})["authenticated"] is True
assert call("/auth/me")["authenticated"] is True
security = call("/security")
assert security["active_sessions"] >= 1
assert security["failure_limit"] == 5 and security["failure_window_minutes"] == 5
library = call("/photos")
photos = library["items"]
assert library["total"] == len(photos)
size_sorted = call("/photos?sort=size_desc")["items"]
assert [photo["size"] for photo in size_sorted] == sorted((photo["size"] for photo in size_sorted), reverse=True)
landscape = call("/photos?orientation=landscape")["items"]
assert all(photo.get("width") and photo.get("height") and photo["width"] > photo["height"] for photo in landscape)
captured_photo = next((photo for photo in photos if photo.get("captured_at")), None)
if captured_photo:
    capture_date = captured_photo["captured_at"][:10].replace(":", "-")
    dated = call(f"/photos?date_from={capture_date}&date_to={capture_date}")["items"]
    assert any(photo["id"] == captured_photo["id"] for photo in dated)
if len(photos) > 1:
    largest_first = call("/photos?limit=1&sort=size_desc")
    largest_second = call(f"/photos?limit=1&sort=size_desc&cursor={largest_first['next_cursor']}")
    assert largest_first["items"][0]["id"] != largest_second["items"][0]["id"]
    assert largest_first["items"][0]["size"] >= largest_second["items"][0]["size"]
try:
    call("/photos?orientation=diagonal")
    raise AssertionError("Invalid orientation filter was accepted")
except HTTPError as error:
    assert error.code == 422
before_duplicate_ids = {photo["id"] for photo in photos}
duplicate_report = call("/duplicates/scan", "POST")
assert duplicate_report["scanned_photos"] == len(photos)
assert duplicate_report["group_count"] == len(duplicate_report["groups"])
assert duplicate_report["potential_savings"] >= 0
assert "no photo" in duplicate_report["policy"].lower()
assert {photo["id"] for photo in call("/photos")["items"]} == before_duplicate_ids
if len(photos) >= 2:
    keep_id, alternate_id = photos[0]["id"], photos[1]["id"]
    cleanup = call("/duplicates/cleanup", "POST", {"keep_id": keep_id, "trash_ids": [alternate_id]})
    assert cleanup["moved_to_trash"] == 1 and cleanup["permanently_deleted"] == 0
    assert cleanup["affected_all_albums"] is True and cleanup["recoverable_bytes"] == photos[1]["size"]
    assert any(photo["id"] == alternate_id for photo in call("/photos?view=trash")["items"])
    media_type, recoverable_original = fetch(f"/photos/{alternate_id}/content")
    assert media_type.startswith("image/") and recoverable_original
    assert call(f"/photos/{alternate_id}/restore", "PATCH")["trashed"] is False
    assert {photo["id"] for photo in call("/photos")["items"]} == before_duplicate_ids
job = call("/integrity/jobs", "POST")
assert job["status"] in {"queued", "running"} and job["id"]
for _ in range(100):
    job = call(f"/integrity/jobs/{job['id']}")
    if job["status"] in {"completed", "failed"}:
        break
    time.sleep(0.05)
assert job["status"] == "completed", job.get("error")
assert call("/integrity/jobs/latest")["id"] == job["id"]
integrity = job["result"]
assert integrity["checked_photos"] >= len(photos)
assert integrity["verified_hashes"] == integrity["checked_photos"]
assert integrity["blocking_issues"] == 0 and integrity["status"] == "healthy"
assert integrity["duration_ms"] >= 0 and isinstance(integrity["issues"], list)
orphan_fixture = Path("data/objects/smoke-orphan.bin")
orphan_fixture.write_bytes(b"recoverable orphan fixture")
try:
    repair = call("/integrity/repair", "POST")
    assert repair["quarantined_objects"] >= 1
    assert repair["report"]["orphan_objects"] == 0
    assert repair["recovery_policy"] == "Orphan objects were quarantined, never deleted"
finally:
    orphan_fixture.unlink(missing_ok=True)
    for quarantined in Path("data/quarantine").glob("*/smoke-orphan.bin"):
        quarantined.unlink(missing_ok=True)
if len(photos) > 1:
    first_page = call("/photos?limit=1")
    second_page = call(f"/photos?limit=1&cursor={first_page['next_cursor']}")
    assert first_page["items"][0]["id"] != second_page["items"][0]["id"]
    assert first_page["total"] == second_page["total"] == library["total"]
timeline = call("/timeline")["items"]
assert sum(group["photo_count"] for group in timeline) == len(photos)
if timeline:
    month_items = call(f"/photos?month={timeline[0]['month']}")["items"]
    assert len(month_items) == timeline[0]["photo_count"] and timeline[0]["cover_photo_id"]
albums = call("/albums")["items"]
if photos and not albums:
    album = call("/albums", "POST", {"name": "Portfolio Demo"})
    call("/photos/batch", "PATCH", {"photo_ids": [x["id"] for x in photos], "action": "add_album", "album_id": album["id"]})
    album_page = call(f"/photos?album_id={album['id']}")
    assert len(album_page["items"]) == len(photos) and album_page["total"] == len(photos)
    albums = call("/albums")["items"]
if albums:
    album = albums[0]
    temporary_name = album["name"] + " - rename check"
    assert call(f"/albums/{album['id']}", "PATCH", {"name": temporary_name})["name"] == temporary_name
    assert call(f"/albums/{album['id']}", "PATCH", {"name": album["name"]})["name"] == album["name"]
    album_members = call(f"/photos?album_id={album['id']}")["items"]
    if album_members:
        cover_id = album_members[0]["id"]
        presentation = call(f"/albums/{album['id']}/presentation", "PATCH",
                            {"description": "Portfolio-ready shared collection", "cover_photo_id": cover_id})
        assert presentation["description"] == "Portfolio-ready shared collection"
        assert presentation["cover_photo_id"] == cover_id
        try:
            call(f"/albums/{album['id']}/presentation", "PATCH",
                 {"description": presentation["description"], "cover_photo_id": "not-a-member"})
            raise AssertionError("Album accepted a non-member cover")
        except HTTPError as error:
            assert error.code == 422
    shared_album = call(f"/albums/{album['id']}/share?expires_hours=24", "POST")
    public_album = anonymous_call(f"/share/albums/{shared_album['token']}")
    assert public_album["id"] == album["id"] and public_album["photo_count"] == album["photo_count"]
    if album_members:
        assert public_album["description"] == "Portfolio-ready shared collection"
        assert public_album["cover_photo_id"] == cover_id
    if public_album["photos"]:
        public_photo_id = public_album["photos"][0]["id"]
        media_type, public_thumb = anonymous_fetch(f"/share/albums/{shared_album['token']}/photos/{public_photo_id}/thumbnail")
        assert media_type.startswith("image/") and public_thumb
    try:
        anonymous_fetch(f"/share/albums/{shared_album['token']}/photos/not-a-member/thumbnail")
        raise AssertionError("Shared album exposed a non-member photo")
    except HTTPError as error:
        assert error.code == 404
    assert call(f"/albums/{album['id']}/share", "DELETE")["revoked"] is True
    if album_members:
        call(f"/albums/{album['id']}/presentation", "PATCH",
             {"description": album.get("description") or "", "cover_photo_id": album.get("cover_photo_id")})
        removable_id = album_members[0]["id"]
        removal = call(f"/albums/{album['id']}/photos/{removable_id}", "DELETE")
        assert removal["removed"] is True and removal["photo_deleted"] is False
        assert all(item["id"] != removable_id for item in call(f"/photos?album_id={album['id']}")["items"])
        assert any(item["id"] == removable_id for item in call("/photos")["items"])
        call("/photos/batch", "PATCH", {"photo_ids": [removable_id], "action": "add_album", "album_id": album["id"]})
    try:
        anonymous_call(f"/share/albums/{shared_album['token']}")
        raise AssertionError("Revoked album link remained public")
    except HTTPError as error:
        assert error.code == 404
stats = call("/stats")
assert stats["photos"] >= len(photos) and 0 <= stats["bandwidth_saved_percent"] <= 100
assert stats["request_count"] >= 1 and stats["average_ms"] >= 0
backup_type, backup_bytes = fetch_binary("/backups/export")
assert backup_type == "application/zip" and backup_bytes.startswith(b"PK")
with zipfile.ZipFile(io.BytesIO(backup_bytes)) as backup_archive:
    backup_manifest = json.loads(backup_archive.read("backup.json"))
    assert backup_manifest["format"] == "pixelvault-backup" and backup_manifest["version"] == 1
    assert len(backup_manifest["photos"]) == stats["photos"]
    assert all(item["archive_path"] in backup_archive.namelist() for item in backup_manifest["photos"])
merge_result = import_backup(backup_bytes)
assert merge_result["imported_photos"] == 0
assert merge_result["duplicate_photos"] == stats["photos"] and merge_result["deleted_existing"] == 0
resume_hash = "a" * 64
resume_path = f"/uploads/init?filename=resume-test.jpg&sha256={resume_hash}&size=2097152&content_type=image/jpeg"
session = call(resume_path, "POST")
resumed = call(resume_path, "POST")
assert resumed["upload_id"] == session["upload_id"] and resumed["resumed"] is True
assert call(f"/uploads/{session['upload_id']}")["uploaded_chunks"] == []
assert call(f"/uploads/{session['upload_id']}", "DELETE")["cancelled"] is True
if photos:
    photo_id = photos[0]["id"]
    original_caption, original_tags, original_capture = photos[0].get("caption") or "", photos[0].get("tags") or [], photos[0].get("captured_at")
    metadata = call(f"/photos/{photo_id}/metadata", "PATCH", {"caption": "Searchable portfolio caption", "tags": ["portfolio-tag", "Demo"], "captured_at": "2024-05-06T14:30"})
    assert metadata["caption"] == "Searchable portfolio caption" and "portfolio-tag" in metadata["tags"]
    assert metadata["captured_at"] == "2024:05:06 14:30:00"
    assert any(x["id"] == photo_id for x in call("/photos?month=2024-05")["items"])
    search_page = call("/photos?search=portfolio-tag")
    assert any(x["id"] == photo_id for x in search_page["items"]) and search_page["total"] >= 1
    call(f"/photos/{photo_id}/metadata", "PATCH", {"caption": original_caption, "tags": original_tags,
                                                     "captured_at": editable_capture(original_capture)})
    batch_ids = [item["id"] for item in photos[:2]]
    original_batch = {item["id"]: item for item in photos[:2]}
    call("/photos/batch", "PATCH", {"photo_ids": batch_ids, "action": "set_captured_at", "captured_at": "2023-08-09T09:15"})
    assert call("/photos?month=2023-08")["total"] >= len(batch_ids)
    for batch_id, original in original_batch.items():
        call(f"/photos/{batch_id}/metadata", "PATCH", {"caption": original.get("caption") or "",
             "tags": original.get("tags") or [], "captured_at": editable_capture(original.get("captured_at"))})
    archive_type, archive_bytes = fetch_binary("/photos/export", "POST", {"photo_ids": [photo_id]})
    assert archive_type == "application/zip" and archive_bytes.startswith(b"PK")
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["photo_count"] == 1 and any(name.startswith("photos/") for name in archive.namelist())
    media_type, thumbnail = fetch(f"/photos/{photo_id}/thumbnail")
    assert media_type in {"image/webp", "image/jpeg", "image/png"} and len(thumbnail) > 0
    metadata = next(x for x in call("/photos")["items"] if x["id"] == photo_id)
    assert metadata.get("width") and metadata.get("height")
    assert metadata.get("processing_status") in {"ready", None}
    thumbnail_path = Path("data/thumbnails") / metadata["thumbnail_name"]
    previous_thumbnail = thumbnail_path.read_bytes()
    thumbnail_path.unlink()
    processing = call(f"/photos/{photo_id}/processing/retry", "POST")
    assert processing["status"] in {"queued", "running"}
    for _ in range(100):
        processing = call(f"/photos/{photo_id}/processing")
        if processing["status"] in {"ready", "failed"}:
            break
        time.sleep(0.05)
    if processing["status"] != "ready":
        thumbnail_path.write_bytes(previous_thumbnail)
    assert processing["status"] == "ready", processing.get("error")
    assert thumbnail_path.is_file() and thumbnail_path.stat().st_size > 0
    original_favorite = bool(photos[0]["favorite"])
    changed = bool(call(f"/photos/{photo_id}/favorite", "PATCH")["favorite"])
    assert changed is not original_favorite
    assert any(x["id"] == photo_id for x in call("/photos?view=favorites")["items"]) is changed
    call(f"/photos/{photo_id}/favorite", "PATCH")
    share_result = call(f"/photos/{photo_id}/share?expires_hours=24", "POST")
    token = share_result["token"]
    assert share_result["expires_at"] and call(f"/share/{token}")["id"] == photo_id
    media_type, shared_bytes = fetch(f"/share/{token}/content")
    assert media_type.startswith("image/") and shared_bytes
    assert any(x["id"] == photo_id for x in call("/photos?view=shared")["items"])
    shared_item = next(x for x in call("/photos?view=shared")["items"] if x["id"] == photo_id)
    assert shared_item["share_views"] >= 1 and shared_item["share_expires_at"]
    assert call(f"/photos/{photo_id}/trash", "PATCH")["trashed"] is True
    assert any(x["id"] == photo_id for x in call("/photos?view=trash")["items"])
    assert call(f"/photos/{photo_id}/restore", "PATCH")["trashed"] is False
events = call("/events")["items"]
assert events and all(event["method"] != "GET" for event in events)
assert call("/auth/logout", "POST")["authenticated"] is False
if photos:
    assert call(f"/share/{token}")["id"] == photo_id
try:
    call("/photos")
    raise AssertionError("Logged-out session remained valid")
except HTTPError as error:
    assert error.code == 401
assert call("/auth/login", "POST", {"password": TEST_PASSWORD})["authenticated"] is True
assert call("/security/revoke-all", "POST")["revoked"] is True
try:
    call("/photos")
    raise AssertionError("Revoked session remained valid")
except HTTPError as error:
    assert error.code == 401
print(f"PixelVault API smoke test passed ({len(photos)} photo records, auth enforced).")
