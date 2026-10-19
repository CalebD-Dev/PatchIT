from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field


Role = Literal["Administrator", "Technician", "Requester"]
Priority = Literal["Low", "Medium", "High", "Urgent"]
Status = Literal["Open", "In Progress", "Waiting", "Resolved", "Closed"]


class UserRead(BaseModel):
    id: int
    name: str
    email: str
    role: Role
    department: str

    model_config = ConfigDict(from_attributes=True)


class CommentRead(BaseModel):
    id: int
    body: str
    created_at: datetime
    author: UserRead

    model_config = ConfigDict(from_attributes=True)


class HistoryRead(BaseModel):
    id: int
    action: str
    details: str
    created_at: datetime
    actor: UserRead

    model_config = ConfigDict(from_attributes=True)


class TicketCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=3)
    device: str = Field(default="", max_length=160)
    category: str = Field(min_length=1, max_length=60)
    priority: Priority = "Medium"
    requester_id: int

    model_config = ConfigDict(extra="forbid")


class TicketUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, min_length=3)
    device: str | None = Field(default=None, max_length=160)
    category: str | None = Field(default=None, min_length=1, max_length=60)
    status: Status | None = None
    priority: Priority | None = None
    assignee_id: int | None = None


class CommentCreate(BaseModel):
    author_id: int
    body: str = Field(min_length=1, max_length=5000)


class KnowledgeArticleRead(BaseModel):
    id: int
    title: str
    category: str
    summary: str
    solution: str
    search_terms: str

    model_config = ConfigDict(from_attributes=True)


class TicketRead(BaseModel):
    id: int
    title: str
    description: str
    device: str
    category: str
    priority: Priority
    status: Status
    escalated: bool
    requester: UserRead
    assignee: UserRead | None
    created_at: datetime
    updated_at: datetime
    due_at: datetime | None
    closed_at: datetime | None
    comments: list[CommentRead]
    history: list[HistoryRead]

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def ticket_number(self) -> str:
        return f"PIT-{self.id:04d}"

    @classmethod
    def from_ticket(cls, ticket):
        return cls.model_validate(ticket)
