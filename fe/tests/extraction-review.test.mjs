import assert from 'node:assert/strict';
import test from 'node:test';
import { loadModule } from './helpers/load-typescript.mjs';

const utils = loadModule('ultis/extractionReview.ts');
test('Evidence offsets use Python code points including non-BMP characters', () => {
  const result = utils.evidenceParts({ segment_content_snapshot: '📄 Hạn nộp 15/12/2026.', start_offset: 10, end_offset: 20, quote: '15/12/2026' });
  assert.equal(result.before, '📄 Hạn nộp ');
  assert.equal(result.quote, '15/12/2026');
  assert.equal(result.after, '.');
  assert.equal(utils.evidenceParts({ segment_content_snapshot: 'abc', start_offset: 0, end_offset: 2, quote: 'no' }), null);
});
test('Human corrections take precedence without modifying original deadline JSON', () => {
  const field = { field_key: 'deadline', raw_value: 'trước ngày 15/12/2026', normalized_value: { date: '2026-12-15' }, reviewed_value: null };
  assert.equal(utils.fieldDisplayValue(field), '15/12/2026');
  assert.equal(utils.fieldDisplayValue({ ...field, reviewed_value: '<script>literal text</script>' }), '<script>literal text</script>');
  assert.equal(field.normalized_value.date, '2026-12-15');
});

function proxy({ token = 'session', origin = true, status = 200 } = {}) {
  const calls = [];
  const route = loadModule('app/api/backend/[...path]/route.ts', {
    '@/ultis/documentUpload': {}, '@/ultis/serverUpload': {},
    'next/headers': { cookies: async () => ({ get: () => token ? { value: token } : undefined }) },
    '@/ultis/serverSession': {
      SESSION_COOKIE: 'regula_session', sameOrigin: () => origin,
      apiError: (status, message) => Response.json({ message }, { status }),
      jsonResponse: (body, status) => Response.json(body, { status }), clearSession: (response) => response,
      backendFetch: async (...args) => { calls.push(args); return Response.json({ data: { id: 9 } }, { status }); },
    },
  });
  return { calls, route };
}
const context = (path) => ({ params: Promise.resolve({ path: path.split('/') }) });
for (const path of ['document-versions/7/extraction-runs', 'extraction-runs/9', 'extraction-runs/9/fields', 'extracted-fields/12/reviews']) {
  test(`Authenticated extraction read: ${path}`, async () => {
    const { route, calls } = proxy();
    const response = await route.GET({ nextUrl: new URL(`http://localhost/api/backend/${path}?page=2`) }, context(path));
    assert.equal(response.status, 200);
    assert.equal(calls[0][0], `/${path}?page=2`);
    assert.equal(calls[0][2], 'session');
    assert.equal((await proxy({ token: null }).route.GET({}, context(path))).status, 401);
  });
}
for (const path of ['document-versions/7/extraction-runs', 'extraction-runs/9/retry', 'extracted-fields/12/reviews']) {
  test(`Mutations enforce origin and forward JSON: ${path}`, async () => {
    const { route, calls } = proxy({ status: 409 });
    const payload = { action: 'approve', expected_revision: 1, idempotency_key: 'same-key' };
    const response = await route.POST({ headers: new Headers({ 'Content-Type': 'application/json' }), json: async () => payload }, context(path));
    assert.equal(response.status, 409);
    assert.deepEqual(JSON.parse(calls[0][1].body), payload);
    assert.equal((await proxy({ origin: false }).route.POST({}, context(path))).status, 403);
    assert.equal((await proxy({ token: null }).route.POST({}, context(path))).status, 401);
  });
}
test('Unrelated extraction paths remain blocked', async () => {
  const { route, calls } = proxy();
  for (const path of ['extraction-runs', 'extraction-runs/1/delete', 'extracted-fields/0/reviews', 'extracted-fields/1/approve']) {
    assert.equal((await route.GET({}, context(path))).status, 404);
    assert.equal((await route.POST({}, context(path))).status, 404);
  }
  assert.equal(calls.length, 0);
});

function pdfProxy({ token = 'session', status = 200, url = 'https://test.r2.cloudflarestorage.com/file?signed=1', mime = 'application/pdf', version = 7 } = {}) {
  const calls = [];
  const route = loadModule('app/api/documents/[documentId]/versions/[versionId]/pdf/route.ts', {
    'next/headers': { cookies: async () => ({ get: () => token ? { value: token } : undefined }) },
    '@/ultis/documentUpload': { DOCUMENT_MAX_FILE_SIZE: 20 * 1024 * 1024 },
    '@/ultis/serverSession': {
      SESSION_COOKIE: 'regula_session', apiError: (status, message) => Response.json({ message }, { status }),
      jsonResponse: (data, status) => Response.json(data, { status }), clearSession: (response) => response,
      backendFetch: async (...args) => { calls.push(args); return Response.json({ data: { document_id: 3, version_id: version, mime_type: mime, url, size_bytes: 10 } }, { status }); },
    },
  }, { Response, AbortSignal, fetch: async (...args) => { calls.push(args); return new Response('%PDF-test', { headers: { 'Content-Type': 'application/pdf' } }); } });
  return { calls, route };
}
const pdfContext = { params: Promise.resolve({ documentId: '3', versionId: '7' }) };
const pdfRequest = () => ({ signal: new AbortController().signal });
test('PDF proxy streams the authorized exact version and never forwards JWT to R2', async () => {
  const { route, calls } = pdfProxy();
  const response = await route.GET(pdfRequest(), pdfContext);
  assert.equal(await response.text(), '%PDF-test');
  assert.equal(calls[0][0], '/documents/3/download-url?version_id=7');
  assert.equal(calls[0][2], 'session');
  assert.equal(calls[1][1].headers, undefined);
  assert.equal(calls[1][1].redirect, 'error');
  assert.match(response.headers.get('cache-control'), /no-store/);
  assert.equal(response.headers.get('content-disposition'), 'inline');
});
for (const [options, expected] of [
  [{ token: null }, 401], [{ status: 403 }, 403], [{ status: 404 }, 404], [{ mime: 'text/html' }, 415],
  [{ version: 8 }, 502], [{ url: 'http://localhost/secret' }, 502],
  [{ url: 'https://evil.test/file' }, 502], [{ url: 'https://test.r2.cloudflarestorage.com.evil.test/file' }, 502],
  [{ url: 'https://user:password@test.r2.cloudflarestorage.com/file' }, 502],
]) {
  test(`PDF proxy rejects invalid/unauthorized input ${JSON.stringify(options)}`, async () => {
    const { route, calls } = pdfProxy(options);
    assert.equal((await route.GET(pdfRequest(), pdfContext)).status, expected);
    assert.ok(calls.length <= 1);
  });
}
