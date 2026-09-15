export function tokenExpiryMs(token, nowMs = Date.now()) {
  try {
    const parts = String(token || '').split('.');
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')));
    const expiry = Number(payload.exp) * 1000;
    return Number.isFinite(expiry) && expiry > nowMs ? expiry : null;
  } catch {
    return null;
  }
}

export function clearStoredSession(storage = localStorage) {
  storage.removeItem('marka_token');
  storage.removeItem('marka_credits');
}

export function readUsableToken(storage = localStorage, nowMs = Date.now()) {
  const token = storage.getItem('marka_token');
  if (token && tokenExpiryMs(token, nowMs)) return token;
  if (token) clearStoredSession(storage);
  return null;
}

export async function authenticatedFetch(fetchImpl, url, options, token, onUnauthorized) {
  const response = await fetchImpl(url, {
    ...options,
    headers: {
      ...(options?.headers || {}),
      Authorization: `Bearer ${token}`,
    },
  });
  if (response.status === 401) onUnauthorized();
  return response;
}
