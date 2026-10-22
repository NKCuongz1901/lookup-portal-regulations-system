import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import test from 'node:test';

// Run only against the disposable API started by serve_backend.py.
const base = process.env.TEST_APP_URL || 'http://127.0.0.1:3100';
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname));
const endpoint = `${base}/api/backend/documents`;
async function session(role) {
  const response = await fetch(`${base}/api/auth/login`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', Origin: base },
    body: JSON.stringify({ email: `test-${role}@example.com`, password: 'Regula-test-only-2026!' }),
  });
  assert.equal(response.status, 200);
  return { Cookie: response.headers.get('set-cookie').split(';')[0], Origin: base, 'Content-Type': 'application/json' };
}

for (const role of ['admin', 'staff']) {
  test(`${role} creates a draft with metadata and sees it in the list`, async () => {
    const headers = await session(role);
    const [types, units, tags] = await Promise.all(['document-types?is_active=true', 'issuing-units?is_active=true', 'tags'].map(async (path) => {
      const response = await fetch(`${base}/api/backend/${path}`, { headers });
      assert.equal(response.status, 200);
      return (await response.json()).data;
    }));
    assert.ok(types.every((type) => type.is_active));
    const code = `FE-${randomUUID()}`;
    const payload = {
      code, title: 'Văn bản tạo từ FE', description: 'Nội dung kiểm thử',
      document_type_id: types[0].id, issuing_unit_id: units[0].id,
      issue_date: '2026-10-22', effective_from: '2026-11-01', effective_until: '2027-06-30',
      academic_year: '2026-2027', applicable_subject_codes: ['STUDENT'], tag_ids: [tags[0].id],
    };
    const response = await fetch(endpoint, { method: 'POST', headers, body: JSON.stringify(payload) });
    assert.equal(response.status, 201);
    assert.match(response.headers.get('cache-control'), /no-store/);
    const created = (await response.json()).data;
    assert.equal(created.publication_status, 'draft');
    assert.equal(created.document_type_id, types[0].id);
    assert.equal(created.issuing_unit_id, units[0].id);
    assert.equal(created.effective_until, payload.effective_until);
    assert.deepEqual(created.applicable_subject_codes, ['STUDENT']);
    assert.equal(created.tags[0].id, tags[0].id);
    const listing = await fetch(`${endpoint}?search=${code}`, { headers });
    assert.equal((await listing.json()).data[0].id, created.id);
    const duplicate = await fetch(endpoint, { method: 'POST', headers, body: JSON.stringify(payload) });
    assert.equal(duplicate.status, 409);
    assert.equal((await duplicate.json()).message, 'Document code already exists');
  });
}

test('Create proxy preserves backend validation and limits mutations to documents', async () => {
  const headers = await session('staff');
  for (const payload of [
    {}, { code: ' ', title: 'Missing code' },
    { code: 'BAD-DATE', title: 'Bad dates', effective_from: '2027-01-01', effective_until: '2026-01-01' },
    { code: 'BAD-REF', title: 'Bad reference', document_type_id: 999999 },
    { code: 'PUBLISHED', title: 'Read only status', publication_status: 'published' },
  ]) {
    const response = await fetch(endpoint, { method: 'POST', headers, body: JSON.stringify(payload) });
    assert.equal(response.status, 422);
  }
  assert.equal((await fetch(endpoint, { method: 'POST', headers, body: '{invalid' })).status, 422);
  assert.equal((await fetch(endpoint, { method: 'POST', headers: { ...headers, 'Content-Type': 'text/plain' }, body: '{}' })).status, 415);
  assert.equal((await fetch(`${base}/api/backend/users`, { method: 'POST', headers, body: '{}' })).status, 404);
  assert.equal((await fetch(endpoint, { method: 'POST', headers: { ...headers, Origin: 'https://untrusted.example' }, body: '{}' })).status, 403);
  assert.equal((await fetch(endpoint, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })).status, 401);
  const expired = await fetch(endpoint, { method: 'POST', headers: { ...headers, Cookie: 'regula_session=invalid' }, body: '{}' });
  assert.equal(expired.status, 401);
  assert.match(expired.headers.get('set-cookie'), /Max-Age=0/);
});
