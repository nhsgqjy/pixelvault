import assert from 'node:assert/strict';
import test from 'node:test';
import {ApiError, createApiClient} from '../src/index.ts';

test('builds encoded URLs and omits null query values', () => {
  const api = createApiClient({baseUrl: 'https://vault.example/api'});
  assert.equal(
    api.url('/photos', {search: 'summer trip', tag: ['family', 'pets'], cursor: null}),
    'https://vault.example/api/photos?search=summer+trip&tag=family&tag=pets',
  );
});

test('serializes JSON and applies shared request defaults', async () => {
  let captured: {url: string; init?: RequestInit} | undefined;
  const api = createApiClient({
    baseUrl: 'https://vault.example/api/',
    credentials: 'include',
    getHeaders: () => ({'X-Client': 'pixelvault'}),
    fetch: async (input, init) => {
      captured = {url: String(input), init};
      return Response.json({ok: true});
    },
  });

  assert.deepEqual(await api.post('/albums', {json: {name: 'Family'}}), {ok: true});
  assert.equal(captured?.url, 'https://vault.example/api/albums');
  assert.equal(captured?.init?.credentials, 'include');
  assert.equal(captured?.init?.body, JSON.stringify({name: 'Family'}));
  const headers = new Headers(captured?.init?.headers);
  assert.equal(headers.get('Accept'), 'application/json');
  assert.equal(headers.get('Content-Type'), 'application/json');
  assert.equal(headers.get('X-Client'), 'pixelvault');
});

test('throws ApiError with the backend detail', async () => {
  const api = createApiClient({
    baseUrl: 'https://vault.example/api',
    fetch: async () => Response.json({detail: 'Album already exists'}, {status: 409}),
  });

  await assert.rejects(
    api.post('/albums', {json: {name: 'Family'}}),
    (error: unknown) => error instanceof ApiError && error.status === 409 && error.message === 'Album already exists',
  );
});

test('raw returns non-JSON responses without consuming the body', async () => {
  const api = createApiClient({
    baseUrl: 'https://vault.example/api',
    fetch: async () => new Response('archive-bytes', {headers: {'Content-Type': 'application/zip'}}),
  });

  const response = await api.raw('/backups/export');
  assert.equal(await response.text(), 'archive-bytes');
});
