import { useEffect, useMemo, useState, type ChangeEvent, type FormEvent } from "react";
import { AlertTriangle, Bot, ClipboardList, IndianRupee, RefreshCw, Send, ShieldCheck, Upload } from "lucide-react";
import { askQuestion, CANDIDATE_ID, getSkipped, getStats, getTasks, ingestEmails } from "./api/client";
import { Metric } from "./components/Metric";
import type { ChatResponse, EmailInput, IngestResponse, SkippedEmail, Stats, Task } from "./types/api";
import "./styles.css";

const emptyStats: Stats = {
  processed: 0, created: 0, updated: 0, skipped: 0, duplicates: 0, spurious_flagged: 0,
  by_assignee: {}, by_category: {}, by_priority: {}, by_run: {}, total_pipeline_inr: 0
};

function createStarterEmails(): EmailInput[] {
  const stamp = `${Date.now()}-${crypto.randomUUID().slice(0, 8)}`;
  return [
    {
    email_id: `sample-rfp-${stamp}`, thread_id: `sample-thread-rfp-${stamp}`, message_index: 0,
    from_name: "Suresh Kulkarni", from_email: "suresh@meridiansteel.co.in", to: "sales@company.com", cc: [],
    subject: "RFP - Enterprise document management system", body: "Please submit a proposal. Budget INR 25L. Deadline 2026-08-10.",
    received_at: "2026-08-08T09:14:22+05:30", attachments: ["RFP_DMS_2026.pdf"], is_reply: false
  },
    {
    email_id: `sample-demo-${stamp}`, thread_id: `sample-thread-demo-${stamp}`, message_index: 0,
    from_name: "Ankit Bose", from_email: "ankit@railyardlogistics.in", to: "sales@company.com", cc: [],
    subject: "Quick demo request", body: "Could you schedule a product demo for our 80-person team? Budget INR 4L.",
    received_at: "2026-08-08T11:02:00+05:30", attachments: [], is_reply: false
  },
    {
    email_id: `sample-news-${stamp}`, thread_id: `sample-thread-news-${stamp}`, message_index: 0,
    from_name: "Vendor Digest", from_email: "news@vendor.example", to: "sales@company.com", cc: [],
    subject: "Weekly digest", body: "Here is this week's newsletter. Unsubscribe at any time.",
    received_at: "2026-08-08T13:00:00+05:30", attachments: [], is_reply: false
    }
  ];
}

export default function App() {
  const [stats, setStats] = useState<Stats>(emptyStats);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [skipped, setSkipped] = useState<SkippedEmail[]>([]);
  const [jsonText, setJsonText] = useState(() => JSON.stringify(createStarterEmails(), null, 2));
  const [batch, setBatch] = useState<EmailInput[]>([]);
  const [ingestResult, setIngestResult] = useState<IngestResponse | null>(null);
  const [question, setQuestion] = useState("How many emails this batch were proposal or RFP related?");
  const [chat, setChat] = useState<ChatResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefreshedAt, setLastRefreshedAt] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setRefreshing(true);
    setError(null);
    try {
      const results = await Promise.allSettled([getStats(), getTasks(), getSkipped()]);
      const [statsResult, tasksResult, skippedResult] = results;
      if (statsResult.status === "fulfilled") setStats(statsResult.value);
      if (tasksResult.status === "fulfilled") setTasks(tasksResult.value);
      if (skippedResult.status === "fulfilled") setSkipped(skippedResult.value);

      const labels = ["Stats", "Tasks", "Skipped log"];
      const failures = results.flatMap((result, index) =>
        result.status === "rejected"
          ? [`${labels[index]}: ${result.reason instanceof Error ? result.reason.message : String(result.reason)}`]
          : []
      );
      if (failures.length) {
        setError(failures.join(" | "));
      } else {
        setLastRefreshedAt(new Date());
      }
    } finally {
      setRefreshing(false);
    }
  }

  function preview() {
    setError(null); setIngestResult(null); setChat(null);
    try {
      const parsed: unknown = JSON.parse(jsonText);
      const emails = (Array.isArray(parsed) ? parsed : (parsed as { emails?: unknown }).emails) as EmailInput[];
      if (!Array.isArray(emails) || emails.length === 0) throw new Error("Paste a JSON array of emails, or an object with an emails array.");
      if (emails.length > 250) throw new Error("The reviewer UI accepts up to 250 emails and routes them in 100-email batches.");
      const required = ["email_id", "thread_id", "from_email", "subject", "body"];
      emails.forEach((email, index) => required.forEach((field) => {
        if (!(field in email)) throw new Error(`Email ${index + 1} is missing ${field}.`);
      }));
      setBatch(emails);
    } catch (err) {
      setBatch([]); setError(err instanceof Error ? err.message : "Invalid JSON input");
    }
  }

  async function routeBatch() {
    if (!batch.length) return;
    setLoading(true); setError(null);
    try {
      setIngestResult(await ingestEmails(batch));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Batch ingest failed");
    } finally { setLoading(false); }
  }

  function generateSamples() {
    const generated = generateSampleEmails(250);
    setJsonText(JSON.stringify(generated, null, 2));
    setBatch(generated); setIngestResult(null); setChat(null); setError(null);
  }

  async function loadFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) { setJsonText(await file.text()); setBatch([]); setIngestResult(null); }
  }

  async function submitQuestion(event: FormEvent) {
    event.preventDefault();
    if (!batch.length) { setError("Preview a batch first so chat can stay scoped to it."); return; }
    setLoading(true); setError(null);
    try { setChat(await askQuestion(question, batch.map((email) => email.email_id))); }
    catch (err) { setError(err instanceof Error ? err.message : "Chat request failed"); }
    finally { setLoading(false); }
  }

  useEffect(() => { void refresh(); }, []);
  const assigneeRows = useMemo(() => Object.entries(stats.by_assignee), [stats.by_assignee]);

  return (
    <main className="appShell">
      <header className="topbar">
        <div className="brandMark"><ShieldCheck size={24} /></div>
        <div><h1>Sales Inbox Task Router</h1><p>Paste emails, inspect the raw batch, route deterministically, then ask grounded questions.</p></div>
        <div className="refreshControl">
          <button type="button" className="secondary" onClick={() => void refresh()} disabled={loading || refreshing}>
            <RefreshCw size={17} className={refreshing ? "spin" : undefined} />
            {refreshing ? "Refreshing..." : "Refresh dashboard"}
          </button>
          <span aria-live="polite">
            {lastRefreshedAt ? `Updated ${lastRefreshedAt.toLocaleTimeString()}` : "Not refreshed yet"}
          </span>
        </div>
      </header>
      {error ? <div className="errorBanner">{error}</div> : null}

      <section className="panel intakePanel">
        <div className="panelHeader"><div><h2>1. Paste or upload inbox JSON</h2><span>Candidate: {CANDIDATE_ID}</span></div></div>
        <div className="intakeBody">
          <textarea aria-label="Email JSON input" value={jsonText} onChange={(event) => { setJsonText(event.target.value); setBatch([]); }} spellCheck={false} />
          <div className="inputActions">
            <button type="button" onClick={preview} disabled={loading}><ClipboardList size={17} />Preview batch</button>
            <label className="fileButton"><Upload size={17} />Upload JSON<input type="file" accept="application/json,.json" onChange={(event) => void loadFile(event)} /></label>
            <button type="button" className="secondary" onClick={generateSamples} disabled={loading}>Generate 250 samples</button>
          </div>
        </div>
      </section>

      {batch.length ? (
        <section className="panel rawPanel">
          <div className="panelHeader"><div><h2>2. Raw batch preview</h2><span>{batch.length} emails — shown before routing</span></div><button type="button" onClick={() => void routeBatch()} disabled={loading}>Route this batch</button></div>
          <div className="tableWrap rawTable"><table><thead><tr><th>From name</th><th>From email</th><th>Subject</th><th>Received</th><th>Thread</th><th>Body preview</th></tr></thead>
            <tbody>{batch.map((email) => <tr key={email.email_id}><td>{email.from_name ?? "—"}</td><td>{email.from_email}</td><td>{email.subject}</td><td>{email.received_at ? new Date(email.received_at).toLocaleString() : "Unknown"}</td><td>{email.thread_id}</td><td>{email.body.slice(0, 110)}{email.body.length > 110 ? "…" : ""}</td></tr>)}</tbody>
          </table></div>
          {ingestResult ? <div className="resultBanner">Processed {ingestResult.processed}: {ingestResult.tasks_created} created, {ingestResult.tasks_updated} updated, {ingestResult.skipped} skipped, {ingestResult.errors.length} errors.</div> : null}
        </section>
      ) : null}

      <section className="metricsGrid" aria-label="Processing metrics">
        <Metric icon={ClipboardList} label="Emails processed" value={stats.processed} />
        <Metric icon={ShieldCheck} label="Tasks created" value={stats.created} />
        <Metric icon={RefreshCw} label="Thread updates" value={stats.updated} />
        <Metric icon={AlertTriangle} label="Skipped noise" value={stats.skipped} />
        <Metric icon={IndianRupee} label="Pipeline INR" value={stats.total_pipeline_inr.toLocaleString("en-IN")} />
      </section>

      <section className="contentGrid">
        <section className="panel"><div className="panelHeader"><h2>Routed Tasks</h2><span>{tasks.length} open</span></div><div className="tableWrap"><table><thead><tr><th>Task</th><th>Owner</th><th>Priority</th><th>Company</th><th>Reason</th></tr></thead><tbody>
          {tasks.map((task) => <tr key={task.task_id}><td><strong>{task.title}</strong><span>{task.thread_id}</span></td><td>{task.assignee_id}</td><td><span className={`pill ${task.priority}`}>{task.priority}</span></td><td>{task.company_name ?? "Unknown"}</td><td>{task.reasoning}</td></tr>)}
          {!tasks.length ? <tr><td colSpan={5} className="empty">No routed tasks yet.</td></tr> : null}
        </tbody></table></div></section>
        <aside className="panel"><div className="panelHeader"><h2>Assignees</h2></div><div className="assigneeList">{assigneeRows.map(([name, count]) => <div className="assigneeRow" key={name}><span>{name}</span><strong>{count}</strong></div>)}{!assigneeRows.length ? <p className="muted">No assignments yet.</p> : null}</div></aside>
      </section>

      <section className="contentGrid lower">
        <section className="panel"><div className="panelHeader"><h2>Skipped Log</h2><span>{skipped.length} latest</span></div><div className="skipList">{skipped.map((item) => <article key={item.source_email_id} className="skipItem"><div><strong>{item.subject}</strong><span>{item.from_email}</span></div><p>{item.reason}</p><span className="pill neutral">{item.skip_type}</span></article>)}{!skipped.length ? <p className="empty">No skipped emails yet.</p> : null}</div></section>
        <section className="panel chatPanel"><div className="panelHeader"><div><h2>3. Grounded batch chat</h2><span>{batch.length ? `Scoped to ${batch.length} previewed emails` : "Preview a batch first"}</span></div><Bot size={20} /></div>
          <form onSubmit={submitQuestion} className="chatForm"><input value={question} onChange={(event) => setQuestion(event.target.value)} /><button type="submit" disabled={loading || !batch.length}><Send size={17} />Ask</button></form>
          {chat ? <div className="chatAnswer"><strong>{chat.answer}</strong>{chat.query_intent ? <span>Intent: {chat.query_intent}</span> : null}<pre>{JSON.stringify(chat.supporting_data, null, 2)}</pre></div> : <p className="muted chatHint">Try RFP count, marketing vs spam, triage reasons, spurious rate, GST refunds, deal value, or thread updates.</p>}
        </section>
      </section>
    </main>
  );
}

function generateSampleEmails(count: number): EmailInput[] {
  const stamp = Date.now();
  const templates = [
    ["Enterprise RFP", "Please send a proposal for our platform rollout. Budget INR 18L.", "buyer", "enterprise.example"],
    ["Product demo request", "Could you schedule a demo? Budget INR 6L.", "founder", "smallco.example"],
    ["Conference sponsorship", "Would you sponsor our HR conference campaign?", "events", "summit.example"],
    ["Reseller partnership", "We would like to discuss a channel reseller partnership.", "alliances", "partner.example"],
    ["Invoice overdue", "Invoice payment is overdue. Please resolve the billing issue.", "accounts", "client.example"],
    ["Weekly digest", "Our weekly newsletter is here. Unsubscribe using this link.", "news", "vendor.example"],
    ["SEO backlinks", "Buy verified leads and SEO backlinks to rank #1.", "growth", "spam.example"]
  ];
  return Array.from({ length: count }, (_, index) => {
    const [subject, body, mailbox, domain] = templates[index % templates.length];
    return {
      email_id: `sample-${stamp}-${index + 1}`, thread_id: `sample-thread-${stamp}-${index + 1}`, message_index: 0,
      from_name: `Sample Sender ${index + 1}`, from_email: `${mailbox}${index + 1}@${domain}`, to: "sales@company.com", cc: [],
      subject, body, received_at: new Date(Date.now() - index * 60000).toISOString(), attachments: [], is_reply: false
    };
  });
}
