from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import KnowledgeArticle, Ticket, TicketComment, TicketHistory, User, utcnow


def seed_demo_data(db: Session) -> None:
    if db.scalar(select(User.id).limit(1)) is not None:
        return

    users = [
        User(name="Alex Morgan", email="alex.morgan@patchit.local", role="Administrator", department="IT"),
        User(name="Jordan Lee", email="jordan.lee@patchit.local", role="Technician", department="IT Support"),
        User(name="Sam Rivera", email="sam.rivera@patchit.local", role="Technician", department="IT Support"),
        User(name="Taylor Kim", email="taylor.kim@patchit.local", role="Requester", department="Operations"),
        User(name="Casey Patel", email="casey.patel@patchit.local", role="Requester", department="Finance"),
        User(name="Morgan Chen", email="morgan.chen@patchit.local", role="Requester", department="People"),
    ]
    db.add_all(users)
    db.flush()
    now = utcnow()
    tickets = [
        Ticket(title="Unable to connect to office Wi-Fi", description="Laptop disconnects from the staff network every few minutes.", device="Dell Latitude 7440", category="Network", priority="High", status="In Progress", requester_id=4, assignee_id=2, created_at=now - timedelta(hours=3), due_at=now + timedelta(hours=1)),
        Ticket(title="Printer showing as offline", description="The Finance floor printer is powered on but unavailable to the team.", device="HP LaserJet Pro M404", category="Hardware", priority="Medium", status="Open", requester_id=5, assignee_id=3, created_at=now - timedelta(hours=8), due_at=now + timedelta(hours=16)),
        Ticket(title="Password reset request", description="Locked out after several unsuccessful sign-in attempts.", device="Windows workstation", category="Account access", priority="Urgent", status="Open", requester_id=6, assignee_id=2, created_at=now - timedelta(hours=1), due_at=now + timedelta(minutes=30)),
        Ticket(title="Blue screen after Windows update", description="PC restarts with a stop code during startup.", device="Lenovo ThinkPad T14", category="Software", priority="High", status="Waiting", requester_id=4, assignee_id=3, created_at=now - timedelta(days=2), due_at=now - timedelta(hours=2)),
        Ticket(title="New starter account setup", description="Please prepare access for a new member of the Operations team.", device="N/A", category="Account access", priority="Low", status="Resolved", requester_id=5, assignee_id=2, created_at=now - timedelta(days=3), closed_at=now - timedelta(days=2, hours=20), due_at=now - timedelta(days=2)),
        Ticket(title="External monitor not detected", description="Dock connected but the second display is blank.", device="Dell WD19 dock", category="Hardware", priority="Medium", status="Closed", requester_id=6, assignee_id=3, created_at=now - timedelta(days=6), closed_at=now - timedelta(days=5, hours=22), due_at=now - timedelta(days=5)),
    ]
    db.add_all(tickets)
    db.flush()
    db.add_all([
        TicketComment(ticket_id=1, author_id=2, body="Checking signal strength and reviewing the wireless adapter logs."),
        TicketComment(ticket_id=4, author_id=3, body="Requested the stop code from the requester before proceeding."),
    ])
    db.add_all([
        TicketHistory(ticket_id=1, actor_id=2, action="Status changed", details="Open → In Progress"),
        TicketHistory(ticket_id=1, actor_id=2, action="Assigned", details="Assigned to Jordan Lee"),
        TicketHistory(ticket_id=4, actor_id=3, action="Status changed", details="Open → Waiting"),
    ])
    db.add_all([
        KnowledgeArticle(title="Fix common Wi-Fi connection issues", category="Network", summary="Steps for diagnosing intermittent Windows Wi-Fi connections.", search_terms="wifi wi-fi wireless network internet disconnect", solution="1. Confirm airplane mode is off and reconnect to the correct network.\n2. Forget the network, then connect again using the current credentials.\n3. Run the Windows Network troubleshooter and restart the wireless adapter.\n4. If disconnections continue, capture the device name and signal strength for IT."),
        KnowledgeArticle(title="Troubleshoot an offline printer", category="Hardware", summary="Restore a Windows printer that appears offline.", search_terms="printer offline print queue spooler", solution="1. Check that the printer is powered on and connected to the network.\n2. In Settings → Bluetooth & devices → Printers & scanners, open the printer queue.\n3. Clear “Use Printer Offline” and cancel any stuck jobs.\n4. Restart the Print Spooler service if the queue remains stuck."),
        KnowledgeArticle(title="Reset a Windows password", category="Account access", summary="Safely regain access to a locked Windows account.", search_terms="password reset locked account sign in login", solution="1. Verify the user's identity according to your organization's policy.\n2. Use the approved identity-management portal to reset the password.\n3. Ask the user to sign in with the temporary password and set a new one.\n4. Confirm multi-factor authentication still works; never request a password over chat."),
        KnowledgeArticle(title="Resolve common Windows update errors", category="Software", summary="Initial checks for Windows Update failures and startup issues.", search_terms="windows update blue screen bsod stop code driver", solution="1. Record the exact error or stop code before making changes.\n2. Disconnect recently added peripherals and restart the device.\n3. Check update history and install pending driver updates from approved sources.\n4. Escalate recurring blue screens with the stop code and recent change history."),
        KnowledgeArticle(title="Restore access to a work account", category="Account access", summary="Check common causes of account access and MFA problems.", search_terms="account access mfa authentication locked sign in", solution="1. Confirm the username and service being accessed.\n2. Check service status and whether the account is locked or disabled.\n3. Re-register the authenticator only after verifying identity.\n4. Record the affected service and error message in the ticket."),
    ])
    db.commit()
