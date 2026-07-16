"use client";

import { useState } from "react";
import {
  CATEGORY_LABELS,
  CATEGORY_ORDER,
  type Digest,
  type LinkedInPost,
} from "@/lib/types";
import { downloadRunMarkdown } from "@/lib/api";

function PostCard({ post }: { post: LinkedInPost }) {
  const heading = (
    <span className="font-semibold text-slate-900">{post.title}</span>
  );

  return (
    <div className="flex flex-col gap-1 rounded-md border border-slate-200 bg-white p-4">
      {post.url ? (
        <a
          href={post.url}
          target="_blank"
          rel="noopener noreferrer"
          className="hover:underline"
        >
          {heading}
        </a>
      ) : (
        heading
      )}
      <div className="flex flex-wrap items-center gap-x-2 text-xs text-slate-500">
        <span>{post.author}</span>
        {post.posted_at && (
          <>
            <span aria-hidden>·</span>
            <span>{post.posted_at}</span>
          </>
        )}
      </div>
      <p className="text-sm text-slate-700">{post.summary}</p>
    </div>
  );
}

export default function ReportView({
  runId,
  result,
}: {
  runId: string;
  result: Digest;
}) {
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  async function handleDownload() {
    setDownloadError(null);
    setDownloading(true);
    try {
      await downloadRunMarkdown(runId);
    } catch (err) {
      setDownloadError(
        err instanceof Error ? err.message : "Failed to download report.",
      );
    } finally {
      setDownloading(false);
    }
  }

  const groups = CATEGORY_ORDER.map((category) => ({
    category,
    posts: result.posts.filter((post) => post.category === category),
  })).filter((group) => group.posts.length > 0);

  return (
    <div className="flex flex-col gap-4 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <h2 className="text-sm font-semibold text-slate-700">Final Report</h2>
        <div className="flex flex-col items-end gap-1">
          <button
            type="button"
            onClick={handleDownload}
            disabled={downloading}
            className="inline-flex items-center justify-center rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {downloading ? "Downloading…" : "Download report (.md)"}
          </button>
          {downloadError && (
            <span className="text-xs text-red-600">{downloadError}</span>
          )}
        </div>
      </div>

      <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        <span className="font-semibold">Top takeaway: </span>
        {result.top_takeaway}
      </div>

      {groups.length === 0 ? (
        <p className="text-sm text-slate-500">
          No relevant posts found this run.
        </p>
      ) : (
        <div className="flex flex-col gap-5">
          {groups.map(({ category, posts }) => (
            <div key={category} className="flex flex-col gap-2">
              <h3 className="text-sm font-semibold text-slate-800">
                {CATEGORY_LABELS[category]}
              </h3>
              <div className="flex flex-col gap-2">
                {posts.map((post, idx) => (
                  <PostCard key={`${category}-${idx}`} post={post} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
