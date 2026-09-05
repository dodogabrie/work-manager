/* Client REST. Sottile di proposito: nessuna regola di planning vive qui —
   il frontend è un client dell'application layer come Claude (§29). */

const BASE = import.meta.env.VITE_API_BASE ?? ''

export class ApiError extends Error {
  constructor(readonly status: number, message: string, readonly detail?: unknown) {
    super(message)
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}/api${path}`, {
    method,
    credentials: 'include',           // la sessione owner è un cookie HttpOnly
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (res.status === 401) {
    throw new ApiError(401, 'Sessione scaduta')
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => undefined)
    throw new ApiError(res.status, detail?.detail ?? res.statusText, detail)
  }
  return res.status === 204 ? (undefined as T) : res.json()
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  del: <T>(path: string) => request<T>('DELETE', path),
}
