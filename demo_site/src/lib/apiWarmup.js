const WARMUP_KEY = 'marka_api_warmed';

export function warmApi(apiUrl, {
  fetcher = fetch,
  sessionStorage = window.sessionStorage,
} = {}) {
  if (!apiUrl || sessionStorage.getItem(WARMUP_KEY)) return;
  sessionStorage.setItem(WARMUP_KEY, '1');
  fetcher(`${apiUrl.replace(/\/$/, '')}/health`, {
    method: 'GET',
    credentials: 'omit',
    cache: 'no-store',
    referrerPolicy: 'no-referrer',
  }).catch(() => {});
}
