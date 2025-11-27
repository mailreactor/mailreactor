# Greenmail Setup Instructions

**Status:** Configuration complete  
**Date:** 2025-11-27 (Sprint 0 - Task #3)

---

## 📦 What Was Created

✅ **Files Created:**
- `tests/docker-compose.test.yml` - Greenmail Docker configuration
- `tests/conftest.py` - Updated with Greenmail fixtures
- `tests/README.md` - Updated with Greenmail documentation
- `tests/e2e/test_example.py` - Updated with real Greenmail E2E tests
- `tests/GREENMAIL-SETUP.md` - This file

---

## 🚀 Starting Greenmail

### Option 1: Start in Background (Recommended)

```bash
cd mailreactor/tests
docker compose -f docker-compose.test.yml up -d
```

**Wait for health check to pass (10-15 seconds):**
```bash
docker compose -f docker-compose.test.yml ps
# Should show: mailreactor-greenmail (healthy)
```

### Option 2: Start with Logs (Debugging)

```bash
cd mailreactor/tests
docker compose -f docker-compose.test.yml up
# Press Ctrl+C to stop
```

---

## ✅ Verifying Greenmail is Running

### Check Container Status
```bash
docker ps | grep greenmail
# Expected: mailreactor-greenmail running on multiple ports
```

### Check Health
```bash
docker compose -f mailreactor/tests/docker-compose.test.yml ps
# Expected: State = running (healthy)
```

### Test IMAP Connection
```bash
# Install telnet if needed: apt-get install telnet
telnet localhost 3143
# Expected: * OK IMAP4rev1 Server GreenMail ready
# Type: A001 CAPABILITY
# Expected: * CAPABILITY IMAP4rev1 ...
# Type: A002 LOGOUT
```

### Test SMTP Connection
```bash
telnet localhost 3025
# Expected: 220 ...
# Type: QUIT
# Expected: 221 Bye
```

### Check Web API
```bash
curl http://localhost:8080/api/service/status
# Expected: JSON response with service status
```

---

## 🧪 Running E2E Tests with Greenmail

### Run All E2E Tests
```bash
cd mailreactor
uv run pytest tests/e2e/ -v -m e2e
```

### Run Specific Greenmail Test
```bash
uv run pytest tests/e2e/test_example.py::test_greenmail_imap_connection -v
```

### Expected Results (when Greenmail is running)
```
tests/e2e/test_example.py::test_greenmail_imap_connection PASSED
tests/e2e/test_example.py::test_greenmail_smtp_send PASSED
```

### If Greenmail NOT Running
```
tests/e2e/test_example.py::test_greenmail_imap_connection SKIPPED
# Reason: IMAPClient not installed (will be added in Epic 2)
```

---

## 🛑 Stopping Greenmail

### Stop Container
```bash
cd mailreactor/tests
docker compose -f docker-compose.test.yml down
```

### Stop and Remove Volumes (Clean Slate)
```bash
cd mailreactor/tests
docker compose -f docker-compose.test.yml down -v
# This deletes all emails stored in Greenmail
```

---

## 📊 Greenmail Configuration

### Ports Exposed

| Service | Port | SSL | Use Case |
|---------|------|-----|----------|
| IMAP | 3143 | No | E2E tests (plaintext) |
| IMAPS | 3993 | Yes | Future SSL tests |
| SMTP | 3025 | No | E2E tests (plaintext) |
| SMTPS | 3465 | Yes | Future SSL tests |
| POP3 | 3110 | No | Not used |
| POP3S | 3995 | Yes | Not used |
| Web API | 8080 | No | Test management |

### Pre-Configured Accounts

Configured in `docker-compose.test.yml`:
- `test@localhost` / `test`
- `admin@localhost` / `admin123`

**Note:** Greenmail auto-creates any account on first login, so you can use any email/password combo.

### Environment Variables

```yaml
GREENMAIL_OPTS: >-
  -Dgreenmail.setup.test.all              # Enable all services
  -Dgreenmail.hostname=0.0.0.0           # Bind to all interfaces
  -Dgreenmail.auth.disabled=false        # Require authentication
  -Dgreenmail.verbose                     # Enable verbose logging
  -Dgreenmail.users=test@localhost:test  # Pre-create test user
```

---

## 🐛 Troubleshooting

### Issue: Port Already in Use

```bash
# Check what's using port 3143
lsof -i :3143
# or
netstat -an | grep 3143

# Stop conflicting service or change port in docker-compose.test.yml
```

### Issue: Container Exits Immediately

```bash
# View container logs
docker logs mailreactor-greenmail

# Common causes:
# - Port conflict
# - Docker daemon not running
# - Insufficient memory
```

### Issue: Health Check Failing

```bash
# Wait longer (can take 15-20 seconds on first start)
docker compose -f mailreactor/tests/docker-compose.test.yml ps

# If still unhealthy after 30 seconds, check logs:
docker logs mailreactor-greenmail
```

### Issue: Cannot Connect from Tests

```bash
# Verify container is running
docker ps | grep greenmail

# Verify ports are accessible
telnet localhost 3143

# Check firewall (Linux)
sudo ufw status

# Check Docker network
docker network inspect mailreactor-test
```

---

## 🔄 CI/CD Integration

### GitHub Actions (Future)

Add to `.github/workflows/ci.yml`:

```yaml
jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Start Greenmail
        run: |
          cd mailreactor/tests
          docker compose -f docker-compose.test.yml up -d
          
          # Wait for health check
          timeout 30 sh -c 'until docker compose -f docker-compose.test.yml ps | grep healthy; do sleep 1; done'
      
      - name: Run E2E tests
        run: |
          cd mailreactor
          uv run pytest tests/e2e/ -v -m e2e
      
      - name: Stop Greenmail
        if: always()
        run: |
          cd mailreactor/tests
          docker compose -f docker-compose.test.yml down -v
```

---

## 📚 Greenmail Documentation

**Official Docs:** https://greenmail-mail-test.github.io/greenmail/

**GitHub:** https://github.com/greenmail-mail-test/greenmail

**Docker Hub:** https://hub.docker.com/r/greenmail/standalone

---

## ✅ Verification Checklist

Before marking Task #3 complete, verify:

- [ ] Greenmail image downloaded: `docker images | grep greenmail`
- [ ] Container starts: `docker compose -f tests/docker-compose.test.yml up -d`
- [ ] Health check passes: `docker compose -f tests/docker-compose.test.yml ps`
- [ ] IMAP accessible: `telnet localhost 3143`
- [ ] SMTP accessible: `telnet localhost 3025`
- [ ] Web API accessible: `curl http://localhost:8080/api/service/status`
- [ ] E2E tests run (or skip gracefully if IMAPClient not installed)

---

**Created:** 2025-11-27  
**Sprint:** Sprint 0 - Task #3  
**Next:** Run E2E tests when Epic 2 (IMAP client) is implemented
