import assert from 'node:assert/strict';
import test from 'node:test';
import { loadModule } from './helpers/load-typescript.mjs';

// Exercise the real TypeScript modules with in-memory session/network/DOM
// boundaries. No local server, application data, or R2 credentials are needed.
const uploadConfig = loadModule('ultis/documentUpload.ts');

function proxy({ token = 'session-token', status = 200, fail = false } = {}) {
  const calls = [];
  const payload = { data: { url: 'https://test.r2.cloudflarestorage.com/file?signed=1' } };
  const route = loadModule('app/api/backend/[...path]/route.ts', {
    '@/ultis/documentUpload': uploadConfig,
    '@/ultis/serverUpload': {},
    'next/headers': { cookies: async () => ({ get: () => token ? { value: token } : undefined }) },
    '@/ultis/serverSession': {
      SESSION_COOKIE: 'regula_session',
      apiError: (code, message) => Response.json({ message }, { status: code }),
      jsonResponse: (data, code) => Response.json(data, { status: code, headers: { 'Cache-Control': 'private, no-store' } }),
      clearSession(response) { response.headers.set('Set-Cookie', 'regula_session=; Max-Age=0'); return response; },
      sameOrigin: () => true,
      backendFetch: async (...args) => {
        calls.push(args);
        if (fail) throw new Error('Storage unavailable');
        return Response.json(payload, { status });
      },
    },
  });
  return { calls, route, payload };
}

for (const [path, search] of [
  ['documents/12/versions', '?page=2&itemsPerPage=5'],
  ['documents/12/download-url', '?version_id=35'],
]) {
  test(`GET ${path} forwards the query and server session, without caching`, async () => {
    const { route, calls, payload } = proxy();
    const response = await route.GET({ nextUrl: new URL(`http://localhost/api/backend/${path}${search}`) }, {
      params: Promise.resolve({ path: path.split('/') }),
    });
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), payload);
    assert.equal(calls[0][0], `/${path}${search}`);
    assert.equal(calls[0][2], 'session-token');
    assert.match(response.headers.get('cache-control'), /no-store/);
  });

  test(`GET ${path} requires a session before calling the backend`, async () => {
    const { route, calls } = proxy({ token: null });
    const response = await route.GET({}, { params: Promise.resolve({ path: path.split('/') }) });
    assert.equal(response.status, 401);
    assert.equal(calls.length, 0);
  });
}

test('Read allowlist does not expose unrelated nested endpoints or new mutations', async () => {
  const { route, calls } = proxy();
  for (const path of ['auth/me', 'documents/12/preview-url', 'documents/12/versions/35', 'documents/versions']) {
    const response = await route.GET({}, { params: Promise.resolve({ path: path.split('/') }) });
    assert.equal(response.status, 404);
  }
  for (const path of ['documents/12/versions/35', 'documents/12/download-url']) {
    assert.equal((await route.POST({}, { params: Promise.resolve({ path: path.split('/') }) })).status, 404);
  }
  assert.equal(calls.length, 0);
});

for (const status of [401, 403, 404, 409, 502]) {
  test(`Download proxy preserves backend ${status} errors`, async () => {
    const { route } = proxy({ status });
    const response = await route.GET({ nextUrl: new URL('http://localhost/api/backend/documents/12/download-url?version_id=35') }, {
      params: Promise.resolve({ path: ['documents', '12', 'download-url'] }),
    });
    assert.equal(response.status, status);
    if (status === 401) assert.match(response.headers.get('set-cookie'), /Max-Age=0/);
  });
}

test('Unavailable backend yields a retryable response', async () => {
  const { route } = proxy({ fail: true });
  const response = await route.GET({ nextUrl: new URL('http://localhost/api/backend/documents/12/versions') }, {
    params: Promise.resolve({ path: ['documents', '12', 'versions'] }),
  });
  assert.equal(response.status, 503);
});

test('Client API uses the selected version ID, requests fresh URLs, and supports cancellation', async () => {
  const calls = [];
  const api = { get: async (...args) => { calls.push(args); return { data: { data: { url: `https://test.r2.cloudflarestorage.com/file?signed=${calls.length}` } } }; } };
  const client = loadModule('apis/documentApis.ts', {
    '@/ultis/documentUpload': uploadConfig,
    '@/axios': { __esModule: true, default: api }, '@/routes': { API_ROUTES: { documents: '/backend/documents' } },
  });
  const signal = new AbortController().signal;
  await client.getDocumentVersions(12, { page: 2, itemsPerPage: 5 }, signal);
  assert.equal(calls[0][0], '/backend/documents/12/versions');
  assert.equal(calls[0][1].params.page, 2);
  assert.equal(calls[0][1].params.itemsPerPage, 5);
  assert.equal(calls[0][1].signal, signal);
  const first = await client.getDocumentDownload(12, 35, signal);
  const second = await client.getDocumentDownload(12, 35, signal);
  assert.notEqual(first.data.url, second.data.url);
  assert.equal(calls[1][0], '/backend/documents/12/download-url');
  assert.equal(calls[1][1].params.version_id, 35);
  assert.equal(calls[1][1].signal, signal);
});

function downloadHarness(clickFails = false) {
  let attached = false;
  let clicked = false;
  let removed = false;
  const anchor = {
    click() {
      assert.ok(attached);
      clicked = true;
      if (clickFails) throw new Error('Download blocked');
    },
    remove() { removed = true; },
  };
  const downloadModule = loadModule('ultis/downloadFile.ts', {}, { document: {
    createElement(tag) { assert.equal(tag, 'a'); return anchor; },
    body: { appendChild(link) { assert.equal(link, anchor); attached = true; } },
  } });
  return { ...downloadModule, anchor, state: () => ({ attached, clicked, removed }) };
}

test('Native file download preserves the signed URL and Vietnamese name without a popup', () => {
  const harness = downloadHarness();
  const file = { file_name: 'Quy chế đào tạo.pdf', url: 'https://test.r2.cloudflarestorage.com/file?X-Amz-Signature=abc&response-content-disposition=attachment' };
  harness.downloadFile(file);
  assert.equal(harness.anchor.href, file.url);
  assert.equal(harness.anchor.download, file.file_name);
  assert.equal(harness.anchor.referrerPolicy, 'no-referrer');
  assert.equal(harness.anchor.rel, 'noreferrer');
  assert.equal(harness.anchor.target, undefined);
  assert.deepEqual(harness.state(), { attached: true, clicked: true, removed: true });
});

for (const url of ['javascript:alert(1)', 'data:text/html,bad', 'http://insecure.example/file', '/relative-file']) {
  test(`Reject invalid download destination ${url.split(':')[0]}`, () => {
    const harness = downloadHarness();
    assert.throws(() => harness.downloadFile({ file_name: 'file.pdf', url }));
    assert.deepEqual(harness.state(), { attached: false, clicked: false, removed: false });
  });
}

test('Download trigger is cleaned up if navigation fails', () => {
  const harness = downloadHarness(true);
  assert.throws(() => harness.downloadFile({ file_name: 'file.pdf', url: 'https://test.r2.cloudflarestorage.com/file' }), /Download blocked/);
  assert.equal(harness.state().removed, true);
});
