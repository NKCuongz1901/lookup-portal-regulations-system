import assert from 'node:assert/strict';
import test from 'node:test';
import { loadModule } from './helpers/load-typescript.mjs';

const plain = (value) => JSON.parse(JSON.stringify(value));
const form = loadModule('ultis/documentTypeForm.ts');
const record = { id: 7, code: 'QUY_DINH', name: 'Quy định', description: 'Mô tả', is_active: true, created_at: '2026-10-26T00:00:00Z' };

test('Only active administrators can manage types, including users with multiple roles', () => {
  for (const roles of [['ADMIN'], ['STAFF', 'ADMIN']]) {
    assert.equal(form.canManageDocumentTypes({ is_active: true, roles }), true);
    assert.equal(form.canManageDocumentTypes({ is_active: false, roles }), false);
  }
  for (const roles of [[], ['STAFF'], ['STUDENT']]) {
    assert.equal(form.canManageDocumentTypes({ is_active: true, roles }), false);
  }
});

test('Create normalizes text, preserves inactive status, and excludes server-controlled fields', () => {
  assert.deepEqual(plain(form.documentTypePayload({ ...record, code: ' QUY_DINH ', name: ' Quy định ', description: '  ', is_active: false })), {
    code: 'QUY_DINH', name: 'Quy định', description: null, is_active: false,
  });
});

test('Edit sends only changed fields, supports clearing descriptions, and skips unchanged forms', () => {
  assert.deepEqual(plain(form.documentTypeChanges({ ...record, name: ' Quy định ' }, record)), {});
  assert.deepEqual(plain(form.documentTypeChanges({ ...record, description: '', name: ' Tên mới ' }, record)), {
    name: 'Tên mới', description: null,
  });
  assert.deepEqual(plain(form.documentTypeChanges({ ...record, is_active: false }, record)), { is_active: false });
  assert.deepEqual(plain(form.documentTypeChanges(record, { ...record, is_active: false })), { is_active: true });
});

function proxy({ token = 'session-token', origin = true, status = 200, failure = false } = {}) {
  const calls = [];
  const payload = status >= 400 ? { message: 'Backend error' } : { data: record };
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
        if (failure) throw new Error('Unavailable');
        return Response.json(payload, { status });
      },
    },
  });
  const call = (method, path, request = jsonRequest(method)) => route[method](request, { params: Promise.resolve({ path: path.split('/') }) });
  return { calls, call, payload };
}

function jsonRequest(method, body = { code: 'QUY_DINH', name: 'Quy định', description: null, is_active: false }) {
  if (method === 'GET') return { nextUrl: new URL('http://localhost/api/backend/document-types') };
  return new Request('http://localhost/api/backend/document-types', {
    method, body: JSON.stringify(body), headers: { 'Content-Type': 'application/json; charset=utf-8' },
  });
}

test('List and detail proxy forward session and search parameters with uncached responses', async () => {
  const { call, calls, payload } = proxy();
  const query = '?page=2&itemsPerPage=20&is_active=false&search=Quy';
  const response = await call('GET', 'document-types', { nextUrl: new URL(`http://localhost/api/backend/document-types${query}`) });
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), payload);
  assert.match(response.headers.get('cache-control'), /no-store/);
  assert.equal(calls[0][0], `/document-types${query}`);
  assert.equal(calls[0][2], 'session-token');
  assert.equal((await call('GET', 'document-types/7')).status, 200);
  assert.equal(calls[1][0], '/document-types/7');
});

test('Create and edit forward the correct method, payload, session, and backend status', async () => {
  for (const [method, path, status] of [['POST', 'document-types', 201], ['PATCH', 'document-types/7', 200]]) {
    const { call, calls, payload } = proxy({ status });
    const body = method === 'POST' ? form.documentTypePayload(record) : { description: null, is_active: false };
    const response = await call(method, path, jsonRequest(method, body));
    assert.equal(response.status, status);
    assert.deepEqual(await response.json(), payload);
    assert.match(response.headers.get('cache-control'), /no-store/);
    assert.equal(calls[0][0], `/${path}`);
    assert.equal(calls[0][1].method, method);
    assert.deepEqual(JSON.parse(calls[0][1].body), plain(body));
    assert.equal(calls[0][2], 'session-token');
  }
});

test('Document creation still forwards to the documents endpoint', async () => {
  const { call, calls } = proxy({ status: 201 });
  const body = { code: 'QD-NEW', title: 'Văn bản mới', document_type_id: 7 };
  assert.equal((await call('POST', 'documents', jsonRequest('POST', body))).status, 201);
  assert.equal(calls[0][0], '/documents');
  assert.deepEqual(JSON.parse(calls[0][1].body), body);
});

test('Every metadata request requires a session and mutations require same-origin', async () => {
  for (const [method, path] of [['GET', 'document-types'], ['GET', 'document-types/7'], ['POST', 'document-types'], ['PATCH', 'document-types/7']]) {
    const { call, calls } = proxy({ token: null });
    assert.equal((await call(method, path)).status, 401);
    assert.equal(calls.length, 0);
    if (method !== 'GET') {
      const otherOrigin = proxy({ origin: false });
      assert.equal((await otherOrigin.call(method, path)).status, 403);
      assert.equal(otherOrigin.calls.length, 0);
    }
  }
});

test('Allowlist rejects invalid IDs, nested actions, unsupported mutations, and type deletion', async () => {
  const { call, calls } = proxy();
  for (const method of ['GET', 'PATCH']) {
    for (const path of ['document-types/0', 'document-types/-1', 'document-types/abc', 'document-types/7/archive', 'document-types/7/extra']) {
      assert.equal((await call(method, path)).status, 404);
    }
  }
  for (const [method, path] of [['POST', 'document-types/7'], ['PATCH', 'document-types'], ['DELETE', 'document-types/7'], ['POST', 'tags'], ['PATCH', 'issuing-units/7']]) {
    assert.equal((await call(method, path)).status, 404);
  }
  assert.equal(calls.length, 0);
});

test('Mutations reject malformed, non-object, or non-JSON bodies before reaching the backend', async () => {
  const { call, calls } = proxy();
  for (const [method, path] of [['POST', 'document-types'], ['PATCH', 'document-types/7']]) {
    for (const body of [null, [], 'text']) assert.equal((await call(method, path, jsonRequest(method, body))).status, 422);
    const malformed = new Request('http://localhost/api/backend/document-types', { method, body: '{bad', headers: { 'Content-Type': 'application/json' } });
    assert.equal((await call(method, path, malformed)).status, 422);
    const wrongType = new Request('http://localhost/api/backend/document-types', { method, body: '{}' });
    assert.equal((await call(method, path, wrongType)).status, 415);
  }
  assert.equal(calls.length, 0);
});

test('Backend role, duplicate code, validation, and missing-record errors remain intact', async () => {
  for (const [method, path] of [['GET', 'document-types/7'], ['POST', 'document-types'], ['PATCH', 'document-types/7']]) {
    for (const status of [401, 403, 404, 409, 422, 500]) {
      const { call, payload } = proxy({ status });
      const response = await call(method, path);
      assert.equal(response.status, status);
      assert.deepEqual(await response.json(), payload);
      if (status === 401) assert.match(response.headers.get('set-cookie'), /Max-Age=0/);
      else assert.equal(response.headers.get('set-cookie'), null);
    }
  }
});

test('Network failures return 503 and never automatically repeat mutations', async () => {
  for (const [method, path] of [['GET', 'document-types'], ['POST', 'document-types'], ['PATCH', 'document-types/7']]) {
    const { call, calls } = proxy({ failure: true });
    assert.equal((await call(method, path)).status, 503);
    assert.equal(calls.length, 1);
  }
});

test('Client forwards list filters, cancellation, detail IDs, and create/update payloads', async () => {
  const calls = [];
  const response = { data: record };
  const api = Object.fromEntries(['get', 'post', 'patch'].map((method) => [method, async (...args) => {
    calls.push([method, ...args]); return { data: response };
  }]));
  const client = loadModule('apis/documentTypeApis.ts', {
    '@/axios': { __esModule: true, default: api }, '@/routes': { API_ROUTES: { documentTypes: '/backend/document-types' } },
  });
  const signal = new AbortController().signal;
  const params = { page: 2, itemsPerPage: 20, search: 'Quy', is_active: false };
  assert.equal(await client.listDocumentTypes(params, signal), response);
  assert.equal(calls[0][1], '/backend/document-types');
  assert.equal(calls[0][2].params, params);
  assert.equal(calls[0][2].signal, signal);
  assert.equal(await client.getDocumentType(7, signal), response);
  assert.equal(calls[1][1], '/backend/document-types/7');
  assert.equal(calls[1][2].signal, signal);
  const payload = form.documentTypePayload(record);
  assert.equal(await client.createDocumentType(payload), response);
  assert.deepEqual(calls[2], ['post', '/backend/document-types', payload]);
  const changes = { is_active: false, description: null };
  assert.equal(await client.updateDocumentType(7, changes), response);
  assert.deepEqual(calls[3], ['patch', '/backend/document-types/7', changes]);
});
