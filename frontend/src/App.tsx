import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import {
  Activity,
  AlertTriangle,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  Clock3,
  Laptop,
  LayoutDashboard,
  Plus,
  Search,
  Send,
  Settings2,
  ShieldCheck,
  TicketCheck,
  X,
} from "lucide-react";
import { api, type Article, type Metrics, type Ticket, type User } from "./api";
import type { ReactNode } from "react";

type Page = "tickets" | "knowledge";

function initials(name: string) {
  return name.split(" ").map((part) => part[0]).slice(0, 2).join("").toUpperCase();
}

function avatarTone(name: string) {
  const tones = ["", "teal", "orange", "purple"];
  return tones[name.split("").reduce((sum, letter) => sum + letter.charCodeAt(0), 0) % tones.length];
}

function timeAgo(value: string) {
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 60000));
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function statusClass(status: Ticket["status"]) {
  return {
    Open: "status-open",
    "In Progress": "status-progress",
    Waiting: "status-waiting",
    Resolved: "status-resolved",
    Closed: "status-closed",
  }[status];
}

function priorityClass(priority: Ticket["priority"]) {
  return `priority-${priority.toLowerCase()}`;
}

function Person({ user, unassigned = "Unassigned" }: { user: User | null; unassigned?: string }) {
  if (!user) return <span className="person-name">{unassigned}</span>;
  return (
    <span className="person">
      <span className={`avatar ${avatarTone(user.name)}`}>{initials(user.name)}</span>
      <span className="person-name">{user.name}</span>
    </span>
  );
}

function MetricCard({
  label,
  value,
  caption,
  icon,
  tone = "",
}: {
  label: string;
  value: string | number;
  caption: string;
  icon: ReactNode;
  tone?: string;
}) {
  return (
    <div className="metric-card">
      <div className="metric-head">
        {label}
        <span className={`metric-icon ${tone}`}>{icon}</span>
      </div>
      <div className="metric-value">{value}</div>
      <div className="metric-foot">{caption}</div>
    </div>
  );
}

function App() {
  const [page, setPage] = useState<Page>("tickets");
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [articles, setArticles] = useState<Article[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [selectedTicket, setSelectedTicket] = useState<Ticket | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [articleSearch, setArticleSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const currentUser = users.find((user) => user.role === "Administrator") ?? users[0];
  const requesters = users.filter((user) => user.role === "Requester");
  const technicians = users.filter((user) => user.role === "Technician");

  const loadData = useCallback(async () => {
    setError("");
    try {
      const [ticketList, people, dashboard] = await Promise.all([
        api.tickets(search, { status: statusFilter, priority: priorityFilter }),
        api.users(),
        api.metrics(),
      ]);
      setTickets(ticketList);
      setUsers(people);
      setMetrics(dashboard);
      setLoading(false);
    } catch (cause) {
      setLoading(false);
      setError(cause instanceof Error ? cause.message : "Could not load PatchIT data.");
    }
  }, [search, statusFilter, priorityFilter]);

  useEffect(() => {
    const timeout = window.setTimeout(() => void loadData(), 200);
    return () => window.clearTimeout(timeout);
  }, [loadData]);

  const loadArticles = useCallback(async () => {
    try {
      setArticles(await api.articles(articleSearch));
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not load knowledge articles.");
    }
  }, [articleSearch]);

  useEffect(() => {
    if (page === "knowledge") void loadArticles();
  }, [page, loadArticles]);

  const refreshSelected = useCallback(async (id: number) => {
    try {
      const all = await api.tickets();
      setTickets((previous) => {
        const updated = all.find((ticket) => ticket.id === id);
        if (!updated) return previous;
        return previous.some((ticket) => ticket.id === id)
          ? previous.map((ticket) => (ticket.id === id ? updated : ticket))
          : [updated, ...previous];
      });
      const ticket = all.find((item) => item.id === id);
      if (ticket) setSelectedTicket(ticket);
      await loadData();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not refresh the ticket.");
    }
  }, [loadData]);

  const openTicketCount = metrics?.open_tickets ?? 0;
  const pageTitle = page === "tickets" ? "Ticket overview" : "Knowledge base";
  const activeTickets = useMemo(
    () => tickets.filter((ticket) => ticket.status !== "Closed" && ticket.status !== "Resolved").length,
    [tickets],
  );
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  const dateLabel = new Intl.DateTimeFormat("en", {
    weekday: "long",
    month: "long",
    day: "numeric",
  }).format(new Date()).toUpperCase();

  async function handleCreate(input: Parameters<typeof api.createTicket>[0]) {
    setBusy(true);
    try {
      const created = await api.createTicket(input);
      setShowCreate(false);
      setPage("tickets");
      setSearch("");
      setStatusFilter("");
      setPriorityFilter("");
      await loadData();
      setSelectedTicket(created);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Ticket could not be created.");
    } finally {
      setBusy(false);
    }
  }

  async function updateSelected(
    updates: Parameters<typeof api.updateTicket>[2],
  ) {
    if (!selectedTicket || !currentUser) return;
    setBusy(true);
    try {
      const updated = await api.updateTicket(selectedTicket.id, currentUser.id, updates);
      setSelectedTicket(updated);
      await loadData();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Ticket could not be updated.");
    } finally {
      setBusy(false);
    }
  }

  async function addComment(body: string) {
    if (!selectedTicket || !currentUser) return;
    setBusy(true);
    try {
      await api.addComment(selectedTicket.id, currentUser.id, body);
      await refreshSelected(selectedTicket.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Note could not be added.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark"><WrenchMark /></span>
          <span className="brand-name">PatchIT</span>
        </div>
        <div className="nav-label">Workspace</div>
        <nav className="nav-list">
          <button className={`nav-item ${page === "tickets" ? "active" : ""}`} onClick={() => setPage("tickets")}>
            <LayoutDashboard size={17} /><span>Dashboard</span><span className="nav-count">{openTicketCount}</span>
          </button>
          <button className={`nav-item ${page === "knowledge" ? "active" : ""}`} onClick={() => setPage("knowledge")}>
            <BookOpen size={17} /><span>Knowledge base</span>
          </button>
        </nav>
        <div className="sidebar-bottom">
          <div className="nav-label">Support</div>
          <button className="nav-item" onClick={() => setPage("knowledge")}><CircleHelp size={17} /><span>Help center</span></button>
          <div className="help-card">
            <ShieldCheck size={16} color="#90aaf0" />
            <strong>Keep work moving</strong>
            <p>Find a fix or follow up on a support request.</p>
          </div>
          {currentUser && (
            <div className="profile">
              <span className={`avatar ${avatarTone(currentUser.name)}`}>{initials(currentUser.name)}</span>
              <span className="profile-copy"><strong>{currentUser.name}</strong><span>{currentUser.role}</span></span>
              <button className="icon-button" title="Profile options"><ChevronDown size={14} /></button>
            </div>
          )}
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="breadcrumbs">Workspace <span style={{ padding: "0 8px", color: "#c4c9d0" }}>/</span> <strong>{pageTitle}</strong></div>
          <div className="top-actions">
            <button className="icon-button" title="Settings"><Settings2 size={17} /></button>
            <button className="icon-button" title="Notifications"><Activity size={17} /><span className="notification-dot" /></button>
            {currentUser && <span className={`avatar ${avatarTone(currentUser.name)}`}>{initials(currentUser.name)}</span>}
          </div>
        </header>

        <section className="content">
          {error && <div className="alert" role="alert">{error}</div>}
          {page === "tickets" ? (
            <>
              <div className="heading-row">
                <div>
                  <p className="eyebrow">{dateLabel}</p>
                  <h1>{greeting}{currentUser ? `, ${currentUser.name.split(" ")[0]}` : ""}</h1>
                  <p className="subtitle">Here&apos;s what&apos;s happening across your support desk today.</p>
                </div>
                <button className="primary-button" onClick={() => setShowCreate(true)}><Plus size={15} /> New ticket</button>
              </div>

              <div className="metrics">
                <MetricCard label="Open tickets" value={metrics?.open_tickets ?? "—"} caption={`${activeTickets} shown in this view`} icon={<TicketCheck size={15} />} />
                <MetricCard label="High priority" value={metrics?.high_priority ?? "—"} caption="Active high & urgent incidents" icon={<AlertTriangle size={15} />} tone="coral" />
                <MetricCard label="Overdue tickets" value={metrics?.overdue ?? "—"} caption="Past their target resolution time" icon={<Clock3 size={15} />} tone="amber" />
                <MetricCard
                  label="Resolved this week"
                  value={metrics?.resolved_this_week ?? "—"}
                  caption={metrics?.average_resolution_hours == null ? "No resolution history yet" : `Avg. resolution ${metrics.average_resolution_hours < 1 ? `${Math.round(metrics.average_resolution_hours * 60)}m` : `${metrics.average_resolution_hours.toFixed(1)}h`}`}
                  icon={<CheckCircle2 size={15} />}
                  tone="green"
                />
              </div>

              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <div className="panel-title">Recent tickets</div>
                    <div className="panel-subtitle">Track, assign, and resolve support requests</div>
                  </div>
                  <div className="panel-heading-actions">
                    <label className="search-box"><Search size={14} /><input aria-label="Search tickets" placeholder="Search tickets..." value={search} onChange={(event) => setSearch(event.target.value)} /></label>
                    <select className="filter-select" aria-label="Filter by status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                      <option value="">All statuses</option>
                      <option>Open</option><option>In Progress</option><option>Waiting</option><option>Resolved</option><option>Closed</option>
                    </select>
                    <select className="filter-select" aria-label="Filter by priority" value={priorityFilter} onChange={(event) => setPriorityFilter(event.target.value)}>
                      <option value="">All priority</option>
                      <option>Urgent</option><option>High</option><option>Medium</option><option>Low</option>
                    </select>
                  </div>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead><tr><th>Ticket</th><th>Requester</th><th>Assignee</th><th>Priority</th><th>Status</th><th>Created</th></tr></thead>
                    <tbody>
                      {loading ? (
                        <tr><td colSpan={6}><div className="loading">Loading tickets…</div></td></tr>
                      ) : tickets.length === 0 ? (
                        <tr><td colSpan={6}><div className="empty-state"><strong>No tickets found</strong>Try a different search or create a new request.</div></td></tr>
                      ) : tickets.map((ticket) => (
                        <tr key={ticket.id} onClick={() => setSelectedTicket(ticket)}>
                          <td><div className="ticket-id">{ticket.ticket_number}</div><div className="ticket-title" title={ticket.title}>{ticket.title}</div><div className="ticket-category">{ticket.category}{ticket.device ? ` · ${ticket.device}` : ""}</div></td>
                          <td><Person user={ticket.requester} /></td>
                          <td><Person user={ticket.assignee} /></td>
                          <td><span className={priorityClass(ticket.priority)}>{ticket.priority}</span></td>
                          <td><span className={`badge ${statusClass(ticket.status)}`}>{ticket.status}</span></td>
                          <td>
                            <div>{timeAgo(ticket.created_at)}</div>
                            {ticket.due_at && !ticket.closed_at && (
                              <div className={`ticket-category ${new Date(ticket.due_at).getTime() < Date.now() ? "due-over" : ""}`}>
                                {new Date(ticket.due_at).getTime() < Date.now() ? "Overdue" : `Due ${timeAgo(ticket.due_at)}`}
                              </div>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="table-footer"><span>Showing {tickets.length} ticket{tickets.length === 1 ? "" : "s"}</span><span>Updates in real time</span></div>
              </section>
            </>
          ) : (
            <>
              <div className="heading-row">
                <div><p className="eyebrow">PATCHIT RESOURCES</p><h1>Knowledge base</h1><p className="subtitle">Quick, trusted fixes for common IT issues.</p></div>
              </div>
              <div className="page-toolbar">
                <label className="search-box" style={{ width: "min(100%, 360px)", height: 40 }}><Search size={15} /><input aria-label="Search knowledge base" placeholder="Search Wi-Fi, printers, passwords..." value={articleSearch} onChange={(event) => setArticleSearch(event.target.value)} /></label>
                <span style={{ alignSelf: "center", color: "#8c95a0", fontSize: 11 }}>{articles.length} articles</span>
              </div>
              {loading && articles.length === 0 ? <div className="loading">Loading articles…</div> : (
                <div className="knowledge-grid">
                  {articles.map((article) => (
                    <article className="article-card" key={article.id}>
                      <span className="article-category">{article.category}</span>
                      <h3>{article.title}</h3>
                      <p>{article.summary}</p>
                      <details><summary>View troubleshooting steps</summary><p className="solution">{article.solution}</p></details>
                    </article>
                  ))}
                  {articles.length === 0 && <div className="panel empty-state" style={{ gridColumn: "1 / -1" }}><strong>No matching articles</strong>Try a different search term.</div>}
                </div>
              )}
            </>
          )}
        </section>
      </main>

      {showCreate && requesters.length > 0 && (
        <CreateTicketModal
          busy={busy}
          requesters={requesters}
          technicians={technicians}
          onClose={() => setShowCreate(false)}
          onSubmit={handleCreate}
        />
      )}
      {selectedTicket && currentUser && (
        <TicketDetails
          ticket={selectedTicket}
          users={users}
          currentUser={currentUser}
          busy={busy}
          onClose={() => setSelectedTicket(null)}
          onUpdate={updateSelected}
          onComment={addComment}
        />
      )}
    </div>
  );
}

function CreateTicketModal({
  busy,
  requesters,
  technicians,
  onClose,
  onSubmit,
}: {
  busy: boolean;
  requesters: User[];
  technicians: User[];
  onClose: () => void;
  onSubmit: (input: Parameters<typeof api.createTicket>[0]) => Promise<void>;
}) {
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    await onSubmit({
      title: String(form.get("title")).trim(),
      description: String(form.get("description")).trim(),
      device: String(form.get("device")).trim(),
      category: String(form.get("category")),
      priority: String(form.get("priority")) as Ticket["priority"],
      requester_id: Number(form.get("requester_id")),
      assignee_id: form.get("assignee_id") ? Number(form.get("assignee_id")) : null,
    });
  }

  return (
    <div className="overlay" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <form className="modal" onSubmit={(event) => void submit(event)}>
        <div className="modal-header"><div><h2>Create a support ticket</h2><p>Share a few details so the team can get started.</p></div><button type="button" className="close-button" aria-label="Close" onClick={onClose}><X size={17} /></button></div>
        <div className="form-body">
          <div className="field"><label htmlFor="ticket-title">Issue title</label><input id="ticket-title" name="title" maxLength={200} minLength={3} placeholder="What do you need help with?" required /></div>
          <div className="field"><label htmlFor="ticket-description">Description</label><textarea id="ticket-description" name="description" minLength={3} placeholder="Include any error messages and what you've tried so far..." required /></div>
          <div className="form-grid">
            <div className="field"><label htmlFor="ticket-device">Affected device</label><input id="ticket-device" name="device" maxLength={160} placeholder="e.g. Dell Latitude 7440" /></div>
            <div className="field"><label htmlFor="ticket-category">Category</label><select id="ticket-category" name="category" required><option value="">Choose category</option><option>Hardware</option><option>Software</option><option>Network</option><option>Account access</option><option>Other</option></select></div>
            <div className="field"><label htmlFor="ticket-priority">Priority</label><select id="ticket-priority" name="priority" defaultValue="Medium"><option>Low</option><option>Medium</option><option>High</option><option>Urgent</option></select></div>
            <div className="field"><label htmlFor="ticket-requester">Requester</label><select id="ticket-requester" name="requester_id" defaultValue={requesters[0].id}>{requesters.map((user) => <option key={user.id} value={user.id}>{user.name}</option>)}</select></div>
            <div className="field"><label htmlFor="ticket-assignee">Assign technician</label><select id="ticket-assignee" name="assignee_id" defaultValue=""><option value="">Unassigned</option>{technicians.map((user) => <option key={user.id} value={user.id}>{user.name}</option>)}</select></div>
          </div>
        </div>
        <div className="modal-footer"><button type="button" className="secondary-button" onClick={onClose}>Cancel</button><button className="primary-button" disabled={busy}><Plus size={14} /> Create ticket</button></div>
      </form>
    </div>
  );
}

function TicketDetails({
  ticket,
  users,
  currentUser,
  busy,
  onClose,
  onUpdate,
  onComment,
}: {
  ticket: Ticket;
  users: User[];
  currentUser: User;
  busy: boolean;
  onClose: () => void;
  onUpdate: (updates: Parameters<typeof api.updateTicket>[2]) => Promise<void>;
  onComment: (body: string) => Promise<void>;
}) {
  const [comment, setComment] = useState("");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({
    title: ticket.title,
    description: ticket.description,
    device: ticket.device,
    category: ticket.category,
  });
  const technicians = users.filter((user) => user.role === "Technician" || user.role === "Administrator");

  async function submitComment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body = comment.trim();
    if (!body) return;
    await onComment(body);
    setComment("");
  }

  async function saveDetails(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onUpdate(draft);
    setEditing(false);
  }

  return (
    <div className="overlay" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="modal" aria-label={`Ticket ${ticket.ticket_number}`}>
        <div className="modal-header"><div><h2>{ticket.title}</h2><p>{ticket.ticket_number} · opened {timeAgo(ticket.created_at)}</p></div><div style={{ display: "flex", gap: 6 }}><button type="button" className="secondary-button" onClick={() => setEditing((value) => !value)}>{editing ? "Cancel edit" : "Edit details"}</button><button type="button" className="close-button" aria-label="Close" onClick={onClose}><X size={17} /></button></div></div>
        <div className="detail-meta"><span className={`badge ${statusClass(ticket.status)}`}>{ticket.status}</span><span className={priorityClass(ticket.priority)}>{ticket.priority} priority</span><span style={{ color: "#8d95a0", fontSize: 10 }}>{ticket.category}{ticket.device ? ` · ${ticket.device}` : ""}</span></div>
        {editing ? (
          <form className="detail-edit-form" onSubmit={(event) => void saveDetails(event)}>
            <div className="field"><label htmlFor="edit-title">Issue title</label><input id="edit-title" value={draft.title} minLength={3} maxLength={200} required onChange={(event) => setDraft({ ...draft, title: event.target.value })} /></div>
            <div className="field"><label htmlFor="edit-description">Description</label><textarea id="edit-description" value={draft.description} minLength={3} required onChange={(event) => setDraft({ ...draft, description: event.target.value })} /></div>
            <div className="form-grid">
              <div className="field"><label htmlFor="edit-device">Affected device</label><input id="edit-device" value={draft.device} maxLength={160} onChange={(event) => setDraft({ ...draft, device: event.target.value })} /></div>
              <div className="field"><label htmlFor="edit-category">Category</label><input id="edit-category" value={draft.category} minLength={1} maxLength={60} required onChange={(event) => setDraft({ ...draft, category: event.target.value })} /></div>
            </div>
            <div style={{ display: "flex", justifyContent: "flex-end" }}><button className="primary-button" type="submit" disabled={busy}>Save details</button></div>
          </form>
        ) : <div className="detail-description">{ticket.description}</div>}
        <div className="detail-fields">
          <div className="field"><label htmlFor="detail-status">Status</label><select id="detail-status" value={ticket.status} disabled={busy} onChange={(event) => void onUpdate({ status: event.target.value as Ticket["status"] })}><option>Open</option><option>In Progress</option><option>Waiting</option><option>Resolved</option><option>Closed</option></select></div>
          <div className="field"><label htmlFor="detail-priority">Priority</label><select id="detail-priority" value={ticket.priority} disabled={busy} onChange={(event) => void onUpdate({ priority: event.target.value as Ticket["priority"] })}><option>Low</option><option>Medium</option><option>High</option><option>Urgent</option></select></div>
          <div className="field"><label htmlFor="detail-assignee">Assignee</label><select id="detail-assignee" value={ticket.assignee?.id ?? ""} disabled={busy} onChange={(event) => void onUpdate({ assignee_id: event.target.value ? Number(event.target.value) : null })}><option value="">Unassigned</option>{technicians.map((user) => <option key={user.id} value={user.id}>{user.name}</option>)}</select></div>
        </div>
        <div className="detail-history">
          <h3>Activity & troubleshooting</h3>
          {[...ticket.history].reverse().map((event) => (
            <div className="timeline-item" key={`history-${event.id}`}><span className="timeline-dot" /><div><p><strong>{event.actor.name}</strong> · {event.action}: {event.details}</p><time>{timeAgo(event.created_at)}</time></div></div>
          ))}
          {ticket.history.length === 0 && <p style={{ color: "#929aa5", fontSize: 10 }}>No activity recorded yet.</p>}
        </div>
        <div className="detail-comments">
          <h3>Technician notes & replies</h3>
          {ticket.comments.map((entry) => (
            <div className="comment" key={entry.id}><strong>{entry.author.name}</strong><time>{timeAgo(entry.created_at)}</time><p>{entry.body}</p></div>
          ))}
          <form className="comment-form" onSubmit={(event) => void submitComment(event)}>
            <textarea aria-label="Add troubleshooting note" value={comment} onChange={(event) => setComment(event.target.value)} maxLength={5000} placeholder={`Add a note as ${currentUser.name}...`} />
            <button className="primary-button" type="submit" disabled={busy || !comment.trim()} aria-label="Add note"><Send size={14} /></button>
          </form>
        </div>
      </section>
    </div>
  );
}

function WrenchMark() {
  return <Laptop size={18} strokeWidth={2.3} />;
}

export default App;
