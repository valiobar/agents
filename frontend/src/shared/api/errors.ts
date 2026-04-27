import type { ApiErrorBody } from "./types";

export function isApiErrorBody(value: unknown): value is ApiErrorBody {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return "detail" in v || "message" in v;
}

function normalizeDetail(detail: ApiErrorBody["detail"]): string | undefined {
  if (!detail) return undefined;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((e) => {
        const loc = e.loc?.join(".") ?? "unknown";
        return `${loc}: ${e.msg}`;
      })
      .join("; ");
  }
  return undefined;
}

export class ApiError extends Error {
  readonly status: number;
  readonly body: ApiErrorBody | null;

  constructor(status: number, message: string, body: ApiErrorBody | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }

  static fromResponse(status: number, body: ApiErrorBody | null): ApiError {
    const message =
      (body?.message && String(body.message)) ||
      normalizeDetail(body?.detail) ||
      `Request failed with status ${status}`;

    return new ApiError(status, message, body);
  }
}

