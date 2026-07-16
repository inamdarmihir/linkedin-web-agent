import type {
  CreateRunResponse,
  HealthResponse,
  ProgressEvent,
  RunRecord,
} from "./types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/**
 * Best-effort extraction of a human-readable error message from a
 * FastAPI-style error body. Handles both `{"detail": "..."}` (plain string,
 * e.g. our 503 responses) and `{"detail": [...]}` (pydantic validation
 * errors, e.g. 422 responses).
 */
async function extractErrorMessage(
  res: Response,
  fallback: string,
): Promise<string> {
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    return fallback;
  }

  if (
    !body ||
    typeof body !== "object" ||
    !("detail" in body)
  ) {
    return fallback;
  }

  const { detail } = body;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((entry) => {
        if (
          entry &&
          typeof entry === "object" &&
          "msg" in entry &&
          typeof entry.msg === "string"
        ) {
          return entry.msg;
        }
        return null;
      })
      .filter((msg): msg is string => msg !== null);

    if (messages.length > 0) {
      return messages.join("; ");
    }
  }

  return fallback;
}

export async function createRun(
  topics: string[],
  project?: string,
): Promise<CreateRunResponse> {
  const res = await fetch(`${API_BASE_URL}/api/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(
      project ? { topics, project } : { topics },
    ),
  });

  if (!res.ok) {
    const message = await extractErrorMessage(
      res,
      `Failed to start run (HTTP ${res.status}).`,
    );
    throw new ApiError(message, res.status);
  }

  const data: CreateRunResponse = await res.json();
  return data;
}

export async function getRun(id: string): Promise<RunRecord> {
  const res = await fetch(`${API_BASE_URL}/api/runs/${id}`);

  if (!res.ok) {
    const message = await extractErrorMessage(
      res,
      `Failed to fetch run (HTTP ${res.status}).`,
    );
    throw new ApiError(message, res.status);
  }

  const data: RunRecord = await res.json();
  return data;
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/api/health`);

  if (!res.ok) {
    throw new ApiError(
      `Failed to fetch health (HTTP ${res.status}).`,
      res.status,
    );
  }

  const data: HealthResponse = await res.json();
  return data;
}

export function runMarkdownUrl(id: string): string {
  return `${API_BASE_URL}/api/runs/${id}/markdown`;
}

export async function downloadRunMarkdown(id: string): Promise<void> {
  const res = await fetch(runMarkdownUrl(id));

  if (!res.ok) {
    const message = await extractErrorMessage(
      res,
      `Failed to download report (HTTP ${res.status}).`,
    );
    throw new ApiError(message, res.status);
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `linkedin-ai-digest-${id}.md`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export interface RunEventStreamHandlers {
  onEvent: (event: ProgressEvent) => void;
  onError?: (err: Event) => void;
}

/**
 * Opens an SSE connection to `/api/runs/{id}/events`. The backend replays
 * all prior events on connect, then streams new ones live, then closes the
 * connection after a terminal ("done" | "error") event. The caller is
 * responsible for closing the returned EventSource (e.g. on unmount), which
 * is a safe no-op once the server has already closed the stream.
 */
export function subscribeToRunEvents(
  id: string,
  { onEvent, onError }: RunEventStreamHandlers,
): EventSource {
  const source = new EventSource(`${API_BASE_URL}/api/runs/${id}/events`);

  source.onmessage = (message) => {
    const parsed: ProgressEvent = JSON.parse(message.data);
    onEvent(parsed);
  };

  if (onError) {
    source.onerror = onError;
  }

  return source;
}
