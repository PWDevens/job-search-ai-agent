# Deployment Checklist

**Status:** Ready for PHASE 1 + PHASE 2 Deployment  
**Last Updated:** 2026-06-16  
**Deployment Target:** Staging → Production

---

## Pre-Deployment: Environment & Dependencies

### System Requirements
- [ ] Python 3.9+
- [ ] Docker & Docker Compose (for ChromaDB, Ollama)
- [ ] 4GB RAM minimum (8GB recommended)
- [ ] 20GB disk space (for Ollama models)
- [ ] Linux/macOS/Windows with WSL2

### Dependencies
- [ ] `pip install -r requirements.txt` completed without errors
- [ ] Virtual environment activated
- [ ] All imports work: `python -c "from app import create_app"`
- [ ] Flask, ChromaDB, CrewAI, Ollama packages available

### Environment Configuration
- [ ] `.env` file exists with all required variables:
  ```
  CHROMA_HOST=chromadb
  CHROMA_PORT=8000
  CHROMA_TIMEOUT=10
  OLLAMA_BASE_URL=http://ollama:11434
  OLLAMA_MODEL=llama3
  FLASK_HOST=0.0.0.0
  FLASK_PORT=5000
  FLASK_DEBUG=false
  SECRET_KEY=<random-value-NOT-change-me-in-production>
  SMTP_HOST=smtp.gmail.com
  SMTP_PORT=587
  SMTP_USER=<your-email>
  SMTP_PASS=<app-password>
  EMAIL_TO=<recipient-email>
  ```
- [ ] `SECRET_KEY` is cryptographically random (not default)
- [ ] SMTP credentials are valid (test with separate script)
- [ ] No sensitive data in git (check `.gitignore`)

---

## Unit & Integration Testing

### Test Suite Execution
```bash
# Install test dependencies
pip install pytest pytest-cov

# Run all tests
pytest tests/ -v --cov=app --cov-report=html

# Target: 75%+ code coverage
# Expected: 104+ tests, all passing
```

**Verification:**
- [ ] All tests pass (0 failures)
- [ ] Code coverage ≥75% (report in `htmlcov/index.html`)
- [ ] No warnings or deprecations
- [ ] Test suite completes in <5 minutes

### Critical Test Coverage
- [ ] `test_ingest.py`: Job/resume ingestion (27 tests)
- [ ] `test_matcher.py`: Semantic search & blind spots (18 tests)
- [ ] `test_chroma_client.py`: Database operations (12 tests)
- [ ] `test_email.py`: Email sending (20 tests)
- [ ] `test_crew.py`: Agent orchestration (25 tests)
- [ ] `test_audit.py`: Audit logging (16 tests)
- [ ] `test_pipeline_integration.py`: End-to-end workflows (12 tests)

---

## Application Startup & Health Checks

### Docker Services
```bash
docker-compose up -d
```

**Verification:**
- [ ] ChromaDB running: `curl http://localhost:8000/api/v1/heartbeat`
- [ ] Ollama running: `curl http://localhost:11434/api/tags`
- [ ] Flask app running: `curl http://localhost:5000/`

### Application Health Check
```bash
python run.py
```

**Expected output:**
```
================================================================================
Job-Search AI Agent starting
Logs: console (INFO), file (logs/app.log), errors (logs/errors.log)
================================================================================
 * Running on http://0.0.0.0:5000
```

**Verification:**
- [ ] App starts without errors
- [ ] No import errors or missing modules
- [ ] `/health` endpoint returns 200 OK with ChromaDB status
- [ ] Logs directory created with `app.log` and `errors.log`

---

## Workflow Testing: Happy Path

### 1. Resume Upload & Ingestion
```
1. Navigate to http://localhost:5000
2. Upload sample resume (data/demo/demo_resume.txt)
3. Check: Resume ingested message appears
4. Check: logs/app.log shows ingestion success
5. Check: data/audit.db created with entry
```

**Verification:**
- [ ] Resume file accepted (PDF/TXT/DOCX)
- [ ] No upload errors in UI or logs
- [ ] Resume deleted from `data/uploads/` after ingestion
- [ ] Resume chunks stored in ChromaDB

### 2. Jobs File Upload
```
1. Upload sample jobs file (data/demo/sample_jobs.csv or XLSX)
2. Check: Jobs ingested message appears
3. Check: logs/app.log shows job count
```

**Verification:**
- [ ] Jobs file accepted (CSV/XLSX)
- [ ] Correct number of jobs ingested
- [ ] Duplicates handled (re-upload doesn't duplicate)
- [ ] Geo filter works (test with location filter)

### 3. Search & Results
```
1. Enter role description: "Data Engineer with Python and SQL"
2. Set geo preference: "Remote"
3. Check resume uploaded from step 1
4. Click "Search"
```

**Expected output:**
- [ ] Top 25 jobs displayed with scores
- [ ] Resume recommendations shown
- [ ] Blind spots identified
- [ ] All fields populated (title, company, location, salary, score)
- [ ] Results match role description relevance

**Verification:**
- [ ] Search completes in <10 seconds
- [ ] Jobs ranked by relevance (scores decrease)
- [ ] Agent validation status logged
- [ ] Audit entry created in `data/audit.db`
- [ ] No errors in logs/errors.log

### 4. File Merge & Download
```
1. Download merged results
2. Check: New jobs appended to original file
3. Check: No duplicate jobs
```

**Verification:**
- [ ] Download button appears after search
- [ ] Downloaded file is valid CSV/XLSX
- [ ] New jobs are unique (not already in file)
- [ ] Original columns preserved

---

## Logging & Monitoring Verification

### File Logging Setup
- [ ] `logs/` directory exists
- [ ] `logs/app.log` file created with rotating handler
- [ ] `logs/errors.log` contains ERROR-level entries only
- [ ] Logs rotate at 10MB without issues
- [ ] Backup logs (.log.1, .log.2, etc.) created
- [ ] Logs are readable and structured

### Audit Database
```bash
sqlite3 data/audit.db "SELECT COUNT(*) FROM search_runs;"
```

- [ ] `data/audit.db` exists
- [ ] `search_runs` table created
- [ ] At least 1 row from test searches
- [ ] Can query by run_id: `SELECT * FROM search_runs WHERE id = 1;`
- [ ] Resume hash is privacy-preserving (not actual text)

### Monitoring & Alerts
- [ ] Error log monitored for ERROR entries
- [ ] Application logs monitored for CRITICAL entries
- [ ] Audit log reviewed for failed validations
- [ ] Health check endpoint monitored (`/health`)

---

## PHASE 1 & 2 Specific Validations

### PHASE 1: Critical Bug Fixes
- [ ] **Issue 1.1**: Resume upload doesn't crash (import error fixed)
- [ ] **Issue 1.2**: ChromaDB timeout works (10s, then clear error)
  - Test: Disconnect ChromaDB, run search, verify timeout message
- [ ] **Issue 1.3**: Upload files cleaned up (not accumulated)
  - Test: Upload file, verify deleted after ingest
  - Check: `data/uploads/` remains empty after searches
- [ ] **Issue 1.4**: Blind-spot failures logged (not silent)
  - Check: logs/app.log shows "Resume chunk query failed" warning

### PHASE 2: Robustness & Performance
- [ ] **Issue 2.1**: Test suite passes (75%+ coverage)
  - Run: `pytest tests/ --cov=app`
- [ ] **Issue 2.2**: Agent validation working
  - Check: logs show "✓ All agent outputs passed validation" or "✗ Agent validation failed"
  - Verify: Fallback results when validation fails
- [ ] **Issue 2.3**: Skill extraction is fast
  - Time: 500+ jobs → <500ms (was 2-5s)
  - Verify: `_extract_skill_terms()` uses compiled regex
- [ ] **Issue 2.4**: Resume chunking respects sections
  - Check: Resume chunks break on "Skills:", "Experience:" boundaries
  - Verify: No chunks break mid-sentence
- [ ] **Issue 2.5**: Audit logging works
  - Check: Every search logged to `data/audit.db`
  - Verify: `get_audit_stats()` returns pass rates
- [ ] **Issue 2.6**: File logging active
  - Check: `logs/app.log` and `logs/errors.log` created
  - Verify: Logs rotate without errors

---

## Performance Baseline

### Expected Performance Metrics
| Operation | Target | Acceptable |
|-----------|--------|------------|
| App startup | <5s | <10s |
| Resume ingest (500 words) | <1s | <3s |
| Job ingest (1000 rows) | <5s | <15s |
| Semantic search (500 jobs) | <2s | <5s |
| Skill extraction (500 jobs) | <500ms | <1s |
| Full pipeline (search → results) | <10s | <20s |

### Load Testing (Optional)
```bash
# Simulate concurrent searches
for i in {1..5}; do
  curl -X POST http://localhost:5000/search \
    -F "role_description=Data Engineer" &
done
wait
```

- [ ] App handles 5 concurrent searches without crashes
- [ ] No memory leaks (memory stable after searches)

---

## Security Checklist

### Secrets & Credentials
- [ ] `.env` file is in `.gitignore` (never committed)
- [ ] `SECRET_KEY` is random, not default
- [ ] SMTP password stored in `.env`, not in code
- [ ] No API keys in logs or error messages
- [ ] Resume content never logged (only hash in audit.db)

### Input Validation
- [ ] File uploads limited to allowed types
- [ ] File size limits enforced
- [ ] SQL injection protection (using parameterized queries)
- [ ] XSS protection in templates

### Error Handling
- [ ] Errors don't expose system paths
- [ ] Errors don't expose database structure
- [ ] Stack traces not shown to users
- [ ] All exceptions logged (not silenced)

---

## Deployment Steps

### Staging Deployment
```bash
# 1. Set up environment
export FLASK_ENV=staging
cp .env.example .env  # Edit with staging values

# 2. Start services
docker-compose up -d

# 3. Run tests
pytest tests/ -v --cov=app

# 4. Start application
python run.py

# 5. Run smoke tests (see above)
# 6. Monitor logs/errors.log for issues
# 7. Load test with concurrent searches
```

### Production Deployment
```bash
# 1. Repeat staging steps with production .env
export FLASK_ENV=production
# Set FLASK_DEBUG=false
# Set SECRET_KEY to random value

# 2. Enable monitoring/alerting
# - Point logs to centralized system (ELK, Datadog, etc.)
# - Set up alerts for ERROR and CRITICAL
# - Monitor /health endpoint

# 3. Set up backup
# - Daily backup of data/audit.db
# - Weekly backup of data/job_pipeline.xlsx

# 4. Deploy with process supervisor (systemd, supervisor, PM2)
# Ensure app restarts on crash

# 5. Set up SSL/TLS (if public-facing)
# - Use nginx/Apache reverse proxy
# - Obtain SSL certificate (Let's Encrypt)
```

---

## Rollback Plan

If critical issues found during deployment:

1. **Immediate**: Stop application with `docker-compose down`
2. **Restore**: Use git to checkout previous stable commit
3. **Verify**: Run full test suite before restarting
4. **Document**: Log what failed and why in incident report

```bash
# Rollback to previous working commit
git log --oneline | head -5  # Find last stable commit
git reset --hard <commit-hash>
docker-compose up -d
pytest tests/ -v
```

---

## Post-Deployment Monitoring

### Daily Checks
- [ ] Application running (`curl /health`)
- [ ] No errors in `logs/errors.log` over last 24h
- [ ] Agent validation pass rate >90% (check audit.db)
- [ ] Disk usage <80% (logs rotate properly)
- [ ] Database size reasonable (<10GB for 10k searches)

### Weekly Reviews
- [ ] Audit log stats: total runs, validation pass rate, avg results per run
- [ ] Error patterns: any recurring errors?
- [ ] Performance trends: any degradation?
- [ ] User feedback: issues reported?

### Monthly Audits
- [ ] Cleanup old audit entries: `cleanup_old_audits(days=90)`
- [ ] Review agent hallucinations: any validation failures?
- [ ] Skill extraction accuracy: is validation catching false results?
- [ ] Log file rotation: backups being kept properly?

---

## Sign-Off Checklist

**Deployment Ready When:**
- [x] All tests pass (pytest)
- [x] App starts without errors
- [x] All 4 critical PHASE 1 bugs verified fixed
- [x] All 6 PHASE 2 robustness features verified
- [x] Smoke test: full workflow succeeds
- [x] Logs created and rotating properly
- [x] Audit database working
- [x] No secrets in git
- [x] Security checklist passed
- [x] Performance baseline acceptable

**Deployment blocked if:**
- ❌ Any test fails
- ❌ App doesn't start
- ❌ Resume upload crashes
- ❌ ChromaDB connection hangs
- ❌ Secrets found in code
- ❌ Performance <2x slower than acceptable

---

**Deployment Date:** ________________  
**Deployed By:** ________________  
**Status:** ☐ Staging ☐ Production  
**Notes:** ________________________________________________

---

This checklist should be run before **any** deployment attempt.
