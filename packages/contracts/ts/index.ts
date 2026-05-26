// packages/contracts/ts/index.ts
// 镜像 packages/contracts/python — 修改时必须同步两边

export type SubscriberStatus = "active" | "paused" | "unsubscribed";
export type Plan = "free" | "pro" | "enterprise";
export type PushChannel = "email" | "feishu";
export type Topic =
  | "new_car" | "sales" | "policy" | "tech" | "overseas"
  | "people" | "finance" | "recall" | "supply_chain";
export type SourceType = "rss" | "api" | "html_scrape" | "rsshub";
export type SourceCategory = "media" | "official" | "association" | "oem";
export type Locale = "zh" | "en";
export type ArticleStatus = "pending" | "processing" | "done" | "failed";
export type DeliveryStatus = "pending" | "sending" | "sent" | "failed" | "bounced";
export type SalesSource = "CPCA" | "CAAM" | "official";

export interface Subscriber {
  id: string;            // uuid
  email: string;
  status: SubscriberStatus;
  plan: Plan;
  push_time: string;     // HH:MM:SS
  push_channel: PushChannel;
  unsubscribe_token: string;
  last_opened_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SubscriberPreferences {
  subscriber_id: string;
  brands: string[];
  topics: Topic[];
  regions: string[];
  created_at: string;
  updated_at: string;
}

export interface SourceLink {
  name: string;
  url: string;
}

export interface BriefCandidate {
  rank: number;
  cluster_id: string;
  title: string;          // ≤25 中文字
  summary: string;        // ≤120 中文字
  brands: string[];
  topics: Topic[];
  source_links: SourceLink[];
  global_importance: number;  // 0-100
}

export interface DailyBrief {
  id: string;
  brief_date: string;
  candidates: BriefCandidate[];
  generated_at: string;
  created_at: string;
  updated_at: string;
}

export interface Delivery {
  id: string;
  subscriber_id: string;
  brief_date: string;
  content_html: string;
  content_text: string;
  selected_items: unknown[] | null;
  status: DeliveryStatus;
  resend_id: string | null;
  sent_at: string | null;
  opened_at: string | null;
  error: string | null;
  retry_count: number;
  created_at: string;
  updated_at: string;
}

// 订阅表单提交体（web API 用）
export interface SubscribeRequest {
  email: string;
  brands: string[];
  topics: Topic[];
  push_time?: string;       // default "08:00"
  turnstile_token: string;  // Cloudflare Turnstile
}

export interface ManageRequest {
  token: string;            // unsubscribe_token
  brands?: string[];
  topics?: Topic[];
  push_time?: string;
  pause?: boolean;
}

export interface UnsubscribeRequest {
  token: string;
}
