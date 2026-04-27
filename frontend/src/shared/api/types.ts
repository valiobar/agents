export interface ApiClientOptions {
  baseUrl: string;
  getToken?: () => Promise<string | null> | string | null;
}

export interface ApiRequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  token?: string | null;
  params?: Record<string, string | number | boolean | null | undefined>;
}

export interface ApiErrorBody {
  detail?: string | Array<{ loc: string[]; msg: string; type: string }>;
  message?: string;
}

