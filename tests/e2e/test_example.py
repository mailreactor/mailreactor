"""
Example E2E test for Mail Reactor.

E2E tests use real servers (Greenmail mock or actual email providers).
These tests are slower but validate the complete system behavior.
"""

import pytest


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_example_e2e():
    """Example E2E test placeholder."""
    # E2E tests will be added after Greenmail setup (Task #3 - deferred)
    assert True


@pytest.mark.e2e
def test_greenmail_imap_connection(greenmail_imap_client):
    """
    Test real IMAP connection to Greenmail.

    Requires Greenmail running:
        cd tests && docker compose -f docker-compose.test.yml up -d

    This test verifies that Greenmail is working and we can connect via IMAP.
    """
    # Search for all messages (should be empty initially)
    messages = greenmail_imap_client.search(["ALL"])
    assert isinstance(messages, list)

    # List folders
    folders = greenmail_imap_client.list_folders()
    assert len(folders) > 0

    # Verify INBOX exists
    folder_names = [f[2] for f in folders]
    assert "INBOX" in folder_names


@pytest.mark.e2e
def test_greenmail_smtp_send(greenmail_smtp_client, greenmail_imap_client):
    """
    Test sending email via SMTP and retrieving via IMAP.

    Requires Greenmail running:
        cd tests && docker compose -f docker-compose.test.yml up -d

    This is a full E2E test of email sending and retrieval.
    """
    from email.message import EmailMessage

    # Create test email
    msg = EmailMessage()
    msg["From"] = "test@localhost"
    msg["To"] = "test@localhost"
    msg["Subject"] = "Greenmail E2E Test"
    msg.set_content("This is a test email sent via Greenmail SMTP")

    # Send email via SMTP
    greenmail_smtp_client.send_message(msg)

    # Wait a moment for email to be delivered
    import time

    time.sleep(1)

    # Retrieve email via IMAP
    messages = greenmail_imap_client.search(["ALL"])
    assert len(messages) > 0, "No messages found after sending"

    # Fetch the latest message
    latest_msg_id = messages[-1]
    msg_data = greenmail_imap_client.fetch(latest_msg_id, ["RFC822"])

    # Verify email content
    email_content = msg_data[latest_msg_id][b"RFC822"]
    assert b"Greenmail E2E Test" in email_content
    assert b"test email sent via Greenmail SMTP" in email_content


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_full_email_journey_placeholder():
    """
    Complete email journey: Add account → Send email → Retrieve email.

    This will be implemented after Epic 2-4 when the Mail Reactor API is built.
    """
    pytest.skip("Mail Reactor API not yet implemented (Epic 2-4)")

    # Future implementation:
    # 1. Add account via API (POST /accounts with Greenmail credentials)
    # 2. Send email via API (POST /messages)
    # 3. Retrieve email via API (GET /messages?filter=UNSEEN)
    # 4. Verify email content matches what was sent


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_provider_compatibility_placeholder():
    """
    Test Gmail/Outlook provider compatibility.

    Requires real test accounts (Phase 2).
    """
    pytest.skip("Real provider testing in Phase 2")

    # Future implementation:
    # 1. Connect to test Gmail account
    # 2. Verify auto-detection works
    # 3. Send test email
    # 4. Retrieve and verify


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_startup_and_shutdown_placeholder():
    """
    Test full application lifecycle: startup → operation → shutdown.

    Validates NFR-P1 (startup time <3 seconds).
    """
    pytest.skip("Application lifecycle testing after Story 1.4")

    # Future implementation:
    # 1. Measure startup time
    # 2. Verify health endpoint responds
    # 3. Gracefully shut down
    # 4. Assert startup < 3 seconds
