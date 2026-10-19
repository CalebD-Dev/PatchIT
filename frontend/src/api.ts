export type User = {
  id: number;
  name: string;
  email: string;
  role: "Administrator" | "Technician" | "Requester";
  department: string;
};

export type Comment = {
  id: number;
  body: string;
  created_at: string;
  author: User;
};

export type HistoryEvent = {
  id: number;
  action: string;
  details: string;
  created_at: string;
  actor: User;
};

export type Ticket = {
  id: number;
  ticket_number: string;
  title: string;
  description: string;
  device: string;
  category: string;
  priority: "Low" | "Medium" | "High" | "Urgent";
  status: "Open" | "In Progress" | "Waiting" | "Resolved" | "Closed";
  requester: User;
  assignee: User | null;
  created_at: string;
  updated_at: string;
  due_at: string | null;
  closed_at: string | null;
  comments: Comment[];
  history: HistoryEvent[];
};

export type Article = {
  id: number;
  title: string;
  category: string;
  summary: string;
  solution: string;
  search_terms: string;
};

export type Metrics = {
  open_tickets: number;
  high_priority: number;
  overdue: number;
  resolved_this_week: number;
  average_resolution_hours: number | null;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  tickets: (search = "", filters: { status?: string; priority?: string } = {}) => {
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (filters.status) params.set("status", filters.status);
    if (filters.priority) params.set("priority", filters.priority);
    return request<Ticket[]>(`/api/tickets?${params}`);
  },
  users: () => request<User[]>("/api/users"),
  metrics: () => request<Metrics>("/api/dashboard"),
  articles: (search = "") => request<Article[]>(`/api/knowledge?search=${encodeURIComponent(search)}`),
  createTicket: (input: {
    title: string;
    description: string;
    device: string;
    category: string;
    priority: Ticket["priority"];
    requester_id: number;
    assignee_id: number | null;
  }) =>
    request<Ticket>("/api/tickets", {
      method: "POST",
      body: JSON.stringify(input),
    }),
  updateTicket: (
    ticketId: number,
    actorId: number,
    updates: Partial<Pick<Ticket, "title" | "description" | "device" | "category" | "status" | "priority">> & { assignee_id?: number | null },
  ) =>
    request<Ticket>(`/api/tickets/${ticketId}?actor_id=${actorId}`, {
      method: "PATCH",
      body: JSON.stringify(updates),
    }),
  addComment: (ticketId: number, authorId: number, body: string) =>
    request<Comment>(`/api/tickets/${ticketId}/comments`, {
      method: "POST",
      body: JSON.stringify({ author_id: authorId, body }),
    }),
};
