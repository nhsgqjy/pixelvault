# Shared API client

PixelVault's frontend sends every API request through `packages/api-client`.
The client owns API URL construction, query-string encoding, cookie credentials,
shared headers, JSON serialization, response parsing and `ApiError` creation.

`frontend/src/lib/api.ts` is the application adapter. It reads
`VITE_API_BASE_URL`, appends `/api`, and creates the single browser client. Keep
feature modules independent of environment variables by importing `api` from
that adapter.

Use `api.get`, `post`, `patch`, `put` or `delete` for JSON endpoints. Use
`api.raw` when the caller must inspect `response.ok`, stream a Blob, or preserve
the upload retry flow. Use `api.url` for image and download URLs placed directly
in DOM attributes.

Run the focused client tests from the repository root:

```powershell
cd packages\api-client
npm test
```

Then run the consuming application build:

```powershell
cd frontend
pnpm build
```

This stage changes only the frontend request boundary. PostgreSQL persistence
and object storage are separate later stages and are not implemented here.
