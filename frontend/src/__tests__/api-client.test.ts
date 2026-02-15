import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { api, ApiError } from "@/api/client";

describe("API client", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  function mockFetch(response: Partial<Response> & { json?: () => Promise<unknown> }) {
    const fn = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      headers: new Headers(),
      json: () => Promise.resolve({}),
      ...response,
    });
    globalThis.fetch = fn;
    return fn;
  }

  it("sends GET request to correct URL", async () => {
    const fetchMock = mockFetch({ json: () => Promise.resolve({ id: 1 }) });

    const result = await api.get("/me");

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, opts] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/me");
    expect(opts.method).toBe("GET");
    expect(result).toEqual({ id: 1 });
  });

  it("sends POST request with JSON body", async () => {
    const fetchMock = mockFetch({ json: () => Promise.resolve({ ok: true }) });

    await api.post("/auth/telegram", { init_data: "test" });

    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.method).toBe("POST");
    expect(JSON.parse(opts.body)).toEqual({ init_data: "test" });
    expect(opts.headers["Content-Type"]).toBe("application/json");
  });

  it("attaches Authorization header when token exists", async () => {
    localStorage.setItem("token", "jwt-token-123");
    const fetchMock = mockFetch({ json: () => Promise.resolve({}) });

    await api.get("/me");

    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.headers["Authorization"]).toBe("Bearer jwt-token-123");
  });

  it("does not attach Authorization header when no token", async () => {
    const fetchMock = mockFetch({ json: () => Promise.resolve({}) });

    await api.get("/me");

    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.headers["Authorization"]).toBeUndefined();
  });

  it("throws ApiError on non-OK response", async () => {
    mockFetch({
      ok: false,
      status: 404,
      statusText: "Not Found",
      json: () => Promise.resolve({ detail: "User not found" }),
    });

    await expect(api.get("/me")).rejects.toThrow(ApiError);
    await expect(api.get("/me")).rejects.toMatchObject({
      status: 404,
      message: "User not found",
    });
  });

  it("throws ApiError with joined Pydantic validation errors", async () => {
    mockFetch({
      ok: false,
      status: 422,
      statusText: "Unprocessable Entity",
      json: () =>
        Promise.resolve({
          detail: [
            { msg: "field required", loc: ["body", "title"] },
            { msg: "value too short", loc: ["body", "name"] },
          ],
        }),
    });

    await expect(api.get("/test")).rejects.toMatchObject({
      status: 422,
      message: "field required; value too short",
    });
  });

  it("retries on 429 with backoff", async () => {
    let callCount = 0;
    globalThis.fetch = vi.fn().mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        return Promise.resolve({
          ok: false,
          status: 429,
          statusText: "Too Many Requests",
          headers: new Headers(),
          json: () => Promise.resolve({ detail: "rate limited" }),
        });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        headers: new Headers(),
        json: () => Promise.resolve({ success: true }),
      });
    });

    const result = await api.get("/me");

    expect(callCount).toBe(2);
    expect(result).toEqual({ success: true });
  });

  it("returns undefined for 204 No Content", async () => {
    mockFetch({ status: 204, ok: true });

    const result = await api.delete("/owner/channels/1");

    expect(result).toBeUndefined();
  });

  it("sends PATCH request", async () => {
    const fetchMock = mockFetch({ json: () => Promise.resolve({ locale: "ru" }) });

    await api.patch("/me/locale", { locale: "ru" });

    const [, opts] = fetchMock.mock.calls[0];
    expect(opts.method).toBe("PATCH");
    expect(JSON.parse(opts.body)).toEqual({ locale: "ru" });
  });
});
