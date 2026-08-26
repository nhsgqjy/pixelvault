# AI-assisted development log

## Decision 001 - Vertical slice before infrastructure breadth

- Requirement: deliver a credible full-stack MVP in 2-3 days.
- AI proposal: PostgreSQL, Redis, Celery, MinIO, authentication, sharing, EXIF, and video processing in the first pass.
- Human decision: reject the all-at-once approach. Build upload-to-gallery first, with stable adapters for later infrastructure.
- Verification: the first slice must upload a real image in chunks, verify SHA-256, persist metadata, and display it in the gallery.

## Decision 002 - Upload idempotency

- Risk: retries can write the same chunk multiple times.
- Implementation: deterministic chunk filenames overwrite safely; completion validates the full-file SHA-256 before publishing metadata.
- Next hardening step: database-backed upload sessions, unique constraints, object reference counting, and concurrent-completion tests.

## Decision 003 - Functional navigation before adding pages

- Problem: the first visual slice contained navigation controls that did not yet perform actions.
- Decision: implement search, favorites, share state, trash, and restore against real API state before adding more decorative pages.
- Verification: `backend/smoke_test.py` exercises every state transition and confirms each filtered collection reflects the change.

## Decision 004 - Replace JSON metadata without breaking the demo

- Problem: a flat JSON index is easy to demo but cannot provide uniqueness guarantees or indexed state queries.
- Decision: migrate existing records into SQLite on startup, enforce unique content hashes and share tokens, and keep storage behind repository functions so PostgreSQL can replace it later.
- Verification: startup migration preserved the existing photo; smoke tests cover favorite, share lookup, trash, and restore transitions.

## Decision 005 - Optimize gallery bandwidth and remove a concurrent-write race

- Problem: loading multi-megabyte originals in every gallery card wastes bandwidth and memory. During verification, two simultaneous first-time thumbnail requests also exposed a lost-update race in the original whole-table save routine.
- Decision: generate orientation-corrected 640 px WebP thumbnails, persist dimensions and EXIF capture time, and update only the affected SQLite row and fields in one transaction.
- Evidence: the two existing 5.4-6.4 MB JPEGs now render from compact WebP derivatives; concurrent thumbnail requests no longer overwrite another photo's metadata.
- Verification: the smoke test checks that the thumbnail endpoint returns image bytes and that dimensions are persisted after lazy generation.

## Decision 006 - Make optimization visible and organization scalable

- Requirement: demonstrate frontend and backend breadth with concrete evidence, not decorative controls.
- Decision: add normalized albums and album-photo membership tables, multi-select batch commands, and a statistics endpoint that calculates storage traffic from actual files.
- Database reasoning: the compound primary key prevents duplicate album membership; `idx_album_photos_photo_id` supports reverse photo membership lookup without adding speculative indexes.
- Verification: the smoke test creates a real portfolio album, batch-adds both photos, confirms filtered album results, and validates the measured bandwidth-saving range.

## Decision 007 - Complete the album lifecycle without coupling it to file deletion

- Problem: create-and-view alone is not a credible album feature; users must be able to rename and reorganize it without risking original files.
- Decision: keep album membership as independent relationship data. Renaming updates only the album row, removing a photo deletes only the relationship, and deleting an album preserves every photo object and metadata record.
- UI evidence: album cards use a real member thumbnail as their cover and expose rename both on the card and inside the album.
- Verification: the smoke test renames an existing album, confirms the returned name, and restores the original name so repeated runs remain deterministic.

## Decision 008 - Turn chunking into a recoverable upload protocol

- Problem: splitting a file into chunks is not resumability if the server forgets the session or the client always sends every chunk again.
- Decision: persist upload sessions in SQLite with a unique content hash, return existing chunk indexes on re-initialization, upload three chunks concurrently, and retry a failed chunk up to three times with incremental backoff.
- User-facing evidence: each upload now displays state, percentage, measured throughput, and pause/resume controls. Duplicate files still complete instantly through SHA-256 deduplication.
- Verification: the smoke test initializes the same file twice, confirms the same durable session is resumed, reads its uploaded-chunk state, and cancels the isolated test session.

## Decision 009 - Protect private APIs with server-owned sessions

- Threat boundary: gallery metadata, originals, uploads, albums and statistics are private; tokenized share routes are intentionally public.
- Decision: use a local vault password only to create a random 256-bit server-side session. The browser receives an HttpOnly, SameSite cookie and never stores the password or session token in JavaScript storage.
- Network hardening: the development server now binds only to `127.0.0.1`; browser API traffic uses the same-origin Vite proxy instead of exposing a credentialed wildcard CORS policy.
- Verification: the smoke test confirms anonymous access returns 401, login unlocks protected endpoints, and logout invalidates the session while health and share routes remain public.

## Decision 010 - Make backend behavior measurable inside the product

- Problem: claims about performance and reliability are weak without runtime evidence, while unrestricted request logs grow forever and become operational debt.
- Decision: instrument API requests in middleware, retain a bounded 1000-event SQLite window, aggregate request count, errors and average latency, and expose only recent write operations in the audit trail.
- Query design: a descending timestamp index supports the actual recent-event query; no speculative per-path or status indexes were added.
- User-facing evidence: Insights now combines storage optimization metrics with API latency, error count and a timestamped operation trail.
- Verification: the regression test checks metric values and confirms the audit endpoint returns write events only.

## Decision 011 - Give public shares an explicit security lifecycle

- Problem: permanent bearer links have no time boundary, and a simple read-then-write view counter loses updates under concurrent access.
- Decision: each new share receives a configurable 1-hour to 1-year expiry, can still be revoked immediately, and returns HTTP 410 after expiry. Original-image delivery increments views with a single atomic SQLite update.
- Privacy boundary: share metadata and content remain the only anonymous photo routes; the owner-only Shared view reports expiry and access count behind the vault session.
- Verification: the regression test creates a 24-hour link, reads its public metadata and image, confirms the view count increases, then logs out and verifies the share still works while private photos return 401.

## Decision 012 - Normalize tags instead of storing comma-separated metadata

- Product need: people remember a subject or event more often than an original camera filename, so search must cover descriptions and reusable tags.
- Decision: store captions on photos and model tags through unique `tags` plus compound-key `photo_tags` membership. Tag replacement runs in one transaction and removes orphaned tags.
- Query design: the membership primary key supports per-photo detail reads; `idx_photo_tags_tag_id` supports reverse tag lookup without redundant indexes.
- User-facing evidence: the full-resolution detail panel edits descriptions and comma-separated tag input, renders saved tag chips, and the main search finds names, captions or tags.
- Verification: the regression test writes mixed-case tags and a caption, finds the photo by tag search, then restores its original metadata for deterministic reruns.

## Decision 013 - Keep user data portable with verifiable exports

- Product need: a personal photo vault must not trap originals or metadata inside its own database.
- Decision: allow authenticated exports for either a selected set or an entire album. Each ZIP contains original bytes plus a UTF-8 manifest with hashes, dimensions, capture time, descriptions and tags.
- Safety details: archive paths use basename-only sanitized names, duplicates receive deterministic numeric prefixes, trashed or missing IDs are rejected, and temporary ZIP files are deleted after the response finishes.
- Verification: the regression test downloads a protected export, checks its ZIP signature, opens it in memory, validates the manifest count and confirms an original exists under `photos/`.

## Decision 014 - Derive a timeline from source metadata

- Product need: a personal library should surface memories chronologically without forcing users to build every album manually.
- Decision: derive month groups from orientation-corrected EXIF capture timestamps, select a real photo as each cover, exclude trash, and keep missing timestamps in an explicit `Unknown date` group.
- API shape: the timeline endpoint returns lightweight group summaries, while the existing paginated photo endpoint accepts a month filter and continues to support search within that month.
- User-facing evidence: the Timeline navigation shows photographic month cards and drills into the normal selectable gallery, preserving download, favorite, sharing and batch actions.
- Verification: the regression test confirms group counts equal the live library and that month filtering returns exactly the selected group's count.

## Decision 015 - Bound gallery payloads without breaking continuous browsing

- Scale risk: fetching every photo record and thumbnail at once makes the first render degrade linearly as a personal library grows.
- Decision: request 24 records per page through the existing cursor contract, replace results when filters change, and append only when the user asks for the next page.
- Interaction design: the detail viewer navigates the currently loaded result set with buttons or arrow keys, closes with Escape, and offers a 3.5-second slideshow that cleans up its timer on pause or close.
- Verification: the regression test requests consecutive one-item pages and asserts they contain different photo IDs; the production TypeScript build validates slideshow and pagination state transitions.

## Decision 016 - Preserve complete navigation when desktop chrome disappears

- Problem: the desktop sidebar was hidden below 760 px, which made secondary views unreachable on phones even though the gallery itself was responsive.
- Decision: add a fixed, translucent six-action mobile bar for Photos, Timeline, Favorites, Albums, Insights and Lock, while preserving the full desktop sidebar.
- Accessibility work: active routes expose `aria-current`, icon-only photo actions have contextual labels, album and photo cards support Enter activation, and all controls receive a consistent visible focus ring.
- Touch behavior: primary targets are at least 36-52 px, toolbars wrap instead of overflowing, toast messages remain visible above the viewport, and page padding reserves space for the fixed navigation.
- Verification: the production TypeScript build passes alongside the full authenticated API regression suite.

## Decision 017 - Persist authentication defenses across requests

- Threat: an in-memory password retry counter resets on restart and cannot support trustworthy security reporting.
- Decision: persist failed attempts by client and timestamp in SQLite, enforce five attempts per five minutes with `Retry-After`, and clear the client's failures after a successful login.
- Session control: expose authenticated counts and policy facts in Insights, while a global revoke operation removes every server-side session in one database transaction and expires the current cookie.
- Privacy boundary: the development stack remains localhost-only; the browser keeps an HttpOnly, SameSite cookie and never receives stored session records.
- Verification: the regression test covers a rejected password, successful recovery, security overview fields, ordinary logout, re-login, global revocation and subsequent 401 enforcement.

## Decision 018 - Verify stored evidence instead of trusting metadata

- Reliability gap: a database row proves that an upload completed once, but it does not prove the original still exists or remains unmodified on disk.
- Decision: add an authenticated, on-demand integrity scan that streams each original through SHA-256 in 1 MiB blocks, compares database references with disk contents, and detects missing thumbnails and untracked object files.
- Product evidence: Insights reports verified hashes, blocking failures, derivative gaps, orphan objects and measured scan duration, with bounded issue details rather than an unbounded payload.
- Performance boundary: the scan is explicit rather than automatic on page load because hashing an entire growing library is I/O intensive; the UI exposes a clear running state and allows deliberate rescans.
- Verification: the regression suite scans the real demo library and requires every original hash to verify with zero blocking issues.

## Decision 019 - Repair derived state without destroying source data

- Maintenance boundary: missing thumbnails are reproducible derivatives, while untracked objects may still contain the user's only copy of a photo.
- Decision: safe repair regenerates only missing thumbnails and moves orphan objects into timestamped quarantine. It never attempts to overwrite checksum failures, fabricate missing originals or permanently delete unknown files.
- User control: repair appears only when the scan finds a repairable derivative or orphan issue, requires confirmation, and immediately rescans to report the post-repair state.
- Verification: the regression suite creates a controlled orphan fixture, confirms repair quarantines it, verifies the follow-up report contains zero orphan objects, and removes the isolated fixture afterward.

## Decision 020 - Move library-wide hashing out of the request lifecycle

- Scale problem: synchronous integrity checks keep one HTTP request open for the full duration and provide no durable progress when a large library or slow disk extends the scan.
- Decision: create a persisted integrity job, execute hashing through a FastAPI background task, and expose job creation, latest-job recovery and per-job status endpoints. Only one queued or running job may exist, so repeated clicks reuse active work.
- Progress contract: SQLite stores total files, completed files, current filename, timestamps, final JSON result and bounded errors; the frontend polls only while the task is active and restores the latest state after a page refresh.
- Failure recovery: startup converts abandoned queued or running rows into explicit failed jobs instead of leaving a permanently active record after a process restart.
- Verification: the regression suite creates a real background scan, polls it to a terminal state, reloads it through the latest-job endpoint and validates the completed hash report.

## Decision 021 - Share a collection without widening the vault boundary

- Product need: sharing individual photo links does not support travel albums, event collections or a portfolio presentation as one coherent experience.
- Decision: give an album one random expiring token with immediate revocation and visit tracking. Membership stays relational, so additions and removals are reflected without copying photo records.
- Authorization boundary: owner endpoints require the vault session. Anonymous metadata and media routes validate the token, expiry, live album membership and trash state on every request, and return only presentation fields rather than storage paths or private metadata.
- User experience: the owner can create or copy a link from an open album; recipients receive a responsive masonry collection with an original-resolution lightbox and no login requirement.
- Verification: the regression suite creates a 24-hour link, reads it through a cookie-free client, fetches a member thumbnail, rejects a non-member ID, revokes the link and confirms subsequent anonymous access returns 404.

## Decision 022 - Make disaster recovery portable and non-destructive

- Recovery gap: photo and album exports preserve selected originals, but they do not reconstruct a complete library's favorites, captions, tags, trash state and album membership after migration or database loss.
- Decision: export a versioned ZIP containing originals plus a complete relational manifest, then restore through a merge-only importer. SHA-256 uniqueness maps duplicate source IDs onto existing photos while album membership is rebuilt without replacing current records.
- Archive safety: imports enforce compressed and expanded size limits, entry-count bounds, a known format version, basename-safe metadata, member paths rooted under `objects/`, and streamed SHA-256 verification before publishing a file.
- Destructive boundary: restore never carries over public share tokens, never deletes existing records, and never overwrites a checksum conflict; the UI states this merge policy before upload.
- Verification: the regression suite exports the live vault, opens the ZIP in memory, checks every manifest member exists, imports the same archive and confirms every photo is skipped as a duplicate with zero existing deletions.

## Decision 023 - Replace presentation pagination with database pagination

- Scale flaw: the earlier cursor-shaped API still loaded every photo and tag into Python, applied filters in memory and sliced the resulting list. Its response was bounded, but database work and process memory still grew with the entire library.
- Decision: compile view state, album membership, capture month and name/caption/tag search into one parameterized SQLite query. Fetch `limit + 1` rows and use the final returned rowid as a descending keyset cursor.
- Query design: existing state and relationship indexes support favorites, trash and album membership; a capture-time index supports chronological filtering. Tag matching uses an indexed membership `EXISTS` subquery while text matching remains substring-compatible.
- Product evidence: the API returns a filter-wide total independently of the page cursor, and the toolbar distinguishes currently loaded photos from total matches.
- Verification: the regression suite checks stable totals across consecutive cursors, distinct page membership, album totals and tag-search totals while the existing view-state tests continue to pass.

## Decision 024 - Treat EXIF time as a useful default, not unquestionable truth

- Product gap: screenshots, scans and messaging-app copies often lack EXIF capture time, while edited photos may contain a misleading date. A read-only timeline leaves these records permanently under `Unknown date` or the wrong month.
- Decision: allow capture-time correction in photo details and one shared date across a selected batch. Empty input deliberately clears the date, while valid browser ISO input is normalized to the existing EXIF-compatible storage representation.
- Data integrity: the server parses every supplied value instead of accepting arbitrary strings; both single and batch paths use the same normalization function and the indexed timeline query remains the only grouping implementation.
- User evidence: saved changes immediately update the selected card and move records into the corresponding month without rewriting image bytes or synthetic EXIF data.
- Verification: the regression suite moves a real photo into May 2024, verifies normalized storage and month lookup, batch-moves selected photos into August 2023, checks the filtered total, then restores every original timestamp.

## Decision 025 - Keep album presentation relational and live

- Product need: a recently added photo is not always the right album cover, and a title alone cannot explain the context of a trip, event or portfolio collection.
- Decision: persist a bounded album description and an optional custom cover reference. Cover writes require a visible album member; reads use the custom cover only while that membership remains valid, then fall back to the newest visible member.
- Consistency boundary: private album cards and public share pages read the same live album record. No presentation snapshot is copied into a share, so descriptions and membership changes remain synchronized.
- Portability: full-vault backups include description and effective cover identity; merge restore applies presentation only to newly created albums so an existing same-name album is never overwritten.
- Verification: the regression suite sets a real member cover and description, rejects a non-member cover, confirms both values on a cookie-free public page, then restores the prior presentation state.

## Decision 026 - Separate relationship removal from photo deletion

- UX failure: the album gallery reused the global trash action, so an operation that appeared local hid the one shared photo entity from every album.
- Decision: album cards expose `Remove from album`, backed by a relationship-only DELETE endpoint. Global views retain `Move to trash`, and permanent deletion remains available only inside Trash.
- Data model: one original continues to serve many albums, preserving deduplication and metadata consistency. Unlinking deletes one `album_photos` row; trash changes the shared photo state; permanent deletion removes the entity and all relationships.
- Safety copy: global trash and permanent delete now require confirmations that explicitly state their cross-album scope, while a successful unlink confirms the original remains in the library.
- Verification: the regression suite removes a real member, confirms it disappears only from that album while remaining in the main library, then restores the relationship for deterministic reruns.

## Decision 027 - Move image derivatives out of upload completion

- Scale problem: thumbnail encoding and EXIF extraction are CPU-heavy and previously kept the final upload request open, making large or concurrent uploads feel stalled after every byte had already arrived.
- Decision: persist the original and photo row first, enqueue one durable processing record per photo, then generate the WebP preview and metadata in a FastAPI background task. Active duplicate requests reuse the existing job.
- Recovery contract: queued and running jobs become explicit failures after a server restart; the gallery preserves the original record, shows processing state, polls only while work is active, and lets the user retry a failed derivative.
- Verification: the regression suite removes a real derivative, starts processing through the retry endpoint, polls the persisted job to `ready`, and requires a newly generated non-empty thumbnail; the production TypeScript build validates every UI state.

## Decision 028 - Detect visual duplicates without automating deletion

- Product problem: byte-level SHA-256 deduplication catches identical uploads but misses resized, recompressed and format-converted copies that look the same to a person.
- Decision: calculate an orientation-corrected 64-bit difference hash, persist it with the photo metadata, connect photos within a conservative Hamming-distance threshold, and show review groups ordered by recoverable bytes.
- Safety boundary: similarity is only evidence, not proof. The feature never selects or deletes a photo automatically; it presents dimensions, sizes and a suggested largest original for human review.
- Verification: the regression suite scans the real library, validates report totals and policy text, and compares every visible photo ID before and after the scan to prove that no library entity was changed or removed.

## Decision 029 - Keep duplicate cleanup reversible and user-directed

- Workflow gap: detection alone still forces users to leave the comparison view and manually find each alternate copy, while automatic cleanup would overstate the certainty of a perceptual hash.
- Decision: let the user choose one retained photo inside each similarity group, then move every explicitly reviewed alternate into global Trash through one SQLite transaction. The largest file is suggested, never silently selected for deletion.
- Safety boundary: a centered confirmation explains that global trash affects every album; the endpoint reports zero permanent deletions and the UI rescans only after the recoverable operation succeeds.
- Verification: the regression suite moves a real alternate into Trash, downloads its still-present original bytes, restores it, and proves the complete visible photo ID set matches its pre-cleanup state.

## Decision 030 - Compose advanced filters inside SQLite

- Retrieval problem: keyword search alone cannot efficiently answer practical library questions such as large landscape photos from a date range, especially when combined with albums and tags.
- Decision: compile date bounds, minimum bytes, orientation and four sort modes into the existing parameterized SQLite query. The UI exposes one collapsible panel, counts active conditions and preserves every existing gallery action.
- Pagination contract: cursors now carry the active sort value plus row identity, so size and capture-time ordering remain stable between pages instead of reverting to import order after page one.
- Index discipline: the existing capture-time index supports range filtering; size and orientation remain unindexed until real usage justifies their write and storage cost.
- Verification: the regression suite checks descending size order, orientation predicates, exact-date composition, sorted cursor continuity and rejection of an unsupported orientation while the full API suite remains green.

## Decision 031 - Modularize by dependency boundary before splitting gallery state

- Maintainability problem: the initial vertical slice accumulated public pages, authenticated panels, domain types, hashing helpers and the main gallery controller in one entry file, increasing the regression surface of every change.
- Decision: extract shared domain types, API configuration and formatting/hash utilities first; then move login, public shares, metadata editing, backup, integrity and duplicate-review surfaces into independent modules with explicit typed props.
- Sequencing: the state-heavy gallery shell remains intact during this pass so component extraction cannot silently change upload, selection or navigation behavior. Its API orchestration and upload state are the next modularization boundary.
- Verification: the production TypeScript build resolves every new module and the complete authenticated backend regression suite passes against four real photo records without changing API behavior.

## Decision 032 - Isolate the upload protocol as a stateful hook

- Coupling problem: hashing, resumable-session discovery, three concurrent chunk workers, retry backoff, pause state, throughput measurement and completion refresh all lived inside the gallery controller.
- Decision: move the upload state machine into `useChunkedUpload` and render its state through a pure `UploadQueue` component. The gallery now supplies files and one completion callback without understanding chunk indexes or retry timing.
- Failure boundary: a failed worker now produces an explicit per-file `failed` state instead of leaving the UI labeled as uploading; server-side resumability remains the recovery mechanism for a later retry.
- Verification: the production TypeScript build validates the Hook/component contract, the local Vite route returns HTTP 200, and the complete backend regression suite continues to exercise resumable upload initialization, status and cancellation.

## Decision 033 - Finish frontend modularization around state ownership

- Architecture goal: make the boot file responsible only for authentication and public routing, keep authenticated composition in one page, and give each stateful workflow exactly one owner.
- State boundaries: `usePhotoLibrary` owns query composition, filter refresh, sort-aware pagination and processing polling; `useAlbums` owns album collection state; `useChunkedUpload` owns the upload state machine; `useVaultActions` owns authenticated mutations and downloads.
- Presentation boundaries: navigation, header, filters, batch commands, collection grids, photo grid, photo detail, delete confirmation, insights and upload progress are typed components that receive data and callbacks rather than issuing unrelated state changes.
- Entry boundary: `main.tsx` now contains only session bootstrap and selection of login, public-share or authenticated entry pages. `VaultPage` composes domain Hooks and presentation components without containing upload, query or mutation protocols.
- Verification: the final production build passes across 24 TypeScript/TSX modules, the live local route returns HTTP 200, and the complete authenticated API regression suite passes against four real photo records.

## Decision 034 - Measure before changing the concurrency path

- Performance problem: the first full load run could not finish within two minutes; the reproducible 20% profile measured only 4-5 requests per second and an 8.15-second mixed-read P95 despite zero request failures.
- Diagnosis: synchronous SQLite session checks and request-audit writes ran inside asynchronous middleware, while every audit event repeated retention cleanup. This serialized otherwise independent reads behind database work.
- Decision: move session validation to the worker pool, attach audit persistence after response delivery, enable WAL plus a busy timeout, and amortize retention cleanup across 100 inserts. Keep the test workload unchanged between measurements.
- Evidence: read throughput improved 4.0-7.0x and mixed-read P95 fell 66.9% to 2694 ms with 0% errors. Upload initialization improved 2.0x but remained write-bound and is reported separately rather than hidden in an aggregate.
- Verification: raw JSON results, scenario definitions, limitations and a technical summary are preserved in `artifacts/performance` and `docs/performance-report.md`; the complete API regression and production frontend build are the final gates.

## Decision 035 - Deploy the architecture that actually exists

- Deployment flaw: the original Compose file started PostgreSQL and MinIO even though runtime code continued to use SQLite and the local filesystem; its standalone Nginx frontend also lacked an API reverse proxy.
- Decision: compile React in a multi-stage image and serve it from the FastAPI process under the same origin. Persist the complete data directory in one named volume and remove inactive infrastructure claims.
- Security boundary: the production process runs as a non-root user with dropped Linux capabilities, rejects the demo password, supports Secure cookies behind HTTPS, exposes a health check and receives secrets only through environment configuration.
- Operations: document first deploy, LAN access, HTTPS requirements, portable and volume backups, restore verification, upgrade, rollback and common failure diagnosis.
- Verification: an isolated production-entrypoint test checks SPA fallback, compiled assets, API health, anonymous rejection, login cookies and authenticated queries; the full API smoke suite and frontend build remain mandatory release gates.

## Decision 036 - Make portfolio claims independently verifiable

- Communication problem: a long feature list forces reviewers to trust prose or inspect the entire repository, which weakens the value of otherwise real engineering work.
- Decision: provide a short showcase, architecture and upload lifecycle diagrams, and a claim-to-code evidence index. Keep limitations beside the claims rather than hiding them; keep personal job-search notes outside the public repository.
- AI Coding positioning: describe AI as an accelerator for decomposition, drafts, refactoring and diagnosis; demonstrate human ownership through safety boundaries, rejected over-engineering, raw measurements and executable release gates.
- Verification: a documentation checker validates every local Markdown link and required artifact; production build, complete API regression and isolated production-entrypoint verification are rerun after the handoff material is created.
