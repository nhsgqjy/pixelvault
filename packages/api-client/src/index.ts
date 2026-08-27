export type QueryValue = string | number | boolean | null | undefined;
export type ApiRequestOptions = Omit<RequestInit, "body"> & {
  body?: BodyInit | null;
  json?: unknown;
  query?: Record<string, QueryValue | QueryValue[]>;
};
export type ApiClientOptions = {
  baseUrl: string;
  credentials?: RequestCredentials;
  fetch?: typeof globalThis.fetch;
  getHeaders?: () => HeadersInit | Promise<HeadersInit>;
};

export class ApiError extends Error {
  readonly status: number;
  readonly payload: unknown;

  constructor(status: number, payload: unknown, message?: string) {
    super(message ?? `API request failed with status ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

function appendQuery(url: URL, query?: ApiRequestOptions["query"]) {
  if (!query) return;
  for (const [key, raw] of Object.entries(query)) {
    for (const value of Array.isArray(raw) ? raw : [raw]) {
      if (value !== null && value !== undefined) url.searchParams.append(key, String(value));
    }
  }
}

async function parseResponse(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined;
  if ((response.headers.get("content-type") ?? "").includes("application/json")) return response.json();
  const text = await response.text();
  return text || undefined;
}

export function createApiClient(options: ApiClientOptions) {
  const baseUrl = options.baseUrl.replace(/\/$/, "");
  const fetcher = options.fetch ?? globalThis.fetch.bind(globalThis);
  const url = (path: string, query?: ApiRequestOptions["query"]) => {
    if (/^https?:\/\//i.test(path)) {
      const result = new URL(path);
      appendQuery(result, query);
      return result.toString();
    }
    const origin = /^https?:\/\//i.test(baseUrl) ? "" : (globalThis.location?.origin ?? "http://localhost");
    const result = new URL(`${origin}${baseUrl}${path.startsWith("/") ? path : `/${path}`}`);
    appendQuery(result, query);
    return result.toString();
  };

  async function raw(path: string, request: ApiRequestOptions = {}) {
    const { json, query, headers: suppliedHeaders, ...init } = request;
    const headers = new Headers(await options.getHeaders?.());
    new Headers(suppliedHeaders).forEach((value, key) => headers.set(key, value));
    if (!headers.has("Accept")) headers.set("Accept", "application/json");
    let body = init.body;
    if (json !== undefined) {
      headers.set("Content-Type", "application/json");
      body = JSON.stringify(json);
    }
    return fetcher(url(path, query), {
      ...init,
      body,
      headers,
      credentials: init.credentials ?? options.credentials ?? "include",
    });
  }

  async function request<T>(path: string, init: ApiRequestOptions = {}) {
    const response = await raw(path, init);
    const payload = await parseResponse(response);
    if (!response.ok) {
      const message = typeof payload === "object" && payload !== null && "detail" in payload
        ? String((payload as { detail: unknown }).detail) : undefined;
      throw new ApiError(response.status, payload, message);
    }
    return payload as T;
  }

  return {
    url, raw, request,
    get: <T>(path: string, init?: ApiRequestOptions) => request<T>(path, { ...init, method: "GET" }),
    post: <T>(path: string, init?: ApiRequestOptions) => request<T>(path, { ...init, method: "POST" }),
    put: <T>(path: string, init?: ApiRequestOptions) => request<T>(path, { ...init, method: "PUT" }),
    patch: <T>(path: string, init?: ApiRequestOptions) => request<T>(path, { ...init, method: "PATCH" }),
    delete: <T>(path: string, init?: ApiRequestOptions) => request<T>(path, { ...init, method: "DELETE" }),
  };
}
export type ApiClient = ReturnType<typeof createApiClient>;
