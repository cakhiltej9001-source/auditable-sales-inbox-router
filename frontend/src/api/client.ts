import type { ChatResponse, EmailInput, IngestResponse, SkippedEmail, Stats, Task } from "../types/api";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

function normalizeCandidateId(value: string): string {
  const candidate = value.trim().toLowerCase();
  const at = candidate.lastIndexOf("@");
  if (at < 0) return candidate;
  const local = candidate.slice(0, at).split("+", 1)[0];
  return `${local}@${candidate.slice(at + 1)}`;
}

export const CANDIDATE_ID = normalizeCandidateId(import.meta.env.VITE_CANDIDATE_ID ?? "cakhiltej9001@gmail.com");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      cache: "no-store",
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      ...init
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : "network request failed";
    throw new Error(`Cannot reach ${url}: ${detail}`);
  }
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

export function reviewSpuriousTask(taskId: string, spuriousFlagged: boolean): Promise<void> {
  return request<void>(`/api/tasks/${encodeURIComponent(taskId)}/spurious`, {
    method: "PATCH",
    body: JSON.stringify({
      candidate_id: CANDIDATE_ID,
      spurious_flagged: spuriousFlagged,
      reason: spuriousFlagged
        ? "Reviewer marked this routed task as spurious from the dashboard."
        : "Reviewer cleared the spurious flag after re-checking the source email."
    })
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
