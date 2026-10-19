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


def test_create_ticket_enters_the_unassigned_team_queue(client):
    response = client.post(
        "/api/tickets",
        json={
            "title": "Cannot access shared drive",
            "description": "Windows reports that the drive is unavailable.",
            "device": "Dell Latitude",
            "category": "Network",
            "priority": "High",
            "requester_id": 4,
        },
    )

    assert response.status_code == 201
    ticket = response.json()
    assert ticket["ticket_number"].startswith("PIT-")
    assert ticket["status"] == "Open"
    assert ticket["assignee"] is None
    assert ticket["escalated"] is False
    assert ticket["history"][0]["action"] == "Ticket created"
    assert len(ticket["history"]) == 1


def test_ticket_creation_rejects_assignee_for_requesters_and_staff(client):
    payload = {
        "title": "New workstation setup",
        "description": "The new workstation needs software installed.",
        "category": "Software",
        "requester_id": 4,
        "assignee_id": 2,
    }

    requester_response = client.post(
        "/api/tickets",
        json=payload,
        headers={"X-Demo-User-ID": "4"},
    )
    staff_response = client.post(
        "/api/tickets",
        json=payload,
        headers={"X-Demo-User-ID": "1"},
    )

    assert requester_response.status_code == 422
    assert staff_response.status_code == 422
    assert any(
        error["loc"][-1] == "assignee_id"
        for error in staff_response.json()["detail"]
    )


def test_update_ticket_and_add_troubleshooting_note(client):
    update = client.patch(
        "/api/tickets/1?actor_id=2",
        json={"status": "Resolved", "priority": "Medium", "title": "Wi-Fi connection restored"},
        headers={"X-Demo-User-ID": "2"},
    )
    note = client.post(
        "/api/tickets/1/comments",
        json={"author_id": 2, "body": "Updated the wireless driver and confirmed a stable connection."},
        headers={"X-Demo-User-ID": "2"},
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


def test_requesters_only_see_their_own_tickets_and_metrics(client):
    headers = {"X-Demo-User-ID": "4"}

    tickets = client.get("/api/tickets", headers=headers)
    own_ticket = client.get("/api/tickets/1", headers=headers)
    another_requesters_ticket = client.get("/api/tickets/2", headers=headers)
    metrics = client.get("/api/dashboard", headers=headers)

    assert tickets.status_code == 200
    assert {ticket["requester"]["id"] for ticket in tickets.json()} == {4}
    assert len(tickets.json()) == 2
    assert own_ticket.status_code == 200
    assert another_requesters_ticket.status_code == 404
    assert metrics.json()["open_tickets"] == 2
    assert metrics.json()["high_priority"] == 2
    assert metrics.json()["overdue"] == 1
    assert metrics.json()["average_resolution_hours"] is None


def test_technicians_and_administrators_can_see_all_tickets(client):
    technician_tickets = client.get("/api/tickets", headers={"X-Demo-User-ID": "2"})
    administrator_tickets = client.get("/api/tickets", headers={"X-Demo-User-ID": "1"})
    technician_metrics = client.get("/api/dashboard", headers={"X-Demo-User-ID": "2"})
    administrator_metrics = client.get("/api/dashboard", headers={"X-Demo-User-ID": "1"})

    assert technician_tickets.status_code == 200
    assert administrator_tickets.status_code == 200
    assert {ticket["id"] for ticket in technician_tickets.json()} == {1, 3, 5}
    assert len(administrator_tickets.json()) == 6
    assert technician_metrics.json()["open_tickets"] == 2
    assert administrator_metrics.json()["open_tickets"] == 4


def test_technician_can_escalate_and_another_technician_can_claim(client):
    first_technician = {"X-Demo-User-ID": "3"}
    second_technician = {"X-Demo-User-ID": "2"}

    hidden_before_escalation = client.get("/api/tickets/2", headers=second_technician)
    tickets_before_escalation = client.get("/api/tickets", headers=second_technician)
    escalation = client.post("/api/tickets/2/escalate", headers=first_technician)
    visible_after_escalation = client.get("/api/tickets/2", headers=second_technician)
    tickets_after_escalation = client.get("/api/tickets", headers=second_technician)
    note_before_claim = client.post(
        "/api/tickets/2/comments",
        json={"author_id": 2, "body": "Trying to add a note before claiming."},
        headers=second_technician,
    )
    claim = client.post("/api/tickets/2/claim", headers=second_technician)
    hidden_after_claim = client.get("/api/tickets/2", headers=first_technician)

    assert hidden_before_escalation.status_code == 404
    assert 2 not in {ticket["id"] for ticket in tickets_before_escalation.json()}
    assert escalation.status_code == 200
    assert escalation.json()["escalated"] is True
    assert any(event["action"] == "Ticket escalated" for event in escalation.json()["history"])
    assert visible_after_escalation.status_code == 200
    assert 2 in {ticket["id"] for ticket in tickets_after_escalation.json()}
    assert note_before_claim.status_code == 403
    assert claim.status_code == 200
    assert claim.json()["assignee"]["id"] == 2
    assert claim.json()["escalated"] is False
    assert any(event["action"] == "Ticket claimed" for event in claim.json()["history"])
    assert hidden_after_claim.status_code == 404


def test_only_assigned_technician_can_escalate_and_closed_tickets_cannot_be_escalated(client):
    wrong_technician = client.post("/api/tickets/1/escalate", headers={"X-Demo-User-ID": "3"})
    closed_ticket = client.post("/api/tickets/6/escalate", headers={"X-Demo-User-ID": "3"})
    requester = client.post("/api/tickets/1/escalate", headers={"X-Demo-User-ID": "4"})

    assert wrong_technician.status_code == 404
    assert closed_ticket.status_code == 409
    assert requester.status_code == 403


def test_technician_can_claim_an_unassigned_ticket(client):
    created = client.post(
        "/api/tickets",
        json={
            "title": "Unassigned laptop issue",
            "description": "A laptop needs someone to investigate.",
            "category": "Hardware",
            "requester_id": 4,
        },
    )
    ticket_id = created.json()["id"]

    claim = client.post(f"/api/tickets/{ticket_id}/claim", headers={"X-Demo-User-ID": "2"})
    other_technician = client.get(f"/api/tickets/{ticket_id}", headers={"X-Demo-User-ID": "3"})

    assert created.status_code == 201
    assert claim.status_code == 200
    assert claim.json()["assignee"]["id"] == 2
    assert other_technician.status_code == 404


def test_unassigned_ticket_must_be_claimed_before_technician_edits(client):
    created = client.post(
        "/api/tickets",
        json={
            "title": "Unassigned software issue",
            "description": "A requester needs software support.",
            "category": "Software",
            "requester_id": 4,
        },
    )
    ticket_id = created.json()["id"]

    update_before_claim = client.patch(
        f"/api/tickets/{ticket_id}?actor_id=2",
        json={"status": "In Progress"},
        headers={"X-Demo-User-ID": "2"},
    )
    claim = client.post(f"/api/tickets/{ticket_id}/claim", headers={"X-Demo-User-ID": "2"})
    update_after_claim = client.patch(
        f"/api/tickets/{ticket_id}?actor_id=2",
        json={"status": "In Progress"},
        headers={"X-Demo-User-ID": "2"},
    )

    assert update_before_claim.status_code == 403
    assert claim.status_code == 200
    assert update_after_claim.status_code == 200
    assert update_after_claim.json()["status"] == "In Progress"


def test_requester_can_create_only_their_own_unassigned_ticket(client):
    headers = {"X-Demo-User-ID": "4"}
    payload = {
        "title": "My laptop cannot join Wi-Fi",
        "description": "It says it cannot connect to the office wireless network.",
        "device": "Laptop",
        "category": "Network",
        "priority": "Medium",
        "requester_id": 4,
    }

    created = client.post("/api/tickets", json=payload, headers=headers)
    another_requester = client.post(
        "/api/tickets",
        json={**payload, "requester_id": 5},
        headers=headers,
    )
    assignment = client.post(
        "/api/tickets",
        json={**payload, "assignee_id": 2},
        headers=headers,
    )

    assert created.status_code == 201
    assert created.json()["requester"]["id"] == 4
    assert another_requester.status_code == 403
    assert assignment.status_code == 422


def test_requesters_can_comment_on_own_tickets_but_cannot_edit_them(client):
    headers = {"X-Demo-User-ID": "4"}
    note = client.post(
        "/api/tickets/1/comments",
        json={"author_id": 4, "body": "The Wi-Fi dropped again this morning."},
        headers=headers,
    )
    other_ticket_note = client.post(
        "/api/tickets/2/comments",
        json={"author_id": 4, "body": "I cannot see this ticket."},
        headers=headers,
    )
    update = client.patch(
        "/api/tickets/1?actor_id=4",
        json={"status": "Closed"},
        headers=headers,
    )

    assert note.status_code == 201
    assert note.json()["author"]["id"] == 4
    assert other_ticket_note.status_code == 404
    assert update.status_code == 403
