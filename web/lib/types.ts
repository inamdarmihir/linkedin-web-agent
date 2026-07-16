export type Category =
  | "research"
  | "product_launch"
  | "industry_news"
  | "commentary";

export interface LinkedInPost {
  author: string;
  title: string;
  summary: string;
  url: string | null;
  category: Category;
  posted_at: string | null;
}

export interface Digest {
  top_takeaway: string;
  posts: LinkedInPost[];
}

export type ProgressEventType =
  | "status"
  | "tool_start"
  | "tool_end"
  | "done"
  | "error";

export interface ProgressEvent {
  id: number;
  ts: string; // ISO 8601
  type: ProgressEventType;
  label: string;
  detail: string; // may be ""
  result: Digest | null; // only non-null when type === "done"
}

export type JobStatus = "queued" | "running" | "done" | "error";

export interface RunRecord {
  id: string;
  status: JobStatus;
  topics: string[];
  created_at: string;
  events: ProgressEvent[];
  result: Digest | null;
  error: string | null;
}

export interface CreateRunResponse {
  id: string;
  status: "queued";
  topics: string[];
  created_at: string;
}

export interface HealthResponse {
  ok: true;
  env: {
    OPENAI_API_KEY: boolean;
    LINKEDIN_EMAIL: boolean;
    LINKEDIN_PASSWORD: boolean;
    LANGSMITH_API_KEY: boolean;
  };
  env_ok: boolean;
}

export const CATEGORY_ORDER: Category[] = [
  "research",
  "product_launch",
  "industry_news",
  "commentary",
];

export const CATEGORY_LABELS: Record<Category, string> = {
  research: "Research",
  product_launch: "Product Launches",
  industry_news: "Industry News",
  commentary: "Commentary & Opinion",
};
