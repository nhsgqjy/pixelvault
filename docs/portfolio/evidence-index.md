# PixelVault evidence index

This index lets a reviewer verify claims without reading the repository from top to bottom.

| Claim | Primary implementation | Executable or raw evidence |
| --- | --- | --- |
| Resumable concurrent uploads | `frontend/src/hooks/useChunkedUpload.ts`, upload routes in `backend/app/main.py` | resumable-session section of `backend/smoke_test.py` |
| SHA-256 deduplication and completion verification | upload initialization/completion routes | duplicate/resume assertions in smoke suite |
| Durable WebP/EXIF processing | `photo_processing_jobs`, `run_photo_processing`, `usePhotoLibrary.ts` polling | derivative deletion, retry and regeneration smoke flow |
| Relational albums and safe membership removal | `albums`, `album_photos`, `CollectionViews.tsx` | rename, cover, unlink and relationship restoration assertions |
| Metadata and timeline | normalized `tags`/`photo_tags`, capture-time queries | metadata normalization, tag search and month-filter assertions |
| Safe duplicate review | difference hash scan and transactional Trash cleanup | scan immutability, recoverable cleanup and restore assertions |
| Integrity and recovery | streamed checksum jobs, derivative rebuild, orphan quarantine | controlled orphan fixture and post-repair verification |
| Private/public authorization boundary | session middleware and tokenized share routes | anonymous 401, public media access, expiry/revocation assertions |
| Backup portability | versioned ZIP manifest and checksum-verified merge importer | in-memory archive inspection and no-delete restore assertions |
| Database-native keyset pagination | `query_photos` in `backend/app/db.py` | stable cursor, total and sort continuity assertions |
| Measured concurrency optimization | middleware and SQLite pragmas/audit policy | `artifacts/performance/*.json`, `docs/performance-report.md` |
| Frontend modularity | pages, components, hooks, lib and domain types | TypeScript production build |
| Production entrypoint | root `Dockerfile`, Compose and SPA fallback | `tools/verify_production.py` |

## Release gates

```bash
cd frontend && npm run build
cd ../backend && python smoke_test.py
cd .. && python tools/verify_production.py
```

Expected results:

- Vite production build completes without TypeScript errors.
- API smoke test reports the number of real photo records and enforced authentication.
- Production verifier confirms compiled SPA hosting, client-route fallback, static assets, health, login and private API access.

## Performance artifact integrity

- `artifacts/performance/baseline.json` is the unoptimized fixed-workload result.
- `artifacts/performance/optimized.json` is the same workload after the middleware/SQLite changes.
- `backend/performance_test.py` contains scenario request counts, concurrency and percentile calculation.
- `docs/performance-report.md` states the four-photo local data-set limitation and does not present the numbers as production capacity.

## AI-assisted development evidence

`docs/ai-development-log.md` records 35 decisions. The useful pattern is consistent:

1. identify a real product, reliability, security or scale problem;
2. state the human decision and boundary;
3. link it to a concrete implementation;
4. define an executable verification rather than treating generated code as evidence.
