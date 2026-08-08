import type { ChatResponse, EmailInput, IngestResponse, SkippedEmail, Stats, Task } from "../types/api";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const CANDIDATE_ID = (import.meta.env.VITE_CANDIDATE_ID ?? "cakhiltej9001@gmail.com").toLowerCase();

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${response.status} ${response.statusText}${detail ? `: ${detail}` : ""}`);
  }
  return response.status === 204 ? (undefined as T) : (response.json() as Promise<T>);
}

export function getStats(): Promise<Stats> {
  return request<Stats>(`/api/stats?candidate_id=${encodeURIComponent(CANDIDATE_ID)}`);
}

export function getTasks(): Promise<Task[]> {
  return request<Task[]>(`/api/tasks?candidate_id=${encodeURIComponent(CANDIDATE_ID)}`);
}

export function getSkipped(): Promise<SkippedEmail[]> {
  return request<SkippedEmail[]>(`/skipped?candidate_id=${encodeURIComponent(CANDIDATE_ID)}`);
}

export function askQuestion(query: string, emailIds: string[]): Promise<ChatResponse> {
  return request<ChatResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify({ candidate_id: CANDIDATE_ID, query, email_ids: emailIds })
  });
}

export async function ingestEmails(emails: EmailInput[]): Promise<IngestResponse> {
  const total: IngestResponse = { processed: 0, tasks_created: 0, tasks_updated: 0, skipped: 0, errors: [] };
  for (let start = 0; start < emails.length; start += 100) {
    const result = await request<IngestResponse>("/ingest", {
      method: "POST",
      body: JSON.stringify({ candidate_id: CANDIDATE_ID, emails: emails.slice(start, start + 100) })
    });
    total.processed += result.processed;
    total.tasks_created += result.tasks_created;
    total.tasks_updated += result.tasks_updated;
    total.skipped += result.skipped;
    total.errors.push(...result.errors);
  }
  return total;
}
