# Mail Reactor Test Suite

**Project:** Mail Reactor - Headless Email Client  
**Date:** 2025-11-27  
**Test Framework:** pytest + pytest-asyncio

---

## 📋 Testing Philosophy

Mail Reactor follows **Test-Driven Development (TDD)** with a balanced test pyramid optimized for API backends.

### Test Distribution

| Test Level | Percentage | Speed | Focus |
|-----------|-----------|-------|-------|
| **Unit** | 50% | <1ms | Business logic, models, utilities |
| **Integration** | 35% | ~100ms | API endpoints with Python mocks |
| **E2E** | 15% | ~5s | Critical paths with real/mock servers |

**Rationale:**
- **High unit %** - Heavy business logic (provider detection, IMAP query building, email parsing)
- **Moderate integration %** - API-centric architecture benefits from endpoint testing
- **Low E2E %** - Stateless design reduces need for extensive end-to-end tests

---

## 🗂️ Test Organization

```
tests/
├── conftest.py           # Shared fixtures (mock IMAP/SMTP, API client)
├── test_smoke.py         # Basic smoke test
├── README.md            # This file
│
├── unit/                # Unit tests (50% of suite)
│   └── __init__.py
│
├── integration/         # Integration tests (35% of suite)
│   └── __init__.py
│
├── e2e/                 # End-to-end tests (15% of suite)
│   └── __init__.py
│
├── performance/         # Performance benchmarks
│   └── __init__.py
│
└── security/            # Security tests
    └── __init__.py
```

---

## 🧪 Test Levels Explained

### Unit Tests (`tests/unit/`)

**Purpose:** Test pure Python business logic in isolation

**Characteristics:**
- ✅ Fast (<1ms per test)
- ✅ No network, no file I/O
- ✅ Use Python mocks for external dependencies
- ✅ High coverage target (80%+ per NFR-M1)

**What to Test:**
- Provider auto-detection logic (Gmail domain → IMAP/SMTP settings)
- IMAP search query construction (`UNSEEN FROM addr SINCE date`)
- Email message parsing (headers, body, attachments)
- Pydantic model validation (AccountCredentials, Message)
- Error classification (IMAPException → MailReactorException)
- Utilities (timestamp formatting, logging config)

**Example:**
```python
# tests/unit/test_provider_detection.py
def test_gmail_domain_detection():
    """Gmail domains should auto-detect imap.gmail.com settings"""
    settings = detect_provider_settings("user@gmail.com")
    assert settings.imap_host == "imap.gmail.com"
    assert settings.imap_port == 993
    assert settings.imap_ssl is True
```

**Run Unit Tests:**
```bash
pytest tests/unit/ -v
```

---

### Integration Tests (`tests/integration/`)

**Purpose:** Test API endpoints with mocked IMAP/SMTP services

**Characteristics:**
- ✅ Moderate speed (~100ms per test)
- ✅ FastAPI TestClient (in-memory HTTP)
- ✅ Python mocks for IMAP/SMTP (NO Greenmail yet)
- ✅ Focus on API contracts and error handling

**What to Test:**
- `POST /accounts` with mock IMAP connection
- `GET /messages?filter=UNSEEN` with mock IMAP search
- `POST /messages` (send email) with mock SMTP
- `/health` endpoint (no mocks - real health check)
- Error responses (401 auth failures, 400 validation errors)
- Async patterns (concurrent API requests)

**Example:**
```python
# tests/integration/test_account_api.py
@pytest.mark.asyncio
async def test_add_account_success(api_client, mock_async_imap_client):
    """POST /accounts should connect to IMAP and store credentials"""
    # Mock IMAP connection succeeds
    mock_async_imap_client.connect.return_value = True
    
    response = await api_client.post("/accounts", json={
        "email": "test@example.com",
        "password": "test123"
    })
    
    assert response.status_code == 201
    assert response.json()["email"] == "test@example.com"
    mock_async_imap_client.connect.assert_called_once()
```

**Run Integration Tests:**
```bash
pytest tests/integration/ -v
```

---

### E2E Tests (`tests/e2e/`)

**Purpose:** Test critical user journeys with real/mock servers

**Characteristics:**
- ⏱️ Slow (~5s per test due to IMAP connection)
- 🌐 Real IMAP/SMTP servers (Greenmail or test accounts)
- 🔄 Full application lifecycle (startup → operation → shutdown)
- 🎯 Focus on happy paths and critical risks

**What to Test:**
- Add Gmail account → auto-detect → connect → verify
- Send email → SMTP transmission → message ID returned
- Retrieve unread emails → IMAP search → JSON response
- Provider compatibility (Gmail, Outlook, self-hosted)
- NFR validation (startup time, API latency, stability)

**Tools:**
- **Greenmail** (mock IMAP/SMTP server in Docker) - Coming in future task
- **Real test accounts** (Phase 2)
- **Dovecot container** (self-hosted IMAP testing)

**Example:**
```python
# tests/e2e/test_email_journey.py
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_send_and_retrieve_email():
    """Full journey: Add account → Send email → Retrieve email"""
    # Note: Requires Greenmail running (Task #3 - deferred)
    pytest.skip("Greenmail setup pending - Task #3")
```

**Run E2E Tests:**
```bash
pytest tests/e2e/ -v -m e2e
```

---

### Performance Tests (`tests/performance/`)

**Purpose:** Validate NFR performance requirements

**What to Test:**
- NFR-P1: Startup time <3 seconds
- NFR-P2: API response <200ms p95
- NFR-P3: IMAP search <2 seconds
- NFR-P4: Memory footprint <100MB
- NFR-P6: 24-hour stability (4h proxy in CI)

**Tools:**
- `pytest-benchmark` for automated benchmarking
- `psutil` for memory profiling
- GitHub Actions for CI tracking

**Example:**
```python
# tests/performance/test_startup.py
@pytest.mark.benchmark
def test_startup_time_under_3_seconds(benchmark):
    """Startup time should be <3s per NFR-P1"""
    def startup():
        from mailreactor.main import app
        return app
    
    result = benchmark(startup)
    assert benchmark.stats.median < 3.0
```

**Run Performance Tests:**
```bash
pytest tests/performance/ --benchmark-only
```

---

### Security Tests (`tests/security/`)

**Purpose:** Validate security requirements (credential handling, API keys)

**What to Test:**
- NFR-S1: Credentials never logged or exposed
- NFR-S2: API key hashing (bcrypt)
- NFR-S4: Dependency vulnerabilities
- Password leak detection in logs/responses

**Tools:**
- `detect-secrets` (pre-commit hook)
- Log scanning for credential patterns
- Future: `pip-audit` (dependency scanning - replaced safety which requires auth)

**Example:**
```python
# tests/security/test_credential_leaks.py
def test_credentials_not_in_logs(caplog):
    """Verify passwords never appear in logs"""
    logger.info("account_connected", email="test@example.com")
    assert "password" not in caplog.text.lower()
```

**Run Security Tests:**
```bash
pytest tests/security/ -v -m security
```

---

## 🚀 Running Tests

### Run All Tests
```bash
pytest
```

### Run by Test Level
```bash
pytest tests/unit/          # Fast feedback (<1s)
pytest tests/integration/   # API validation (~5s)
pytest tests/e2e/           # Full stack (~30s)
```

### Run by Marker
```bash
pytest -m unit              # Only unit tests
pytest -m integration       # Only integration tests
pytest -m e2e               # Only E2E tests
pytest -m benchmark         # Only performance tests
pytest -m security          # Only security tests
```

### Run with Coverage
```bash
pytest --cov=src/mailreactor --cov-report=html
open htmlcov/index.html
```

### Run Specific Test
```bash
pytest tests/unit/test_provider.py::test_gmail_detection -v
```

---

## 📊 Coverage Requirements

**Minimum Coverage:** 80% (NFR-M1 requirement)

**Enforced by:**
- Pre-commit hook (`pytest --cov-fail-under=80`)
- CI pipeline (GitHub Actions)

**Check Coverage:**
```bash
pytest --cov=src/mailreactor --cov-report=term-missing
```

**Generate HTML Report:**
```bash
pytest --cov=src/mailreactor --cov-report=html
open htmlcov/index.html
```

---

## 🔧 Test Fixtures

All shared fixtures are in `tests/conftest.py`:

### FastAPI Test Client
- `api_client` - Async HTTP client for API testing

### Mock IMAP Clients
- `mock_imap_client` - Sync mock (unit tests)
- `mock_async_imap_client` - Async mock (integration tests)

### Mock SMTP Clients
- `mock_smtp_client` - Sync mock (unit tests)
- `mock_async_smtp_client` - Async mock (integration tests)

### Mock Data
- `mock_account_credentials` - Fake account credentials
- `mock_gmail_credentials` - Fake Gmail credentials
- `mock_email_message` - Sample email message
- `mock_email_with_attachment` - Email with attachment

**Usage Example:**
```python
def test_with_fixture(mock_account_credentials):
    creds = mock_account_credentials
    assert creds['email'] == 'test@example.com'
```

---

## 🎯 TDD Workflow

Mail Reactor follows **strict TDD** (test-first development):

### 1. RED - Write Failing Test
```python
def test_provider_detection():
    """Gmail domain should be detected"""
    result = detect_provider("user@gmail.com")
    assert result == "gmail"
```

### 2. GREEN - Make It Pass
```python
def detect_provider(email: str) -> str:
    if "@gmail.com" in email:
        return "gmail"
    return "unknown"
```

### 3. REFACTOR - Improve Code
```python
def detect_provider(email: str) -> str:
    domain = email.split("@")[1]
    provider_map = {
        "gmail.com": "gmail",
        "outlook.com": "outlook"
    }
    return provider_map.get(domain, "unknown")
```

**See:** `docs/tdd-guide.md` for detailed TDD examples

---

## 🐛 Troubleshooting

### Import Errors
```bash
# Make sure package is installed in editable mode
pip install -e ".[dev]"
```

### Async Tests Failing
```bash
# Make sure pytest-asyncio is installed
pip install pytest-asyncio

# Verify pytest.ini or pyproject.toml has:
# [tool.pytest.ini_options]
# asyncio_mode = "auto"
```

### Coverage Not Updating
```bash
# Clean coverage data
rm .coverage
pytest --cov=src/mailreactor --cov-report=term
```

### Slow Tests
```bash
# Run only fast tests
pytest -m "not e2e"

# Skip slow markers
pytest -m "not soak"
```

---

## 📚 Reference

- **TDD Guide:** `/docs/tdd-guide.md`
- **Test Design System:** `/docs/test-design-system.md`
- **Development Practices:** `/docs/development-practices.md`
- **Test Templates:** `/tests/templates/`

---

## 🐳 Greenmail Mock Server (E2E Tests)

### What is Greenmail?

Greenmail is a mock email server for testing that supports IMAP, SMTP, and POP3. It runs in Docker and provides a real email server environment without needing actual email accounts.

**Features:**
- ✅ Supports IMAP + SMTP + POP3
- ✅ Auto-creates accounts on first login
- ✅ Web API for test management (port 8080)
- ✅ No configuration needed
- ✅ Isolated test environment

### Starting Greenmail

**Start server:**
```bash
cd tests
docker compose -f docker-compose.test.yml up -d
```

**Check status:**
```bash
docker ps | grep greenmail
# Should show: mailreactor-greenmail running on ports 3143, 3025, etc.
```

**View logs:**
```bash
docker logs mailreactor-greenmail
```

**Stop server:**
```bash
cd tests
docker compose -f docker-compose.test.yml down -v
```

### Test Accounts

Greenmail auto-creates accounts on first login. Pre-configured accounts:

| Email | Password | Use Case |
|-------|----------|----------|
| `test@localhost` | `test` | Default test account |
| `admin@localhost` | `admin123` | Admin test account |
| Any other email | Any password | Auto-created on login |

### Connection Details

| Service | Host | Port | SSL | Notes |
|---------|------|------|-----|-------|
| IMAP | localhost | 3143 | No | Plaintext IMAP |
| IMAPS | localhost | 3993 | Yes | SSL IMAP |
| SMTP | localhost | 3025 | No | Plaintext SMTP |
| SMTPS | localhost | 3465 | Yes | SSL SMTP |
| Web API | localhost | 8080 | No | Test management |

### Using Greenmail in Tests

**Example E2E Test:**
```python
@pytest.mark.e2e
def test_send_and_receive_email(greenmail_imap_client, greenmail_smtp_client):
    """Send email via SMTP and retrieve via IMAP"""
    from email.message import EmailMessage
    
    # Create email
    msg = EmailMessage()
    msg['From'] = 'test@localhost'
    msg['To'] = 'test@localhost'
    msg['Subject'] = 'Test Email'
    msg.set_content('This is a test email body')
    
    # Send via SMTP
    greenmail_smtp_client.send_message(msg)
    
    # Retrieve via IMAP
    messages = greenmail_imap_client.search(['ALL'])
    assert len(messages) > 0
    
    # Fetch message
    msg_data = greenmail_imap_client.fetch(messages[-1], ['RFC822'])
    assert b'Test Email' in msg_data[messages[-1]][b'RFC822']
```

**Available Fixtures:**
- `greenmail_host` - Connection details dict
- `greenmail_test_account` - Test account credentials
- `greenmail_imap_client` - Connected IMAP client
- `greenmail_smtp_client` - Connected SMTP client

### Greenmail Web API

**Check server status:**
```bash
curl http://localhost:8080/api/service/status
```

**List messages:**
```bash
curl http://localhost:8080/api/messages
```

**Delete all messages:**
```bash
curl -X DELETE http://localhost:8080/api/messages
```

### Troubleshooting

**Issue: Container not starting**
```bash
# Check Docker is running
docker ps

# View container logs
docker logs mailreactor-greenmail

# Restart container
docker compose -f tests/docker-compose.test.yml restart
```

**Issue: Connection refused**
```bash
# Wait for healthcheck to pass (can take 10-15 seconds)
docker compose -f tests/docker-compose.test.yml ps

# Check port bindings
docker port mailreactor-greenmail
```

**Issue: Tests fail with "IMAPClient not installed"**
```bash
# Will be fixed when IMAPClient added in Epic 2
# For now, tests are skipped automatically
```

---

## 🔮 Future Enhancements

### Coming in Phase 2:
- **Real Provider Tests** - Gmail/Outlook test accounts
- **Soak Tests** - 4-hour stability validation
- **Load Tests** - Locust-based throughput testing
- **Contract Tests** - OpenAPI spec validation

---

**Generated:** 2025-11-27 (Sprint 0 - Task #4)  
**Maintained by:** TEA (Test Architect)  
**Test Framework:** pytest 7.0+ with pytest-asyncio
