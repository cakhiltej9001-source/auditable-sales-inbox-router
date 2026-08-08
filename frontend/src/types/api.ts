export type EmailInput = {
  email_id: string;
  thread_id: string;
  message_index: number;
  from_name: string | null;
  from_email: string;
  to: string | string[] | null;
  cc: string[];
  subject: string;
  body: string;
  received_at: string | null;
  attachments: string[];
  is_reply: boolean;
};

export type Stats = {
  processed: number;
  created: number;
  updated: number;
  skipped: number;
  duplicates: number;
  spurious_flagged: number;
  by_assignee: Record<string, number>;
  by_category: Record<string, number>;
  by_priority: Record<string, number>;
  by_run: Record<string, Record<string, number>>;
  total_pipeline_inr: number;
};

export type Task = {
  task_id: string;
  candidate_id: string;
  thread_id: string;
  source_email_id: string;
  assignee_id: string;
  category: string;
  priority: string;
  title: string;
  description: string | null;
  company_name: string | null;
  deal_value_inr: number | null;
  due_date: string | null;
  confidence: number;
  reasoning: string;
  status: string;
  update_count: number;
  updated_at: string;
};

export type SkippedEmail = {
  source_email_id: string;
  thread_id: string;
  skip_type: string;
  reason: string;
  subject: string;
  from_email: string;
  received_at: string | null;
};

export type IngestResponse = {
  processed: number;
  tasks_created: number;
  tasks_updated: number;
  skipped: number;
  errors: Array<Record<string, unknown>>;
};

export type ChatResponse = {
  answer: string;
  supporting_data: Record<string, unknown>;
  query_intent?: string | null;
};
