import assert from 'node:assert/strict';
import test from 'node:test';
import { loadModule } from './helpers/load-typescript.mjs';

const config = loadModule('ultis/documentUpload.ts');
const upload = loadModule('ultis/serverUpload.ts', {
  'server-only': {}, './documentUpload': config,
}, { Response, Blob, File, FormData });
const { DOCUMENT_MAX_FILE_SIZE: maxSize } = config;
const sample = new File(['%PDF-1.7\nTest document'], 'Quy chế đào tạo.PDF', { type: 'application/pdf' });
const url = 'http://localhost/api/backend/documents/12/versions';

function formRequest(file = sample, change = () => {}) {
  const body = new FormData();
  if (file !== null) body.append('file', file);
  change(body);
  return new Request(url, { method: 'POST', body });
}

test('File picker validation accepts PDF/DOCX and the exact 20 MB boundary', () => {
  for (const name of ['quy-che.pdf', 'QUY CHE.DOCX']) {
    assert.equal(config.documentFileError({ name, size: maxSize }), null);
  }
  for (const file of [
    { name: 'file.pdf', size: 0 }, { name: 'file.docx', size: maxSize + 1 },
    { name: 'file.exe', size: 10 }, { name: '', size: 10 },
    { name: `${'a'.repeat(500)}.pdf`, size: 10 },
  ]) assert.equal(typeof config.documentFileError(file), 'string');
});

test('Multipart parsing preserves file contents, MIME type, and Vietnamese filename', async () => {
  const body = await upload.readDocumentUpload(formRequest());
  assert.deepEqual([...body.keys()], ['file']);
  const file = body.get('file');
  assert.equal(file.name, sample.name);
  assert.equal(file.type, sample.type);
  assert.equal(await file.text(), await sample.text());
});

test('Missing or unhelpful client MIME types do not reject valid file extensions', async () => {
  const body = await upload.readDocumentUpload(formRequest(new File(['%PDF-1.7'], 'file.pdf')));
  assert.equal(body.get('file').name, 'file.pdf');
});

for (const [label, file, change] of [
  ['missing file', null, () => {}],
  ['string instead of file', null, (body) => body.append('file', 'text')],
  ['multiple files', sample, (body) => body.append('file', sample)],
  ['unexpected fields', sample, (body) => body.append('document_id', '99')],
  ['empty file', new File([], 'empty.pdf'), () => {}],
  ['unsupported file', new File(['text'], 'file.txt'), () => {}],
]) {
  test(`Multipart validation rejects ${label}`, async () => {
    await assert.rejects(upload.readDocumentUpload(formRequest(file, change)), { status: 422 });
  });
}

test('Wrong content type and malformed multipart bodies return validation errors', async () => {
  await assert.rejects(upload.readDocumentUpload(new Request(url, { method: 'POST', body: '{}' })), { status: 415 });
  await assert.rejects(upload.readDocumentUpload(new Request(url, {
    method: 'POST', body: 'broken', headers: { 'Content-Type': 'multipart/form-data; boundary=missing' },
  })), { status: 422 });
});

test('Oversized Content-Length is rejected before reading the body', async () => {
  const request = {
    headers: new Headers({ 'Content-Type': 'multipart/form-data; boundary=test', 'Content-Length': String(maxSize + 65537) }),
    get body() { assert.fail('Should not read an oversized body'); },
  };
  await assert.rejects(upload.readDocumentUpload(request), { status: 413 });
});

test('Chunked requests cannot bypass the body limit and cancel the stream on overflow', async () => {
  let cancelled = false;
  const chunk = new Uint8Array(1024 * 1024);
  const body = new ReadableStream({
    pull(controller) { controller.enqueue(chunk); },
    cancel() { cancelled = true; },
  });
  await assert.rejects(upload.readDocumentUpload({
    headers: new Headers({ 'Content-Type': 'multipart/form-data; boundary=test' }), body,
  }), { status: 413 });
  assert.ok(cancelled);
});

test('File size limit applies separately from the multipart overhead allowance', async () => {
  const file = new File([new Uint8Array(maxSize + 1)], 'large.pdf');
  await assert.rejects(upload.readDocumentUpload(formRequest(file)), { status: 413 });
});

function proxy({ token = 'session-token', origin = true, status = 201, failure } = {}) {
  const calls = [];
  const payload = { data: { id: 35, version_number: 2, is_current: true } };
  const route = loadModule('app/api/backend/[...path]/route.ts', {
    'next/headers': { cookies: async () => ({ get: () => token ? { value: token } : undefined }) },
    '@/ultis/documentUpload': config,
    '@/ultis/serverUpload': upload,
    '@/ultis/serverSession': {
      SESSION_COOKIE: 'regula_session',
      sameOrigin: () => origin,
      apiError: (code, message) => Response.json({ message }, { status: code }),
      jsonResponse: (data, code) => Response.json(data, { status: code, headers: { 'Cache-Control': 'private, no-store' } }),
      clearSession(response) { response.headers.set('Set-Cookie', 'regula_session=; Max-Age=0'); return response; },
      backendFetch: async (...args) => {
        calls.push(args);
        if (failure) throw failure;
        return Response.json(payload, { status });
      },
    },
  }, { AbortSignal, Error });
  const post = (request = formRequest(), path = ['documents', '12', 'versions']) => route.POST(request, { params: Promise.resolve({ path }) });
  return { calls, post, payload };
}

test('Upload proxy sends one multipart file with server session and preserves 201 response', async () => {
  const { calls, post, payload } = proxy();
  const result = await post();
  assert.equal(result.status, 201);
  assert.deepEqual(await result.json(), payload);
  assert.match(result.headers.get('cache-control'), /no-store/);
  assert.equal(calls.length, 1);
  const [path, init, token] = calls[0];
  assert.equal(path, '/documents/12/versions');
  assert.equal(init.method, 'POST');
  assert.equal(token, 'session-token');
  assert.ok(init.signal instanceof AbortSignal);
  assert.equal(await init.body.get('file').text(), await sample.text());
});

test('Proxy rejects unauthenticated, cross-origin, and disallowed requests before reading files', async () => {
  for (const [options, status, path] of [
    [{ token: null }, 401], [{ origin: false }, 403],
    [{}, 404, ['documents', '12', 'versions', '35']],
  ]) {
    const { calls, post } = proxy(options);
    const result = await post({ get body() { assert.fail('Body must not be read'); } }, path);
    assert.equal(result.status, status);
    assert.equal(calls.length, 0);
  }
});

test('Invalid multipart requests are not sent upstream', async () => {
  const { calls, post } = proxy();
  assert.equal((await post(formRequest(null))).status, 422);
  assert.equal(calls.length, 0);
});

test('Proxy preserves backend validation, authorization, and storage errors', async () => {
  for (const status of [401, 403, 404, 413, 422, 502]) {
    const { post, calls } = proxy({ status });
    const response = await post();
    assert.equal(response.status, status);
    assert.equal(calls.length, 1);
    if (status === 401) assert.match(response.headers.get('set-cookie'), /Max-Age=0/);
  }
});

test('Ambiguous network failures do not retry uploads and ask to refresh versions', async () => {
  for (const [failure, status] of [
    [Object.assign(new Error('Timed out'), { name: 'TimeoutError' }), 504],
    [new Error('Connection lost'), 503],
  ]) {
    const { post, calls } = proxy({ failure });
    const response = await post();
    assert.equal(response.status, status);
    assert.equal(calls.length, 1);
    assert.match((await response.json()).message, /Refresh versions before retrying/);
  }
});

test('JSON document creation still works through the shared proxy', async () => {
  const { calls, post } = proxy();
  const response = await post(new Request(url, {
    method: 'POST', body: JSON.stringify({ code: 'QD-01', title: 'Quy định' }),
    headers: { 'Content-Type': 'application/json' },
  }), ['documents']);
  assert.equal(response.status, 201);
  assert.equal(calls[0][0], '/documents');
  assert.deepEqual(JSON.parse(calls[0][1].body), { code: 'QD-01', title: 'Quy định' });
});

test('Backend fetch creates a matching multipart boundary and keeps JSON requests working', async () => {
  const calls = [];
  const session = loadModule('ultis/serverSession.ts', {
    'server-only': {}, 'next/headers': {}, 'next/server': {},
  }, {
    Headers, FormData, AbortSignal, process: { env: { BACKEND_API_URL: 'http://backend.test/api/v1' } },
    fetch: async (...args) => { calls.push(args); return Response.json({}); },
  });
  const body = new FormData(); body.append('file', sample);
  const signal = new AbortController().signal;
  await session.backendFetch('/documents/12/versions', {
    method: 'POST', body, signal, headers: { 'Content-Type': 'application/json' },
  }, 'server-token');
  const [url, init] = calls[0];
  assert.equal(url, 'http://backend.test/api/v1/documents/12/versions');
  assert.equal(init.headers.get('Content-Type'), null);
  assert.equal(init.headers.get('Authorization'), 'Bearer server-token');
  assert.equal(init.signal, signal);
  assert.equal(init.cache, 'no-store');
  const encoded = new Request(url, init);
  assert.match(encoded.headers.get('Content-Type'), /^multipart\/form-data; boundary=/);
  assert.equal(await (await encoded.formData()).get('file').text(), await sample.text());
  await session.backendFetch('/documents', { method: 'POST', body: '{}' }, 'server-token');
  assert.equal(calls[1][1].headers.get('Content-Type'), 'application/json');
});

test('Client uploads use multipart, a longer timeout, progress, and cancellation', async () => {
  const calls = [];
  const result = { data: { id: 35, version_number: 2 } };
  const client = loadModule('apis/documentApis.ts', {
    '@/axios': { __esModule: true, default: { post: async (...args) => { calls.push(args); return { data: result }; } } },
    '@/routes': { API_ROUTES: { documents: '/backend/documents' } },
    '@/ultis/documentUpload': config,
  }, { FormData });
  const signal = new AbortController().signal;
  const progress = [];
  assert.equal(await client.uploadDocumentVersion(12, sample, (value) => progress.push(value), signal), result);
  const [path, body, options] = calls[0];
  assert.equal(path, '/backend/documents/12/versions');
  assert.deepEqual([...body.keys()], ['file']);
  assert.equal(await body.get('file').text(), await sample.text());
  assert.equal(options.signal, signal);
  assert.ok(options.timeout > config.DOCUMENT_UPLOAD_TIMEOUT_MS);
  assert.equal(options.headers, undefined);
  options.onUploadProgress({ loaded: 5, total: 10 });
  options.onUploadProgress({ loaded: 11, total: 10 });
  options.onUploadProgress({ loaded: 5 });
  assert.deepEqual(progress, [50, 100]);
});
