import { useEffect, useMemo, useState, type FormEvent } from "react";
import { AlertTriangle, Bot, ClipboardList, IndianRupee, RefreshCw, Send, ShieldCheck } from "lucide-react";
import { askQuestion, getSkipped, getStats, getTasks, seedDemo } from "./api/client";
import { Metric } from "./components/Metric";
import type { ChatResponse, SkippedEmail, Stats, Task } from "./types/api";
import "./styles.css";

const emptyStats: Stats = {
  total_emails: 0,
  created_tasks: 0,
  updated_tasks: 0,
  duplicates: 0,
  skipped: 0,
  by_assignee: {},
  by_category: {},
  by_priority: {},
  total_pipeline_inr: 0
};

export default function App() {
  const [stats, setStats] = useState<Stats>(emptyStats);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [skipped, setSkipped] = useState<SkippedEmail[]>([]);
  const [question, setQuestion] = useState("How many high priority tasks do we have?");
  const [chat, setChat] = useState<ChatResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [nextStats, nextTasks, nextSkipped] = await Promise.all([getStats(), getTasks(), getSkipped()]);
      setStats(nextStats);
      setTasks(nextTasks);
      setSkipped(nextSkipped);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to reach backend");
    } finally {
      setLoading(false);
    }
  }

  async function loadDemo() {
    setLoading(true);
    setError(null);
    try {
      await seedDemo();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Demo ingest failed");
      setLoading(false);
    }
  }

  async function submitQuestion(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      setChat(await askQuestion(question));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat request failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  const assigneeRows = useMemo(() => Object.entries(stats.by_assignee), [stats.by_assignee]);

  return (
    <main className="appShell">
      <header className="topbar">
        <div className="brandMark">
          <ShieldCheck size={24} />
        </div>
        <div>
          <h1>Sales Inbox Task Router</h1>
          <p>Auditable routing for RFPs, finance, sponsorships, alliances, and inbox noise.</p>
        </div>
        <div className="actions">
          <button type="button" className="secondary" onClick={refresh} disabled={loading} title="Refresh dashboard">
            <RefreshCw size={17} />
            Refresh
          </button>
          <button type="button" onClick={loadDemo} disabled={loading}>
            <ClipboardList size={17} />
            Load demo
          </button>
        </div>
      </header>

      {error ? <div className="errorBanner">{error}</div> : null}

      <section className="metricsGrid" aria-label="Processing metrics">
        <Metric icon={ClipboardList} label="Emails processed" value={stats.total_emails} />
        <Metric icon={ShieldCheck} label="Tasks created" value={stats.created_tasks} />
        <Metric icon={RefreshCw} label="Thread updates" value={stats.updated_tasks} />
        <Metric icon={AlertTriangle} label="Skipped noise" value={stats.skipped} />
        <Metric icon={IndianRupee} label="Pipeline INR" value={stats.total_pipeline_inr.toLocaleString("en-IN")} />
      </section>

      <section className="contentGrid">
        <section className="panel taskPanel">
          <div className="panelHeader">
            <h2>Routed Tasks</h2>
            <span>{tasks.length} open</span>
          </div>
          <div className="tableWrap">
            <table>
              <thead>
                <tr>
                  <th>Task</th>
                  <th>Owner</th>
                  <th>Priority</th>
                  <th>Company</th>
                  <th>Reason</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <tr key={task.external_task_id}>
                    <td>
                      <strong>{task.title}</strong>
                      <span>{task.thread_id}</span>
                    </td>
                    <td>{task.assignee_id}</td>
                    <td>
                      <span className={`pill ${task.priority}`}>{task.priority}</span>
                    </td>
                    <td>{task.company ?? "Unknown"}</td>
                    <td>{task.reasoning}</td>
                  </tr>
                ))}
                {tasks.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="empty">No routed tasks yet.</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>

        <aside className="panel sidePanel">
          <div className="panelHeader">
            <h2>Assignees</h2>
          </div>
          <div className="assigneeList">
            {assigneeRows.map(([name, count]) => (
              <div className="assigneeRow" key={name}>
                <span>{name}</span>
                <strong>{count}</strong>
              </div>
            ))}
            {assigneeRows.length === 0 ? <p className="muted">No assignments yet.</p> : null}
          </div>
        </aside>
      </section>

      <section className="contentGrid lower">
        <section className="panel">
          <div className="panelHeader">
            <h2>Skipped Log</h2>
            <span>{skipped.length} latest</span>
          </div>
          <div className="skipList">
            {skipped.map((item) => (
              <article key={item.source_email_id} className="skipItem">
                <div>
                  <strong>{item.subject}</strong>
                  <span>{item.from_email}</span>
                </div>
                <p>{item.reason}</p>
                <span className="pill neutral">{item.skip_type}</span>
              </article>
            ))}
            {skipped.length === 0 ? <p className="empty">No skipped emails yet.</p> : null}
          </div>
        </section>

        <section className="panel chatPanel">
          <div className="panelHeader">
            <h2>Grounded Chat</h2>
            <Bot size={20} />
          </div>
          <form onSubmit={submitQuestion} className="chatForm">
            <input value={question} onChange={(event) => setQuestion(event.target.value)} />
            <button type="submit" disabled={loading} title="Ask question">
              <Send size={17} />
              Ask
            </button>
          </form>
          {chat ? (
            <div className="chatAnswer">
              <strong>{chat.answer}</strong>
              <span>Intent: {chat.query_intent}</span>
              <pre>{JSON.stringify(chat.supporting_data, null, 2)}</pre>
            </div>
          ) : (
            <p className="muted">Ask about counts, high priority work, skipped emails, assignees, or pipeline.</p>
          )}
        </section>
      </section>
    </main>
  );
}
