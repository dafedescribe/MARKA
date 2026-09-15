import test from 'node:test';
import assert from 'node:assert/strict';

import {
  authenticatedFetch,
  readUsableToken,
  tokenExpiryMs,
} from './session.js';

const encode = (value) => Buffer.from(JSON.stringify(value)).toString('base64url');
const jwt = (payload) => `${encode({ alg: 'HS256' })}.${encode(payload)}.signature`;

test('tokenExpiryMs accepts only a future numeric expiry', () => {
  assert.equal(tokenExpiryMs(jwt({ exp: 200 }), 100_000), 200_000);
  assert.equal(tokenExpiryMs(jwt({ exp: 100 }), 100_000), null);
  assert.equal(tokenExpiryMs('not-a-jwt', 100_000), null);
});

test('readUsableToken clears an expired stored session', () => {
  const removed = [];
  const storage = {
    getItem: () => jwt({ exp: 100 }),
    removeItem: (key) => removed.push(key),
  };

  assert.equal(readUsableToken(storage, 100_000), null);
  assert.deepEqual(removed, ['marka_token', 'marka_credits']);
});

test('authenticatedFetch clears auth on 401', async () => {
  let loggedOut = false;
  const response = await authenticatedFetch(
    async (_url, options) => {
      assert.equal(options.headers.Authorization, 'Bearer token');
      return { status: 401 };
    },
    '/private',
    {},
    'token',
    () => { loggedOut = true; },
  );

  assert.equal(response.status, 401);
  assert.equal(loggedOut, true);
});
