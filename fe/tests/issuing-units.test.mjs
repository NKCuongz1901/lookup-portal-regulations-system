import assert from 'node:assert/strict';
import test from 'node:test';
import { loadModule } from './helpers/load-typescript.mjs';

const plain = (value) => JSON.parse(JSON.stringify(value));
const form = loadModule('ultis/issuingUnitForm.ts');
const record = { id: 8, code: 'PDT', name: 'Phòng Đào tạo', description: 'Quản lý đào tạo', is_active: true, created_at: '2026-10-26T00:00:00Z' };
const endpoints = [['GET', 'issuing-units'], ['GET', 'issuing-units/8'], ['POST', 'issuing-units'], ['PATCH', 'issuing-units/8']];

test('Issuing unit management is restricted to active administrators', () => {
  for (const roles of [['ADMIN'], ['STAFF', 'ADMIN']]) {
    assert.equal(form.canManageIssuingUnits({ is_active: true, roles }), true);
    assert.equal(form.canManageIssuingUnits({ is_active: false, roles }), false);
  }
  for (const roles of [[], ['STAFF'], ['STUDENT']]) {
    assert.equal(form.canManageIssuingUnits({ is_active: true, roles }), false);
  }
});

test('Unit forms trim input, retain inactive status, and exclude server-controlled fields', () => {
  assert.deepEqual(plain(form.issuingUnitPayload({ ...record, code: ' PDT ', name: ' Phòng Đào tạo ', description: ' ', is_active: false })), {
    code: 'PDT', name: 'Phòng Đào tạo', description: null, is_active: false,
  });
});

test('Unit edits preserve unchanged values and send explicit clearing or status changes', () => {
  assert.deepEqual(plain(form.issuingUnitChanges({ ...record, name: ' Phòng Đào tạo ' }, record)), {});
  assert.deepEqual(plain(form.issuingUnitChanges({ ...record, name: ' Phòng Khảo thí ', description: '' }, record)), {
    name: 'Phòng Khảo thí', description: null,
  });
  assert.deepEqual(plain(form.issuingUnitChanges({ ...record, is_active: false }, record)), { is_active: false });
  assert.deepEqual(plain(form.issuingUnitChanges(record, { ...record, is_active: false })), { is_active: true });
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

function jsonRequest(method, body = { code: 'PDT', name: 'Phòng Đào tạo', description: null, is_active: false }) {
  if (method === 'GET') return { nextUrl: new URL('http://localhost/api/backend/issuing-units') };
  return new Request('http://localhost/api/backend/issuing-units', {
    method, body: JSON.stringify(body), headers: { 'Content-Type': 'application/json; charset=utf-8' },
  });
}

test('Unit list and detail forward filters and session without caching', async () => {
  const { call, calls, payload } = proxy();
  const query = '?page=2&itemsPerPage=20&is_active=false&search=PDT';
  const response = await call('GET', 'issuing-units', { nextUrl: new URL(`http://localhost/api/backend/issuing-units${query}`) });
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), payload);
  assert.match(response.headers.get('cache-control'), /no-store/);
  assert.equal(calls[0][0], `/issuing-units${query}`);
  assert.equal(calls[0][2], 'session-token');
  assert.equal((await call('GET', 'issuing-units/8')).status, 200);
  assert.equal(calls[1][0], '/issuing-units/8');
});

test('Unit creation and editing preserve method, payload, and backend status', async () => {
  for (const [method, path, status] of [['POST', 'issuing-units', 201], ['PATCH', 'issuing-units/8', 200]]) {
    const { call, calls, payload } = proxy({ status });
    const body = method === 'POST' ? form.issuingUnitPayload(record) : { description: null, is_active: false };
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

test('Unit endpoints require a session and same-origin mutations', async () => {
  for (const [method, path] of endpoints) {
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

test('Unit allowlist excludes invalid IDs, nested actions, deletion, and unrelated resources', async () => {
  const { call, calls } = proxy();
  for (const method of ['GET', 'PATCH']) {
    for (const suffix of ['0', '-1', 'abc', '8/archive', '8/extra']) {
      assert.equal((await call(method, `issuing-units/${suffix}`)).status, 404);
    }
  }
  for (const [method, path] of [['POST', 'issuing-units/8'], ['PATCH', 'issuing-units'], ['DELETE', 'issuing-units/8'], ['POST', 'users'], ['PATCH', 'users/8']]) {
    assert.equal((await call(method, path)).status, 404);
  }
  assert.equal(calls.length, 0);
});

test('Unit mutations reject malformed and non-JSON payloads without upstream calls', async () => {
  const { call, calls } = proxy();
  for (const [method, path] of endpoints.filter(([method]) => method !== 'GET')) {
    for (const body of [null, [], 'text']) assert.equal((await call(method, path, jsonRequest(method, body))).status, 422);
    const malformed = new Request('http://localhost/api/backend/issuing-units', { method, body: '{bad', headers: { 'Content-Type': 'application/json' } });
    assert.equal((await call(method, path, malformed)).status, 422);
    const wrongType = new Request('http://localhost/api/backend/issuing-units', { method, body: '{}' });
    assert.equal((await call(method, path, wrongType)).status, 415);
  }
  assert.equal(calls.length, 0);
});

test('Unit proxy preserves authorization, missing record, duplicate code, and validation errors', async () => {
  for (const [method, path] of endpoints) {
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

test('Unit network failures return 503 without repeating mutations', async () => {
  for (const [method, path] of endpoints) {
    const { call, calls } = proxy({ failure: true });
    assert.equal((await call(method, path)).status, 503);
    assert.equal(calls.length, 1);
  }
});

test('Unit client forwards filters, abort signal, IDs, and payloads to issuing-unit endpoints', async () => {
  const calls = [];
  const response = { data: record };
  const api = Object.fromEntries(['get', 'post', 'patch'].map((method) => [method, async (...args) => {
    calls.push([method, ...args]); return { data: response };
  }]));
  const client = loadModule('apis/issuingUnitApis.ts', {
    '@/axios': { __esModule: true, default: api }, '@/routes': { API_ROUTES: { issuingUnits: '/backend/issuing-units' } },
  });
  const signal = new AbortController().signal;
  const params = { page: 2, itemsPerPage: 20, search: 'PDT', is_active: false };
  assert.equal(await client.listIssuingUnits(params, signal), response);
  assert.equal(calls[0][1], '/backend/issuing-units');
  assert.equal(calls[0][2].params, params);
  assert.equal(calls[0][2].signal, signal);
  assert.equal(await client.getIssuingUnit(8, signal), response);
  assert.equal(calls[1][1], '/backend/issuing-units/8');
  assert.equal(calls[1][2].signal, signal);
  const payload = form.issuingUnitPayload(record);
  assert.equal(await client.createIssuingUnit(payload), response);
  assert.deepEqual(calls[2], ['post', '/backend/issuing-units', payload]);
  const changes = { is_active: false, description: null };
  assert.equal(await client.updateIssuingUnit(8, changes), response);
  assert.deepEqual(calls[3], ['patch', '/backend/issuing-units/8', changes]);
});
