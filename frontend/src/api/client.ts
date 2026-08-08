import type { ChatResponse, SkippedEmail, Stats, Task } from "../types/api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export async function getStats(): Promise<Stats> {
  return request<Stats>("/stats");
}

export async function getTasks(): Promise<Task[]> {
  return request<Task[]>("/tasks");
}

export async function getSkipped(): Promise<SkippedEmail[]> {
  return request<SkippedEmail[]>("/skipped");
}

export async function askQuestion(question: string): Promise<ChatResponse> {
  return request<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({ question })
  });
}

export async function seedDemo(): Promise<void> {
  await request("/ingest", {
    method: "POST",
    body: JSON.stringify({
      candidate_id: "demo",
      emails: [
        {
          source_email_id: `demo-psu-${Date.now()}`,
          thread_id: "demo-thread-psu",
          from_email: "procurement@bharatpsu.gov.in",
          subject: "Urgent PSU LMS tender",
          body: "Please submit proposal for a public sector LMS tender. Budget INR 25L. Deadline 2026-08-10."
        },
        {
          source_email_id: `demo-finance-${Date.now()}`,
          thread_id: `demo-thread-finance-${Date.now()}`,
          from_email: "accounts@client.com",
          subject: "Invoice mismatch",
          body: "The invoice amount and purchase order do not match. Please resolve billing."
        },
        {
          source_email_id: `demo-news-${Date.now()}`,
          thread_id: `demo-thread-news-${Date.now()}`,
          from_email: "news@vendor.com",
          subject: "Weekly digest",
          body: "Here is our weekly newsletter. Unsubscribe here."
        }
      ]
    })
  });
}

