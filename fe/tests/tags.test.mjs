import assert from 'node:assert/strict';
import test from 'node:test';
import { loadModule } from './helpers/load-typescript.mjs';

const plain = (value) => JSON.parse(JSON.stringify(value));
const form = loadModule('ultis/tagForm.ts');
const record = { id: 9, name: 'Đào tạo', slug: 'dao-tao', created_at: '2026-10-26T00:00:00Z' };
const endpoints = [['GET', 'tags'], ['GET', 'tags/9'], ['POST', 'tags'], ['PATCH', 'tags/9']];

test('Active Admin and Staff accounts can manage tags, but students and inactive accounts cannot', () => {
  for (const roles of [['ADMIN'], ['STAFF'], ['STUDENT', 'STAFF']]) {
    assert.equal(form.canManageTags({ is_active: true, roles }), true);
    assert.equal(form.canManageTags({ is_active: false, roles }), false);
  }
  for (const roles of [[], ['STUDENT']]) assert.equal(form.canManageTags({ is_active: true, roles }), false);
});

test('Tag payload trims user input and excludes unsupported or server-controlled fields', () => {
  assert.deepEqual(plain(form.tagPayload({ ...record, name: ' Đào tạo ', slug: ' dao-tao ', code: 'DT', description: 'Ignored', is_active: false })), {
    name: 'Đào tạo', slug: 'dao-tao',
  });
});

test('Renaming a tag preserves its existing slug, while explicit slug changes are sent', () => {
  assert.deepEqual(plain(form.tagChanges({ ...record, name: ' Đào tạo ' }, record)), {});
  assert.deepEqual(plain(form.tagChanges({ ...record, name: ' Học vụ ' }, record)), { name: 'Học vụ' });
  assert.deepEqual(plain(form.tagChanges({ ...record, slug: ' hoc-vu ' }, record)), { slug: 'hoc-vu' });
});

test('Slug suggestions handle Vietnamese accents, Đ, punctuation, spacing, and numbers', () => {
  for (const [name, expected] of [
    ['  Đào tạo & Tuyển sinh 2026  ', 'dao-tao-tuyen-sinh-2026'],
    ['QUY ĐỊNH – HỌC PHÍ', 'quy-dinh-hoc-phi'],
    ['  ---Đoàn___Hội!!! ', 'doan-hoi'],
    ['ĐÀO TẠO'.normalize('NFD'), 'dao-tao'],
    ['A  B', 'a-b'],
  ]) {
    const slug = form.tagSlugFromName(name);
    assert.equal(slug, expected);
    assert.equal(form.TAG_SLUG_PATTERN.test(slug), true);
  }
});

test('Slug suggestions remain within 120 characters and never add trailing hyphens', () => {
  for (const name of ['a'.repeat(121), `${'a'.repeat(119)} b`, `-${'b'.repeat(121)}-`]) {
    const slug = form.tagSlugFromName(name);
    assert.ok(slug.length <= 120);
    assert.equal(form.TAG_SLUG_PATTERN.test(slug), true);
  }
  for (const name of ['', '   ', '!!!', '🎓']) assert.equal(form.tagSlugFromName(name), '');
});

test('Slug validation rejects unsupported syntax instead of silently rewriting manually supplied slugs', () => {
  for (const slug of ['', 'Đào-tạo', 'DAO-TAO', 'dao_tao', 'dao tao', '-dao', 'dao-', 'dao--tao', 'dao/tao']) {
    assert.equal(form.TAG_SLUG_PATTERN.test(slug), false);
  }
  assert.equal(form.tagPayload({ name: 'Đào tạo', slug: ' DAO-TAO ' }).slug, 'DAO-TAO');
});

function proxy({ token = 'session-token', origin = true, status = 200, failure = false, body } = {}) {
  const calls = [];
  const payload = body ?? (status >= 400 ? { message: 'Backend error' } : { data: record });
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

function jsonRequest(method, body = { name: 'Đào tạo', slug: 'dao-tao' }) {
  if (method === 'GET') return { nextUrl: new URL('http://localhost/api/backend/tags') };
  return new Request('http://localhost/api/backend/tags', {
    method, body: JSON.stringify(body), headers: { 'Content-Type': 'application/json; charset=utf-8' },
  });
}

test('Tag list forwards pagination/search, preserves pagination metadata, and does not cache', async () => {
  const { call, calls, payload } = proxy({ body: { data: [record], meta: { page: 2, itemsPerPage: 20, total: 21, totalPages: 2 } } });
  const query = '?page=2&itemsPerPage=20&search=dao-tao';
  const response = await call('GET', 'tags', { nextUrl: new URL(`http://localhost/api/backend/tags${query}`) });
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), payload);
  assert.match(response.headers.get('cache-control'), /no-store/);
  assert.equal(calls[0][0], `/tags${query}`);
  assert.equal(calls[0][2], 'session-token');
});

test('Tag detail forwards the selected ID and returns the backend record', async () => {
  const { call, calls, payload } = proxy();
  const response = await call('GET', 'tags/9');
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), payload);
  assert.equal(calls[0][0], '/tags/9');
});

test('Tag creation and updates forward the correct body, session, method, and status', async () => {
  for (const [method, path, status] of [['POST', 'tags', 201], ['PATCH', 'tags/9', 200]]) {
    const { call, calls, payload } = proxy({ status });
    const body = method === 'POST' ? form.tagPayload(record) : { name: 'Học vụ' };
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

test('Tag endpoints require a session and same-origin mutations', async () => {
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

test('Tag allowlist excludes deletion, archive, invalid IDs, and unrelated mutations', async () => {
  const { call, calls } = proxy();
  for (const method of ['GET', 'PATCH']) {
    for (const suffix of ['0', '-1', 'abc', '9/archive', '9/extra']) assert.equal((await call(method, `tags/${suffix}`)).status, 404);
  }
  for (const [method, path] of [['POST', 'tags/9'], ['PATCH', 'tags'], ['DELETE', 'tags/9'], ['POST', 'users'], ['PATCH', 'users/9']]) {
    assert.equal((await call(method, path)).status, 404);
  }
  assert.equal(calls.length, 0);
});

test('Tag mutations reject malformed and non-JSON payloads without upstream calls', async () => {
  const { call, calls } = proxy();
  for (const [method, path] of endpoints.filter(([method]) => method !== 'GET')) {
    for (const body of [null, [], 'text']) assert.equal((await call(method, path, jsonRequest(method, body))).status, 422);
    const malformed = new Request('http://localhost/api/backend/tags', { method, body: '{bad', headers: { 'Content-Type': 'application/json' } });
    assert.equal((await call(method, path, malformed)).status, 422);
    const wrongType = new Request('http://localhost/api/backend/tags', { method, body: '{}' });
    assert.equal((await call(method, path, wrongType)).status, 415);
  }
  assert.equal(calls.length, 0);
});

test('Tag proxy preserves duplicate-slug, validation, authorization, and missing-record errors', async () => {
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

test('Tag network failures return 503 without repeating mutations', async () => {
  for (const [method, path] of endpoints) {
    const { call, calls } = proxy({ failure: true });
    assert.equal((await call(method, path)).status, 503);
    assert.equal(calls.length, 1);
  }
});

test('Tag client forwards search, pagination, cancellation, IDs, and create/update payloads', async () => {
  const calls = [];
  const response = { data: record };
  const api = Object.fromEntries(['get', 'post', 'patch'].map((method) => [method, async (...args) => {
    calls.push([method, ...args]); return { data: response };
  }]));
  const client = loadModule('apis/tagApis.ts', {
    '@/axios': { __esModule: true, default: api }, '@/routes': { API_ROUTES: { tags: '/backend/tags' } },
  });
  const signal = new AbortController().signal;
  const params = { page: 2, itemsPerPage: 20, search: 'dao-tao' };
  assert.equal(await client.listTags(params, signal), response);
  assert.equal(calls[0][1], '/backend/tags');
  assert.equal(calls[0][2].params, params);
  assert.equal(calls[0][2].signal, signal);
  assert.equal(await client.getTag(9, signal), response);
  assert.equal(calls[1][1], '/backend/tags/9');
  assert.equal(calls[1][2].signal, signal);
  const payload = form.tagPayload(record);
  assert.equal(await client.createTag(payload), response);
  assert.deepEqual(calls[2], ['post', '/backend/tags', payload]);
  const changes = { name: 'Học vụ' };
  assert.equal(await client.updateTag(9, changes), response);
  assert.deepEqual(calls[3], ['patch', '/backend/tags/9', changes]);
});
