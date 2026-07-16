import type { JobStatus } from "@/lib/types";

const STYLES: Record<JobStatus, string> = {
  queued: "bg-slate-100 text-slate-700 ring-slate-300",
  running: "bg-blue-100 text-blue-700 ring-blue-300",
  done: "bg-green-100 text-green-700 ring-green-300",
  error: "bg-red-100 text-red-700 ring-red-300",
};

const LABELS: Record<JobStatus, string> = {
  queued: "Queued",
  running: "Running",
  done: "Done",
  error: "Error",
};

export default function StatusBadge({ status }: { status: JobStatus }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium ring-1 ring-inset ${STYLES[status]}`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          status === "running" ? "animate-pulse" : ""
        } bg-current`}
      />
      {LABELS[status]}
    </span>
  );
}
