import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.seed import seed_demo_data


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    with TestingSession() as db:
        seed_demo_data(db)

    def override_get_db():
        with TestingSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    test_client.close()
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_dashboard_uses_ticket_timestamps(client):
    response = client.get("/api/dashboard")

    assert response.status_code == 200
    data = response.json()
    assert data["open_tickets"] == 4
    assert data["high_priority"] == 3
    assert data["overdue"] == 1
    assert data["average_resolution_hours"] == pytest.approx(3, abs=0.01)
    assert isinstance(data["resolved_this_week"], int)


def test_create_ticket_assigns_number_and_writes_history(client):
    response = client.post(
        "/api/tickets",
        json={
            "title": "Cannot access shared drive",
            "description": "Windows reports that the drive is unavailable.",
            "device": "Dell Latitude",
            "category": "Network",
            "priority": "High",
            "requester_id": 4,
            "assignee_id": 2,
        },
    )

    assert response.status_code == 201
    ticket = response.json()
    assert ticket["ticket_number"].startswith("PIT-")
    assert ticket["status"] == "Open"
    assert ticket["assignee"]["id"] == 2
    assert ticket["history"][0]["action"] == "Ticket created"


def test_update_ticket_and_add_troubleshooting_note(client):
    update = client.patch(
        "/api/tickets/1?actor_id=2",
        json={"status": "Resolved", "priority": "Medium", "title": "Wi-Fi connection restored"},
    )
    note = client.post(
        "/api/tickets/1/comments",
        json={"author_id": 2, "body": "Updated the wireless driver and confirmed a stable connection."},
    )

    assert update.status_code == 200
    assert update.json()["status"] == "Resolved"
    assert update.json()["title"] == "Wi-Fi connection restored"
    assert update.json()["closed_at"] is not None
    assert note.status_code == 201
    assert note.json()["author"]["id"] == 2
    detail = client.get("/api/tickets/1").json()
    assert detail["comments"][-1]["body"].startswith("Updated the wireless")
    assert any(item["action"] == "Troubleshooting note" for item in detail["history"])


def test_ticket_search_and_knowledge_base_search(client):
    tickets = client.get("/api/tickets?search=printer")
    articles = client.get("/api/knowledge?search=wifi")

    assert tickets.status_code == 200
    assert len(tickets.json()) == 1
    assert tickets.json()[0]["category"] == "Hardware"
    assert articles.status_code == 200
    assert len(articles.json()) == 1
    assert "Wi-Fi" in articles.json()[0]["title"]
