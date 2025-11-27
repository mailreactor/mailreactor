# CI/CD Pipeline Guide

**Project:** Mail Reactor  
**Date:** 2025-11-27 (Sprint 0 - Task #7)  
**CI Platform:** GitHub Actions

---

## 📋 Overview

Mail Reactor uses GitHub Actions for continuous integration and continuous deployment. The CI pipeline runs on every push and pull request to ensure code quality, test coverage, and security.

**Pipeline Goals:**
- ✅ Automated testing (unit, integration, E2E)
- ✅ Code quality enforcement (linting, formatting, type checking)
- ✅ Security scanning (secrets, vulnerabilities)
- ✅ Performance benchmarking
- ✅ Coverage reporting (80% minimum)

---

## 🔄 CI Workflows

### Workflow 1: Main CI Pipeline (`.github/workflows/ci.yml`)

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests to `main`

**Matrix Testing:**
- Python versions: 3.10, 3.11, 3.12
- Operating systems: ubuntu-latest

**Pipeline Steps:**

#### 1. Setup
```yaml
- Checkout code
- Set up Python (3.10, 3.11, 3.12)
- Install uv package manager
- Create virtual environment
- Install dependencies (dev + production)
```

#### 2. Code Quality Checks
```bash
# Linting (ruff)
uv run ruff check .

# Formatting (ruff)
uv run ruff format --check .

# Type checking (mypy)
uv run mypy src/mailreactor --ignore-missing-imports
```

**Status:** Type checking is currently `continue-on-error: true` (won't fail CI). Will be strict after Epic 1 implementation.

#### 3. Testing
```bash
# Run all tests with coverage
uv run pytest tests/ --cov=src/mailreactor --cov-report=xml --cov-report=term-missing

# Check coverage threshold (80%)
uv run pytest --cov=src/mailreactor --cov-fail-under=80 --cov-report=term
```

**Status:** Coverage threshold is currently `continue-on-error: true` (won't fail CI). Will be strict after Epic 1 has significant code.

#### 4. Security Checks
```bash
# Detect secrets
uv run detect-secrets scan --baseline .secrets.baseline

# Dependency vulnerabilities (safety removed - requires auth)
# Future: Use pip-audit as alternative
```

#### 5. Coverage Upload
- Uploads coverage report to Codecov (Python 3.10 only)
- Requires `CODECOV_TOKEN` secret in GitHub repository settings

#### 6. Artifact Archival
- Uploads test results, coverage reports as GitHub artifacts
- Accessible from Actions tab for debugging

---

### Workflow 2: Performance Benchmarks (`.github/workflows/benchmarks.yml`)

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests to `main`
- Manual dispatch (workflow_dispatch)

**Pipeline Steps:**

#### 1. Setup
```yaml
- Checkout code
- Set up Python 3.10
- Install uv + dependencies
```

#### 2. Run Benchmarks
```bash
# Run performance tests only
uv run pytest tests/performance/ --benchmark-only --benchmark-json=benchmark-results.json
```

#### 3. Store Results
- Uploads `benchmark-results.json` as artifact
- Results include: min, max, mean, median, stddev

#### 4. Comment on PR
- Automatically posts benchmark results as PR comment
- Shows performance comparison table

**Future:** Add automated threshold checking (fail if startup >3.5s)

---

## 🚀 Local Development Workflow

### Before Committing

**Pre-commit hooks run automatically:**
```bash
# Configured in .pre-commit-config.yaml
- ruff linting and formatting
- mypy type checking
- detect-secrets scanning
- pytest with 80% coverage requirement
```

**If hooks fail:**
1. Fix the issues reported
2. Re-run: `git commit` (hooks run again)

**Manual pre-commit run:**
```bash
pre-commit run --all-files
```

### Running Tests Locally

```bash
# All tests
uv run pytest

# Specific test level
uv run pytest tests/unit/
uv run pytest tests/integration/
uv run pytest tests/e2e/

# With coverage
uv run pytest --cov=src/mailreactor --cov-report=html
open htmlcov/index.html

# Performance benchmarks
uv run pytest tests/performance/ --benchmark-only
```

### Running Code Quality Checks

```bash
# Linting
uv run ruff check .

# Auto-fix linting issues
uv run ruff check . --fix

# Formatting
uv run ruff format .

# Type checking
uv run mypy src/mailreactor --ignore-missing-imports
```

### Running Security Checks

```bash
# Detect secrets
uv run detect-secrets scan

# Update secrets baseline (if false positive)
uv run detect-secrets scan --baseline .secrets.baseline

# Dependency vulnerabilities (safety removed - requires auth)
# Future: uv run pip-audit
```

---

## 🔀 Pull Request Workflow

### 1. Create Feature Branch
```bash
git checkout -b feature/story-1.1-project-structure
```

### 2. Implement with TDD
- Write failing test (RED)
- Implement code (GREEN)
- Refactor (REFACTOR)
- Commit regularly

### 3. Pre-commit Hooks
- Run automatically on `git commit`
- Must pass before commit is allowed

### 4. Push to GitHub
```bash
git push origin feature/story-1.1-project-structure
```

### 5. Create Pull Request
- CI runs automatically
- Benchmarks run and post results
- All checks must pass:
  - ✅ Linting
  - ✅ Formatting
  - ✅ Type checking (warning only for now)
  - ✅ Tests pass
  - ✅ Coverage ≥80% (warning only for now)
  - ✅ No secrets detected

### 6. Code Review
- Request review from team
- Address feedback
- Re-push triggers CI again

### 7. Merge
- Squash and merge to `main`
- Delete feature branch

---

## 📊 Branch Protection Rules

**Recommended settings for `main` branch:**

### Required Status Checks
- ✅ `test (3.10)`
- ✅ `test (3.11)`
- ✅ `test (3.12)`
- ✅ `benchmark`

### Additional Protection
- ✅ Require pull request reviews (1 approval minimum)
- ✅ Require branches to be up to date before merging
- ✅ Require conversation resolution before merging
- ✅ Do not allow bypassing (include administrators)

**Setup:**
1. Go to: Repository Settings → Branches
2. Click "Add rule" for `main` branch
3. Enable checkboxes above
4. Save changes

---

## 🐛 Troubleshooting CI Failures

### Linting Failures
```bash
# Local fix
uv run ruff check . --fix
uv run ruff format .

# Re-commit
git add .
git commit --amend --no-edit
git push --force-with-lease
```

### Type Checking Failures
```bash
# Run locally
uv run mypy src/mailreactor --ignore-missing-imports

# Common fixes:
# - Add type hints to function signatures
# - Import types from typing module
# - Use # type: ignore for unavoidable issues
```

### Test Failures
```bash
# Run locally with verbose output
uv run pytest -vv

# Run specific failing test
uv run pytest tests/unit/test_specific.py::test_name -vv

# Common fixes:
# - Check test assumptions
# - Update mock return values
# - Check async/await patterns
```

### Coverage Failures
```bash
# Generate coverage report
uv run pytest --cov=src/mailreactor --cov-report=html
open htmlcov/index.html

# Identify uncovered lines
# Add tests for uncovered code
```

### Secret Detection Failures
```bash
# Scan locally
uv run detect-secrets scan

# If false positive, update baseline
uv run detect-secrets scan --baseline .secrets.baseline

# Commit baseline update
git add .secrets.baseline
git commit -m "Update secrets baseline"
```

### Dependency Vulnerabilities
```bash
# Safety removed (requires auth)
# Future alternative: pip-audit
# uv pip install pip-audit
# uv run pip-audit

# If vulnerabilities found, upgrade affected packages
uv pip install --upgrade <package>

# Re-run tests
uv run pytest
```

---

## 📈 Performance Monitoring

### Benchmark Tracking

**In Pull Requests:**
- Benchmark results posted automatically as comment
- Compare against baseline (main branch)
- Review for performance regressions

**Manual Benchmark Run:**
```bash
# Local
uv run pytest tests/performance/ --benchmark-only

# CI (manual trigger)
# Go to: Actions → Performance Benchmarks → Run workflow
```

### Performance Thresholds

**Current Thresholds (validated after baseline established):**
- Startup time: <3.0s median (NFR-P1)
- Health endpoint: <50ms p95 (NFR-P2)
- API endpoints: <200ms p95 (NFR-P2)
- Memory footprint: <100MB (NFR-P4)

**Future:** Automated threshold checking will fail CI if thresholds breached.

---

## 🔐 Secrets Management

### Required GitHub Secrets

**Setup:** Repository Settings → Secrets and variables → Actions

| Secret Name | Purpose | When Needed |
|-------------|---------|-------------|
| `CODECOV_TOKEN` | Upload coverage to Codecov | Now (optional) |
| `PYPI_TOKEN` | Publish to PyPI | Phase 2 (deployment) |

**Note:** GitHub automatically provides `GITHUB_TOKEN` for Actions API access.

---

## 🚢 Deployment Pipeline (Future - Phase 2)

**Not yet implemented.** Future workflows will include:

### Workflow 3: Release Pipeline
- Tag-based releases (v0.1.0, v0.2.0, etc.)
- Build Python wheel and sdist
- Publish to PyPI
- Create GitHub Release with changelog

### Workflow 4: Docker Build
- Build Docker image
- Push to GitHub Container Registry
- Tag: `ghcr.io/user/mailreactor:latest`

---

## 📚 Reference

**GitHub Actions Documentation:**
- https://docs.github.com/en/actions

**Tools Documentation:**
- pytest: https://docs.pytest.org
- ruff: https://docs.astral.sh/ruff/
- mypy: https://mypy.readthedocs.io
- detect-secrets: https://github.com/Yelp/detect-secrets
- pytest-benchmark: https://pytest-benchmark.readthedocs.io

**Related Docs:**
- `tests/README.md` - Testing philosophy and guides
- `docs/tdd-guide.md` - Test-driven development workflow
- `docs/environment-setup-guide.md` - Local setup instructions

---

## ✅ Sprint 0 Task #7 Complete

**What Was Created:**
- ✅ `.github/workflows/ci.yml` - Main CI pipeline
- ✅ `.github/workflows/benchmarks.yml` - Performance benchmarks
- ✅ `docs/ci-cd-guide.md` - This documentation

**What's Next:**
- Set up branch protection rules (manual GitHub UI step)
- Configure Codecov token (optional)
- Establish performance baselines after Epic 1

---

**Generated:** 2025-11-27 (Sprint 0 - Task #7)  
**Maintained by:** TEA (Test Architect)  
**CI Platform:** GitHub Actions
