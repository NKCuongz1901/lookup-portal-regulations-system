import assert from 'node:assert/strict';
import test from 'node:test';
import { loadModule } from './helpers/load-typescript.mjs';

function proxy({ token = 'session-token', origin = true, status = 200, fail = false } = {}) {
  const calls = [];
  const payload = { data: null, message: 'Document deleted', status_code: status };
  const route = loadModule('app/api/backend/[...path]/route.ts', {
    'next/headers': { cookies: async () => ({ get: () => token ? { value: token } : undefined }) },
    '@/ultis/documentUpload': {}, '@/ultis/serverUpload': {},
    '@/ultis/serverSession': {
      SESSION_COOKIE: 'regula_session', sameOrigin: () => origin,
      apiError: (code, message) => Response.json({ message }, { status: code }),
      jsonResponse: (data, code) => Response.json(data, { status: code, headers: { 'Cache-Control': 'private, no-store' } }),
      clearSession(response) { response.headers.set('Set-Cookie', 'regula_session=; Max-Age=0'); return response; },
      backendFetch: async (...args) => {
        calls.push(args);
        if (fail) throw new Error('Connection failed');
        return Response.json(payload, { status });
      },
    },
  });
  const remove = (path = 'documents/12') => route.DELETE({
    json: () => assert.fail('DELETE should not read or forward a client body'),
    nextUrl: new URL('http://localhost/api/backend/documents/12?untrusted=1'),
  }, { params: Promise.resolve({ path: path.split('/') }) });
  return { remove, calls, payload };
}

test('Delete proxy sends a bodyless DELETE for the selected document using the server session', async () => {
  const { remove, calls, payload } = proxy();
  const response = await remove();
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), payload);
  assert.match(response.headers.get('cache-control'), /no-store/);
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], '/documents/12');
  assert.equal(calls[0][1].method, 'DELETE');
  assert.equal(calls[0][1].body, undefined);
  assert.equal(calls[0][2], 'session-token');
});

test('Delete requires authentication and a same-origin request before calling the backend', async () => {
  for (const [options, status] of [[{ token: null }, 401], [{ origin: false }, 403]]) {
    const { remove, calls } = proxy(options);
    assert.equal((await remove()).status, status);
    assert.equal(calls.length, 0);
  }
});

test('Delete allowlist does not expose bulk deletion, other resources, or nested endpoints', async () => {
  const { remove, calls } = proxy();
  for (const path of ['documents', 'users/12', 'documents/0', 'documents/-1', 'documents/bad', 'documents/12/archive', 'documents/12/versions', 'documents/12/download-url']) {
    assert.equal((await remove(path)).status, 404);
  }
  assert.equal(calls.length, 0);
});

test('Delete preserves backend errors and clears expired sessions', async () => {
  for (const status of [401, 403, 404, 409, 422, 500]) {
    const { remove } = proxy({ status });
    const response = await remove();
    assert.equal(response.status, status);
    if (status === 401) assert.match(response.headers.get('set-cookie'), /Max-Age=0/);
  }
});

test('Delete connection failure does not automatically retry the mutation', async () => {
  const { remove, calls } = proxy({ fail: true });
  assert.equal((await remove()).status, 503);
  assert.equal(calls.length, 1);
});

test('Client deletion uses the selected document ID and returns the null-data response', async () => {
  const calls = [];
  const payload = { data: null, message: 'Document deleted', status_code: 200 };
  const client = loadModule('apis/documentApis.ts', {
    '@/axios': { __esModule: true, default: { delete: async (...args) => { calls.push(args); return { data: payload }; } } },
    '@/routes': { API_ROUTES: { documents: '/backend/documents' } }, '@/ultis/documentUpload': {},
  });
  assert.equal(await client.deleteDocument(12), payload);
  assert.deepEqual(calls, [['/backend/documents/12']]);
});
