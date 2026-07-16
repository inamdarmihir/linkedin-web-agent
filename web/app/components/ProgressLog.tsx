"use client";

import { useEffect, useRef } from "react";
import type { ProgressEvent, ProgressEventType } from "@/lib/types";

const ROW_STYLES: Record<ProgressEventType, string> = {
  status: "border-slate-200 bg-slate-50 text-slate-700",
  tool_start: "border-blue-200 bg-blue-50 text-blue-800",
  tool_end: "border-green-200 bg-green-50 text-green-800",
  done: "border-green-300 bg-green-100 text-green-900 font-medium",
  error: "border-red-300 bg-red-50 text-red-800",
};

const DOT_STYLES: Record<ProgressEventType, string> = {
  status: "bg-slate-400",
  tool_start: "bg-blue-500 animate-pulse",
  tool_end: "bg-green-500",
  done: "bg-green-600",
  error: "bg-red-500",
};

function formatTime(ts: string): string {
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return ts;
  return date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function ProgressLog({ events }: { events: ProgressEvent[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [events.length]);

  if (events.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-sm font-semibold text-slate-700">Progress</h2>
      <div className="flex max-h-80 flex-col gap-1.5 overflow-y-auto">
        {events.map((event) => (
          <div
            key={event.id}
            className={`flex items-start gap-2 rounded-md border px-3 py-1.5 text-sm ${ROW_STYLES[event.type]}`}
          >
            <span
              className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${DOT_STYLES[event.type]}`}
            />
            <div className="flex min-w-0 flex-1 flex-col">
              <div className="flex items-baseline justify-between gap-2">
                <span className="truncate">{event.label}</span>
                <span className="shrink-0 text-xs text-slate-400">
                  {formatTime(event.ts)}
                </span>
              </div>
              {event.detail && (
                <span className="text-xs text-slate-500">{event.detail}</span>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
