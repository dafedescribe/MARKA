import test from 'node:test';
import assert from 'node:assert/strict';

let warmApi;
try {
  ({ warmApi } = await import('./apiWarmup.js'));
} catch {
  warmApi = undefined;
}

test('warmApi makes one credential-free health request per browser session', () => {
  const calls = [];
  const storage = new Map();
  const sessionStorage = {
    getItem: (key) => storage.get(key) || null,
    setItem: (key, value) => storage.set(key, value),
  };
  const fetcher = (url, options) => {
    calls.push({ url, options });
    return Promise.resolve();
  };

  assert.equal(typeof warmApi, 'function');
  warmApi('https://api.marka.com', { fetcher, sessionStorage });
  warmApi('https://api.marka.com', { fetcher, sessionStorage });

  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, 'https://api.marka.com/health');
  assert.deepEqual(calls[0].options, {
    method: 'GET',
    credentials: 'omit',
    cache: 'no-store',
    referrerPolicy: 'no-referrer',
  });
});
