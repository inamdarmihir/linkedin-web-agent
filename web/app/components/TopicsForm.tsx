"use client";

import { useMemo, useState } from "react";
import { parseTopics } from "@/lib/topics";

const TOPICS_PLACEHOLDER =
  "AI research\nlarge language models\nAI product launches";

export interface TopicsFormSubmitValue {
  topics: string[];
  project?: string;
}

export default function TopicsForm({
  submitting,
  submitError,
  onSubmit,
}: {
  submitting: boolean;
  submitError: string | null;
  onSubmit: (value: TopicsFormSubmitValue) => void;
}) {
  const [topicsText, setTopicsText] = useState("");
  const [project, setProject] = useState("linkedin-ai-digest");

  const topics = useMemo(() => parseTopics(topicsText), [topicsText]);
  const canSubmit = topics.length > 0 && !submitting;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    const trimmedProject = project.trim();
    onSubmit({
      topics,
      project: trimmedProject.length > 0 ? trimmedProject : undefined,
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-4 rounded-lg border border-slate-200 bg-white p-5 shadow-sm"
    >
      <div className="flex flex-col gap-1.5">
        <label htmlFor="topics" className="text-sm font-medium text-slate-700">
          Topics
        </label>
        <textarea
          id="topics"
          rows={4}
          value={topicsText}
          onChange={(e) => setTopicsText(e.target.value)}
          placeholder={TOPICS_PLACEHOLDER}
          disabled={submitting}
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500 disabled:bg-slate-50 disabled:text-slate-400"
        />
        <p className="text-xs text-slate-500">
          One topic per line, or comma-separated.
          {topics.length > 0 && ` ${topics.length} topic(s) detected.`}
        </p>
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="project" className="text-sm font-medium text-slate-700">
          LangSmith project name{" "}
          <span className="font-normal text-slate-400">(optional, advanced)</span>
        </label>
        <input
          id="project"
          type="text"
          value={project}
          onChange={(e) => setProject(e.target.value)}
          disabled={submitting}
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500 disabled:bg-slate-50 disabled:text-slate-400"
        />
      </div>

      {submitError && (
        <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-800">
          {submitError}
        </div>
      )}

      <button
        type="submit"
        disabled={!canSubmit}
        className="inline-flex items-center justify-center rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
      >
        {submitting ? "Running…" : "Run digest"}
      </button>
    </form>
  );
}
