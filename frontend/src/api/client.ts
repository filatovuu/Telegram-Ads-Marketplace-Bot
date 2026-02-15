const BASE_URL = "/api";

const REQUEST_TIMEOUT_MS = 15_000;
const MAX_RETRIES = 2;
const RETRY_BACKOFF_MS = 1000;

interface RequestOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  timeout?: number;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, headers = {}, timeout = REQUEST_TIMEOUT_MS } = options;

  const token = localStorage.getItem("token");
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  headers["Content-Type"] = "application/json";

  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
      const response = await fetch(`${BASE_URL}${endpoint}`, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      // Retry on 429 with backoff
      if (response.status === 429 && attempt < MAX_RETRIES) {
        const retryAfter = response.headers.get("Retry-After");
        const delay = retryAfter ? parseInt(retryAfter, 10) * 1000 : RETRY_BACKOFF_MS * (attempt + 1);
        await new Promise((r) => setTimeout(r, delay));
        continue;
      }

      if (!response.ok) {
        let detail = `${response.status} ${response.statusText}`;
        try {
          const body = await response.json();
          if (typeof body.detail === "string") {
            detail = body.detail;
          } else if (Array.isArray(body.detail)) {
            detail = body.detail.map((e: { msg?: string }) => e.msg || JSON.stringify(e)).join("; ");
          }
        } catch {
          /* no JSON body */
        }
        throw new ApiError(detail, response.status);
      }

      if (response.status === 204) {
        return undefined as T;
      }

      return response.json() as Promise<T>;
    } catch (err) {
      clearTimeout(timeoutId);

      if (err instanceof ApiError) {
        throw err;
      }

      // Network error or abort — retry if attempts remain
      lastError = err instanceof Error ? err : new Error(String(err));
      if (attempt < MAX_RETRIES) {
        await new Promise((r) => setTimeout(r, RETRY_BACKOFF_MS * (attempt + 1)));
        continue;
      }
    }
  }

  throw lastError || new Error("Request failed");
}

export const api = {
  get: <T>(endpoint: string, opts?: { timeout?: number }) =>
    request<T>(endpoint, { ...opts }),

  post: <T>(endpoint: string, body: unknown, opts?: { timeout?: number }) =>
    request<T>(endpoint, { method: "POST", body, ...opts }),

  patch: <T>(endpoint: string, body: unknown, opts?: { timeout?: number }) =>
    request<T>(endpoint, { method: "PATCH", body, ...opts }),

  delete: <T>(endpoint: string, opts?: { timeout?: number }) =>
    request<T>(endpoint, { method: "DELETE", ...opts }),
};

export default api;
