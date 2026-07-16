import type { HealthResponse } from "@/lib/types";

const REQUIRED_VARS = ["OPENAI_API_KEY", "LINKEDIN_EMAIL", "LINKEDIN_PASSWORD"] as const;

export default function HealthBanner({
  health,
}: {
  health: HealthResponse | null;
}) {
  if (!health) return null;

  const missing = REQUIRED_VARS.filter((key) => !health.env[key]);

  return (
    <div className="flex flex-col gap-2">
      {missing.length > 0 && (
        <div className="rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800">
          <span className="font-semibold">Backend misconfigured:</span> missing
          required environment variable{missing.length > 1 ? "s" : ""}{" "}
          <span className="font-mono text-xs">{missing.join(", ")}</span>.
          Real runs will fail until these are set on the backend.
        </div>
      )}
    </div>
  );
}
