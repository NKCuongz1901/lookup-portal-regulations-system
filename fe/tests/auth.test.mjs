import assert from 'node:assert/strict';
import test from 'node:test';

// This suite targets only the disposable local API started by serve_backend.py.
const base = process.env.TEST_APP_URL || 'http://127.0.0.1:3100';
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname));
const password = 'Regula-test-only-2026!';
const signIn = (role, overrides = {}) => fetch(`${base}/api/auth/login`, {
  method: 'POST', headers: { 'Content-Type': 'application/json', Origin: base },
  body: JSON.stringify({ email: `test-${role}@example.com`, password, remember: true, ...overrides }),
});

test('Unauthenticated requests cannot read management data', async () => {
  assert.equal((await fetch(`${base}/api/auth/session`)).status, 401);
  assert.equal((await fetch(`${base}/api/backend/documents`)).status, 401);
  const response = await fetch(`${base}/dashboard`);
  assert.ok(response.url.endsWith('/login') || (await response.text()).includes('/login'));
});

for (const role of ['admin', 'staff']) {
  test(`${role} signs in, loads the dashboard and signs out`, async () => {
    const login = await signIn(role);
    assert.equal(login.status, 200);
    const setCookie = login.headers.get('set-cookie');
    assert.match(setCookie, /HttpOnly/i);
    assert.match(setCookie, /SameSite=lax/i);
    assert.match(setCookie, /Max-Age=/i);
    const cookie = setCookie.split(';')[0];
    const payload = await login.json();
    assert.equal(payload.data.roles.includes(role.toUpperCase()), true);
    assert.equal(payload.data.access_token, undefined);
    const headers = { Cookie: cookie };
    assert.equal((await fetch(`${base}/api/auth/session`, { headers })).status, 200);
    const dashboard = await fetch(`${base}/dashboard`, { headers });
    assert.equal(dashboard.status, 200);
    assert.match(await dashboard.text(), /Tổng quan/);
    for (const resource of ['users', 'documents', 'documents/1']) {
      const response = await fetch(`${base}/api/backend/${resource}`, { headers });
      assert.equal(response.status, 200);
      assert.ok((await response.json()).data);
    }
    const logout = await fetch(`${base}/api/auth/logout`, { method: 'POST', headers: { ...headers, Origin: base } });
    assert.equal(logout.status, 200);
    assert.match(logout.headers.get('set-cookie'), /Max-Age=0/i);
  });
}

test('Student, wrong password and malformed login are rejected', async () => {
  const student = await signIn('student');
  assert.equal(student.status, 403);
  assert.match(student.headers.get('set-cookie'), /Max-Age=0/i);
  assert.equal((await signIn('admin', { password: 'wrong' })).status, 401);
  assert.equal((await signIn('admin', { email: '' })).status, 422);
});

test('Remember off uses a session cookie and external origins cannot change the session', async () => {
  const response = await signIn('staff', { remember: false });
  assert.equal(response.status, 200);
  assert.doesNotMatch(response.headers.get('set-cookie'), /Max-Age=/i);
  for (const path of ['login', 'logout']) {
    const denied = await fetch(`${base}/api/auth/${path}`, {
      method: 'POST', headers: { Origin: 'https://untrusted.example', 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'test-admin@example.com', password }),
    });
    assert.equal(denied.status, 403);
  }
  assert.equal((await fetch(`${base}/api/backend/auth/me`)).status, 404);
});

test('Expired or invalid sessions are cleared', async () => {
  const response = await fetch(`${base}/api/auth/session`, { headers: { Cookie: 'regula_session=invalid' } });
  assert.equal(response.status, 401);
  assert.match(response.headers.get('set-cookie'), /Max-Age=0/i);
});
