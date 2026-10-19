from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.config import settings
from app.database import SessionLocal, get_db
from app.models import KnowledgeArticle, Ticket, TicketComment, TicketHistory, User, utcnow
from app.schemas import (
    CommentCreate,
    CommentRead,
    KnowledgeArticleRead,
    TicketCreate,
    TicketRead,
    TicketUpdate,
    UserRead,
)
from app.seed import seed_demo_data


@asynccontextmanager
async def lifespan(_: FastAPI):
    with SessionLocal() as db:
        seed_demo_data(db)
    yield


app = FastAPI(title="PatchIT API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)


def ticket_query():
    return select(Ticket).options(
        joinedload(Ticket.requester),
        joinedload(Ticket.assignee),
        selectinload(Ticket.comments).joinedload(TicketComment.author),
        selectinload(Ticket.history).joinedload(TicketHistory.actor),
    )


def get_ticket_or_404(db: Session, ticket_id: int) -> Ticket:
    ticket = db.scalar(ticket_query().where(Ticket.id == ticket_id))
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


def add_history(db: Session, ticket: Ticket, actor_id: int, action: str, details: str) -> None:
    if db.get(User, actor_id) is None:
        raise HTTPException(status_code=422, detail="Actor not found")
    db.add(TicketHistory(ticket=ticket, actor_id=actor_id, action=action, details=details))


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/users", response_model=list[UserRead])
def list_users(db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.name)).all()


@app.get("/api/tickets", response_model=list[TicketRead])
def list_tickets(
    search: str = Query(default="", max_length=200),
    status_filter: str = Query(default="", alias="status"),
    priority: str = "",
    category: str = "",
    db: Session = Depends(get_db),
):
    query = ticket_query()
    if search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Ticket.title.ilike(term),
                Ticket.description.ilike(term),
                Ticket.device.ilike(term),
                Ticket.category.ilike(term),
                Ticket.requester.has(User.name.ilike(term)),
                Ticket.assignee.has(User.name.ilike(term)),
            )
        )
    if status_filter:
        query = query.where(Ticket.status == status_filter)
    if priority:
        query = query.where(Ticket.priority == priority)
    if category:
        query = query.where(Ticket.category == category)
    return [TicketRead.from_ticket(ticket) for ticket in db.scalars(query.order_by(Ticket.created_at.desc())).unique().all()]


@app.post("/api/tickets", response_model=TicketRead, status_code=status.HTTP_201_CREATED)
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db)):
    requester = db.get(User, payload.requester_id)
    if requester is None or requester.role != "Requester":
        raise HTTPException(status_code=422, detail="Requester must be a requester account")
    if payload.assignee_id is not None:
        assignee = db.get(User, payload.assignee_id)
        if assignee is None or assignee.role not in ("Technician", "Administrator"):
            raise HTTPException(status_code=422, detail="Assignee must be a technician or administrator")
    ticket = Ticket(**payload.model_dump(), due_at=utcnow() + timedelta(hours=24))
    db.add(ticket)
    db.flush()
    add_history(db, ticket, payload.requester_id, "Ticket created", f"Created by {requester.name}")
    if ticket.assignee_id is not None:
        assignee = db.get(User, ticket.assignee_id)
        add_history(db, ticket, payload.requester_id, "Assignment changed", f"Unassigned → {assignee.name}")
    db.commit()
    return TicketRead.from_ticket(get_ticket_or_404(db, ticket.id))


@app.get("/api/tickets/{ticket_id}", response_model=TicketRead)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    return TicketRead.from_ticket(get_ticket_or_404(db, ticket_id))


@app.patch("/api/tickets/{ticket_id}", response_model=TicketRead)
def update_ticket(ticket_id: int, payload: TicketUpdate, actor_id: int = Query(...), db: Session = Depends(get_db)):
    ticket = get_ticket_or_404(db, ticket_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="At least one field must be updated")
    if any(field != "assignee_id" and value is None for field, value in changes.items()):
        raise HTTPException(status_code=422, detail="Status and priority cannot be cleared")
    if db.get(User, actor_id) is None:
        raise HTTPException(status_code=422, detail="Actor not found")
    for field, value in changes.items():
        if field == "assignee_id" and value is not None:
            assignee = db.get(User, value)
            if assignee is None or assignee.role not in ("Technician", "Administrator"):
                raise HTTPException(status_code=422, detail="Assignee must be a technician or administrator")
        old_value = getattr(ticket, field)
        if old_value == value:
            continue
        setattr(ticket, field, value)
        label = "Assignee" if field == "assignee_id" else field.replace("_", " ").capitalize()
        if field == "assignee_id":
            old_name = db.get(User, old_value).name if old_value else "Unassigned"
            new_name = db.get(User, value).name if value else "Unassigned"
            details = f"{old_name} → {new_name}"
            action = "Assignment changed"
        else:
            details = f"{old_value} → {value}"
            action = f"{label} changed"
        add_history(db, ticket, actor_id, action, details)
        if field == "status" and value in ("Resolved", "Closed") and ticket.closed_at is None:
            ticket.closed_at = utcnow()
        elif field == "status" and old_value in ("Resolved", "Closed"):
            ticket.closed_at = None
    db.commit()
    return TicketRead.from_ticket(get_ticket_or_404(db, ticket.id))


@app.post("/api/tickets/{ticket_id}/comments", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
def add_comment(ticket_id: int, payload: CommentCreate, db: Session = Depends(get_db)):
    ticket = get_ticket_or_404(db, ticket_id)
    if db.get(User, payload.author_id) is None:
        raise HTTPException(status_code=422, detail="Comment author not found")
    comment = TicketComment(ticket=ticket, author_id=payload.author_id, body=payload.body)
    db.add(comment)
    db.flush()
    add_history(db, ticket, payload.author_id, "Troubleshooting note", "Added a note")
    db.commit()
    db.refresh(comment)
    return comment


@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)):
    now = utcnow()
    week_start = now - timedelta(days=now.weekday(), hours=now.hour, minutes=now.minute, seconds=now.second, microseconds=now.microsecond)
    active = Ticket.status.notin_(("Resolved", "Closed"))
    resolved_tickets = db.execute(
        select(Ticket.created_at, Ticket.closed_at).where(Ticket.closed_at.is_not(None))
    ).all()
    resolution_hours = [
        (closed_at - created_at).total_seconds() / 3600
        for created_at, closed_at in resolved_tickets
    ]
    average_resolution_hours = (
        sum(resolution_hours) / len(resolution_hours) if resolution_hours else None
    )
    return {
        "open_tickets": db.scalar(select(func.count()).select_from(Ticket).where(active)) or 0,
        "high_priority": db.scalar(select(func.count()).select_from(Ticket).where(active, Ticket.priority.in_(("High", "Urgent")))) or 0,
        "overdue": db.scalar(select(func.count()).select_from(Ticket).where(active, Ticket.due_at < now)) or 0,
        "resolved_this_week": db.scalar(select(func.count()).select_from(Ticket).where(Ticket.closed_at >= week_start, Ticket.closed_at <= now)) or 0,
        "average_resolution_hours": average_resolution_hours,
    }


@app.get("/api/knowledge", response_model=list[KnowledgeArticleRead])
def search_knowledge(search: str = Query(default="", max_length=200), db: Session = Depends(get_db)):
    query = select(KnowledgeArticle)
    if search.strip():
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                KnowledgeArticle.title.ilike(term),
                KnowledgeArticle.category.ilike(term),
                KnowledgeArticle.summary.ilike(term),
                KnowledgeArticle.solution.ilike(term),
                KnowledgeArticle.search_terms.ilike(term),
            )
        )
    return db.execute(query.order_by(KnowledgeArticle.category, KnowledgeArticle.title)).scalars().all()
