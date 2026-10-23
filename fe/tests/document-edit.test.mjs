import assert from 'node:assert/strict';
import test from 'node:test';
import dayjs from 'dayjs';
import { loadModule } from './helpers/load-typescript.mjs';

const form = loadModule('ultis/documentForm.ts', { dayjs });
const plain = (value) => JSON.parse(JSON.stringify(value));
const original = {
  id: 12, code: 'QD-12', title: 'Quy chế đào tạo', description: 'Nội dung hiện tại',
  document_type_id: 2, issuing_unit_id: 3,
  document_type: { id: 2, name: 'Quy chế cũ', is_active: false },
  issuing_unit: { id: 3, name: 'Phòng đào tạo', is_active: true },
  issue_date: '2026-10-22', effective_from: '2026-11-01', effective_until: '2027-06-30',
  academic_year: '2026-2027', applicable_subject_codes: ['STUDENT', 'STAFF'],
  tags: [{ id: 4, name: 'Đào tạo', slug: 'dao-tao' }], publication_status: 'published',
  created_by: 1, updated_by: null, published_at: '2026-10-22T10:00:00Z',
};

test('Edit form pre-fills dates, relationships, subjects and tags', () => {
  const values = form.documentInitialValues(original);
  assert.equal(values.title, original.title);
  assert.equal(values.document_type_id, 2);
  assert.equal(values.issue_date.format('YYYY-MM-DD'), original.issue_date);
  assert.equal(values.effective_until.format('YYYY-MM-DD'), original.effective_until);
  assert.deepEqual(plain(values.tag_ids), [4]);
  assert.deepEqual(plain(values.applicable_subject_codes), ['STUDENT', 'STAFF']);
  assert.notEqual(values.applicable_subject_codes, original.applicable_subject_codes);
});

test('Unchanged forms produce no PATCH, including inactive metadata', () => {
  assert.deepEqual(plain(form.documentUpdatePayload(form.documentInitialValues(original), original)), {});
  const values = { ...form.documentInitialValues(original), title: 'Tên mới' };
  assert.deepEqual(plain(form.documentUpdatePayload(values, original)), { title: 'Tên mới' });
});

test('Cleared optional fields become null and cleared lists remain empty arrays', () => {
  const values = {
    ...form.documentInitialValues(original), description: ' ', academic_year: '',
    document_type_id: undefined, issuing_unit_id: null,
    issue_date: null, effective_from: null, effective_until: null,
    tag_ids: [], applicable_subject_codes: [],
  };
  assert.deepEqual(plain(form.documentUpdatePayload(values, original)), {
    description: null, academic_year: null, document_type_id: null, issuing_unit_id: null,
    issue_date: null, effective_from: null, effective_until: null,
    tag_ids: [], applicable_subject_codes: [],
  });
});

test('Form normalization trims input, deduplicates lists and excludes server-controlled fields', () => {
  const payload = form.documentFormPayload({
    ...form.documentInitialValues(original), code: ' QD-20 ', title: ' Tên mới ',
    applicable_subject_codes: [' STAFF ', '', 'STAFF'], tag_ids: [5, 5, 6],
    publication_status: 'archived', created_by: 99, id: 99,
  });
  assert.equal(payload.code, 'QD-20');
  assert.equal(payload.title, 'Tên mới');
  assert.deepEqual(plain(payload.applicable_subject_codes), ['STAFF']);
  assert.deepEqual(plain(payload.tag_ids), [5, 6]);
  for (const key of ['publication_status', 'created_by', 'id']) assert.equal(key in payload, false);
});

test('Changed dates preserve calendar days without UTC conversion', () => {
  const values = { ...form.documentInitialValues(original), issue_date: dayjs('2026-12-05') };
  assert.deepEqual(plain(form.documentUpdatePayload(values, original)), { issue_date: '2026-12-05' });
});

test('Current metadata stays visible when unavailable or inactive without duplicate IDs', () => {
  assert.deepEqual(plain(form.includeCurrentOptions(undefined, [original.document_type])), [original.document_type]);
  const current = { id: 3, name: 'Tên cũ' };
  const available = [{ id: 3, name: 'Tên mới' }, { id: 7, name: 'Loại mới' }];
  assert.deepEqual(plain(form.includeCurrentOptions(available, [current, original.document_type])), [...available, original.document_type]);
});

test('Create mode keeps empty initial lists and produces a valid metadata payload', () => {
  const values = { ...form.documentInitialValues(), code: 'QD-NEW', title: 'Văn bản mới' };
  const payload = form.documentFormPayload(values);
  assert.equal(payload.issue_date, null);
  assert.equal(payload.document_type_id, null);
  assert.deepEqual(plain(payload.tag_ids), []);
  assert.deepEqual(plain(payload.applicable_subject_codes), []);
});

function proxy({ token = 'session-token', origin = true, status = 200, failure = false } = {}) {
  const calls = [];
  const payload = { data: { ...original, title: 'Đã cập nhật' } };
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
  const patch = (request = jsonRequest(), path = 'documents/12') => route.PATCH(request, { params: Promise.resolve({ path: path.split('/') }) });
  return { calls, patch, payload };
}

function jsonRequest(body = { title: 'Đã cập nhật', description: null, tag_ids: [] }) {
  return new Request('http://localhost/api/backend/documents/12', {
    method: 'PATCH', body: JSON.stringify(body), headers: { 'Content-Type': 'application/json; charset=utf-8' },
  });
}

test('Edit proxy forwards PATCH with session, explicit nulls and empty lists', async () => {
  const { patch, calls, payload } = proxy();
  const response = await patch();
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), payload);
  assert.match(response.headers.get('cache-control'), /no-store/);
  assert.equal(calls[0][0], '/documents/12');
  assert.equal(calls[0][1].method, 'PATCH');
  assert.equal(calls[0][2], 'session-token');
  assert.deepEqual(JSON.parse(calls[0][1].body), { title: 'Đã cập nhật', description: null, tag_ids: [] });
});

test('Archive forwards a bodyless PATCH without reading or forwarding arbitrary payloads', async () => {
  const { patch, calls } = proxy();
  const response = await patch({ json: () => assert.fail('Archive must not read a JSON body') }, 'documents/12/archive');
  assert.equal(response.status, 200);
  assert.equal(calls[0][0], '/documents/12/archive');
  assert.equal(calls[0][1].method, 'PATCH');
  assert.equal(calls[0][1].body, undefined);
  assert.equal(calls[0][2], 'session-token');
});

test('Both edit and archive require a valid session and same-origin request', async () => {
  for (const path of ['documents/12', 'documents/12/archive']) {
    for (const [options, status] of [[{ token: null }, 401], [{ origin: false }, 403]]) {
      const { patch, calls } = proxy(options);
      assert.equal((await patch({}, path)).status, status);
      assert.equal(calls.length, 0);
    }
  }
});

test('Mutation allowlist excludes other resources, invalid IDs, and nested endpoints', async () => {
  const { patch, calls } = proxy();
  for (const path of ['documents', 'users/12', 'documents/0', 'documents/-1', 'documents/12/versions', 'documents/12/download-url', 'documents/12/archive/extra']) {
    assert.equal((await patch({}, path)).status, 404);
  }
  assert.equal(calls.length, 0);
});

test('Edit rejects malformed, non-object, and non-JSON payloads without calling BE', async () => {
  const { patch, calls } = proxy();
  for (const body of [null, [], 'text']) assert.equal((await patch(jsonRequest(body))).status, 422);
  const malformed = new Request('http://localhost/api/backend/documents/12', {
    method: 'PATCH', body: '{bad', headers: { 'Content-Type': 'application/json' },
  });
  assert.equal((await patch(malformed)).status, 422);
  const wrongType = new Request('http://localhost/api/backend/documents/12', { method: 'PATCH', body: '{}' });
  assert.equal((await patch(wrongType)).status, 415);
  assert.equal(calls.length, 0);
});

test('Backend authorization, missing document, duplicate code, and validation errors are preserved', async () => {
  for (const path of ['documents/12', 'documents/12/archive']) {
    for (const status of [401, 403, 404, 409, 422, 500]) {
      const { patch } = proxy({ status });
      const response = await patch(jsonRequest(), path);
      assert.equal(response.status, status);
      if (status === 401) assert.match(response.headers.get('set-cookie'), /Max-Age=0/);
    }
  }
});

test('Connection failures return 503 without silently retrying mutations', async () => {
  const { patch, calls } = proxy({ failure: true });
  assert.equal((await patch()).status, 503);
  assert.equal(calls.length, 1);
});

test('Client calls the document ID for edits and the archive endpoint with no body', async () => {
  const calls = [];
  const response = { data: original };
  const client = loadModule('apis/documentApis.ts', {
    '@/axios': { __esModule: true, default: { patch: async (...args) => { calls.push(args); return { data: response }; } } },
    '@/routes': { API_ROUTES: { documents: '/backend/documents' } }, '@/ultis/documentUpload': {},
  });
  const changes = { title: 'Đổi tên', description: null, tag_ids: [] };
  assert.equal(await client.updateDocument(12, changes), response);
  assert.equal(calls[0][0], '/backend/documents/12');
  assert.equal(calls[0][1], changes);
  assert.equal(await client.archiveDocument(12), response);
  assert.equal(calls[1][0], '/backend/documents/12/archive');
  assert.equal(calls[1].length, 1);
});
