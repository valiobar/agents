import { env } from "@/shared/config/env";
import type { ApiRequestOptions } from "./types";
import { ApiError, isApiErrorBody } from "./errors";

class ApiClient {
  constructor(private readonly baseUrl: string = env.publicGatewayUrl) {}

  async request<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
    // Next listens on container/`npm run dev` port 3000. Host publish is 3010.
    const origin =
      globalThis.window === undefined ? "http://localhost:3000" : globalThis.window.location.origin;
    const baseUrl = this.baseUrl.startsWith("http") ? this.baseUrl : `${origin}${this.baseUrl}`;
    const url = new URL(path.replace(/^\/+/, ""), `${baseUrl.replace(/\/+$/, "")}/`);
    for (const [key, value] of Object.entries(options.params ?? {})) {
      if (value !== null && value !== undefined) {
        url.searchParams.set(key, String(value));
      }
    }

    const headers = new Headers(options.headers);
    if (!(options.body instanceof FormData) && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    headers.set("ngrok-skip-browser-warning", "true");
    if (options.token) {
      headers.set("Authorization", `Bearer ${options.token}`);
    }

    const requestBody: BodyInit | null | undefined =
      options.body && !(options.body instanceof FormData) && typeof options.body !== "string"
        ? JSON.stringify(options.body)
        : (options.body as BodyInit | null | undefined);

    const response = await fetch(url, {
      ...options,
      headers,
      body: requestBody,
    });

    if (!response.ok) {
      const body = (await response.json().catch(() => null)) as unknown;
      throw ApiError.fromResponse(response.status, isApiErrorBody(body) ? body : null);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json() as Promise<T>;
  }

  get<T>(path: string, options?: ApiRequestOptions) {
    return this.request<T>(path, { ...options, method: "GET" });
  }

  post<T>(path: string, body?: unknown, options?: ApiRequestOptions) {
    return this.request<T>(path, { ...options, method: "POST", body });
  }

  patch<T>(path: string, body?: unknown, options?: ApiRequestOptions) {
    return this.request<T>(path, { ...options, method: "PATCH", body });
  }

  put<T>(path: string, body?: unknown, options?: ApiRequestOptions) {
    return this.request<T>(path, { ...options, method: "PUT", body });
  }

  delete(path: string, options?: ApiRequestOptions) {
    return this.request<void>(path, { ...options, method: "DELETE" });
  }
}

export const apiClient = new ApiClient();
export { ApiClient };

