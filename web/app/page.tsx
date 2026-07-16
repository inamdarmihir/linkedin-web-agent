"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiError,
  createRun,
  getHealth,
  subscribeToRunEvents,
} from "@/lib/api";
import type {
  Digest,
  HealthResponse,
  JobStatus,
  ProgressEvent,
} from "@/lib/types";
import HealthBanner from "./components/HealthBanner";
import StatusBadge from "./components/StatusBadge";
import TopicsForm, {
  type TopicsFormSubmitValue,
} from "./components/TopicsForm";
import ProgressLog from "./components/ProgressLog";
import ReportView from "./components/ReportView";
import ErrorPanel from "./components/ErrorPanel";

interface TerminalError {
  label: string;
  detail: string | null;
}

export default function Home() {
  const [health, setHealth] = useState<HealthResponse | null>(null);

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [runId, setRunId] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [result, setResult] = useState<Digest | null>(null);
  const [terminalError, setTerminalError] = useState<TerminalError | null>(
    null,
  );

  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => {
        // Health check is best-effort; the form still works without it.
      });
  }, []);

  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
    };
  }, []);

  const handleEvent = useCallback((event: ProgressEvent) => {
    setEvents((prev) => [...prev, event]);

    if (event.type === "done") {
      setStatus("done");
      setResult(event.result);
      eventSourceRef.current?.close();
    } else if (event.type === "error") {
      setStatus("error");
      setTerminalError({ label: event.label, detail: event.detail || null });
      eventSourceRef.current?.close();
    } else {
      setStatus((prev) => (prev === "queued" || prev === null ? "running" : prev));
    }
  }, []);

  async function handleSubmit({ topics, project }: TopicsFormSubmitValue) {
    setSubmitError(null);
    setSubmitting(true);

    try {
      const run = await createRun(topics, project);

      setRunId(run.id);
      setStatus("queued");
      setEvents([]);
      setResult(null);
      setTerminalError(null);

      eventSourceRef.current?.close();
      eventSourceRef.current = subscribeToRunEvents(run.id, {
        onEvent: handleEvent,
        onError: () => {
          // The backend closes the stream after a terminal event; a
          // mid-stream network error just means the browser's own
          // EventSource will retry, so there's nothing to surface here
          // unless we never reach a terminal state at all.
        },
      });
    } catch (err) {
      setSubmitError(
        err instanceof ApiError
          ? err.message
          : "Failed to start run. Is the backend reachable?",
      );
    } finally {
      setSubmitting(false);
    }
  }

  function handleReset() {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    setRunId(null);
    setStatus(null);
    setEvents([]);
    setResult(null);
    setTerminalError(null);
    setSubmitError(null);
  }

  const isRunActive = status === "queued" || status === "running";
  const isTerminal = status === "done" || status === "error";

  return (
    <main className="mx-auto flex w-full max-w-2xl flex-1 flex-col gap-6 px-4 py-10">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-bold text-slate-900">
          LinkedIn AI Digest
        </h1>
        <p className="text-sm text-slate-500">
          Scan LinkedIn for AI news on your topics and get a categorized
          digest.
        </p>
      </header>

      <HealthBanner health={health} />

      {!runId || !status ? (
        <TopicsForm
          submitting={submitting}
          submitError={submitError}
          onSubmit={handleSubmit}
        />
      ) : (
        <div className="flex flex-col gap-4">
          <div className="flex items-center justify-between gap-4">
            <StatusBadge status={status} />
            {isTerminal && (
              <button
                type="button"
                onClick={handleReset}
                className="text-sm font-medium text-slate-600 underline-offset-2 hover:underline"
              >
                Run again
              </button>
            )}
          </div>

          <ProgressLog events={events} />

          {status === "error" && terminalError && (
            <ErrorPanel label={terminalError.label} detail={terminalError.detail} />
          )}

          {status === "done" && result && (
            <ReportView runId={runId} result={result} />
          )}

          {isRunActive && events.length === 0 && (
            <p className="text-sm text-slate-500">Waiting for updates…</p>
          )}
        </div>
      )}
    </main>
  );
}
