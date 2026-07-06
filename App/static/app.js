async function apiFetch(path, options = {}) {
  const apiKey = localStorage.getItem('apiKey');
  const headers = Object.assign(
    { 'Content-Type': 'application/json' },
    apiKey ? { 'X-API-Key': apiKey } : {},
    options.headers || {}
  );
  const response = await fetch(path, Object.assign({}, options, { headers }));
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail ? JSON.stringify(data.detail) : `HTTP ${response.status}`);
  }
  return data;
}
