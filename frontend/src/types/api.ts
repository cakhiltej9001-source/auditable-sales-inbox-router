export type Stats = {
  total_emails: number;
  created_tasks: number;
  updated_tasks: number;
  duplicates: number;
  skipped: number;
  by_assignee: Record<string, number>;
  by_category: Record<string, number>;
  by_priority: Record<string, number>;
  total_pipeline_inr: number;
};

export type Task = {
  external_task_id: string;
  thread_id: string;
  source_email_id: string;
  assignee_id: string;
  category: string;
  priority: string;
  title: string;
  company: string | null;
  deal_value_inr: number | null;
  due_at: string | null;
  confidence: number;
  reasoning: string;
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

export type ChatResponse = {
  answer: string;
  supporting_data: Record<string, unknown>;
  query_intent: string;
};

