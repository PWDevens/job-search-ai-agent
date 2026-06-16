# TESTING & DEBUGGING GUIDE

**Purpose:** Local testing, debugging issues, and validation procedures  
**Target Audience:** Developers, QA, DevOps  
**Last Updated:** 2026-06-16

---

## Quick Start: Local Testing

### Prerequisites
```bash
# Check Docker
docker --version      # Must be installed
docker-compose --version

# Install Python dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env if needed (SMTP credentials optional)
```

### Start Services (2-5 minutes)
```bash
# Terminal 1: Start Docker services
docker-compose up -d

# Check services are healthy
docker-compose ps
# Expected: all 3 services "healthy" or "running"

# Terminal 2: Check logs
docker-compose logs -f
# Expected: "Running on http://0.0.0.0:5000"
```

### Verify Health
```bash
# ChromaDB health
curl http://localhost:8000/api/v1/heartbeat
# Expected: {"created_at":...}

# Ollama health  
curl http://localhost:11434/api/version
# Expected: {"version":"..."}

# Flask health
curl http://localhost:5000/health
# Expected: {"status":"ok","service":"job-search-ai","chroma_db":"healthy"}
```

### First Run
```bash
# 1. Open browser
open http://localhost:5000

# 2. Upload demo data
- Use data/demo/demo_resume.txt
- Use data/demo/sample_jobs.csv

# 3. Run a search
- Role: "Data Engineer with Python"
- Geo: "Remote"
- Check "Use my resume" checkbox
- Click Search

# 4. Expected results
- 25 jobs ranked by match score
- 10 resume recommendations
- 5 blind spots with suggestions
```

---

## Debugging Common Issues

### Issue: "ERROR: ConnectionRefusedError: [Errno 111] Connection refused"

**Problem:** ChromaDB or Ollama not running

**Solution:**
```bash
# Check which services failed
docker-compose logs chromadb
docker-compose logs ollama

# If chromadb logs show errors:
docker-compose down
docker volume rm chromadb chroma_data
docker-compose up -d chromadb
# Wait 10 seconds for ChromaDB to start
docker-compose logs chromadb

# If ollama failed to start:
# May need to wait longer (it downloads 2-4 GB models)
docker-compose logs ollama
# Look for "listening on" message
```

### Issue: "TimeoutError: Request timed out after 10 seconds"

**Problem:** Service is running but slow or overloaded

**Solution:**
```bash
# Check service resource usage
docker stats jobsearch_app jobsearch_chroma jobsearch_ollama

# If high CPU/memory:
# 1. Restart services
docker-compose restart

# 2. Reduce concurrent requests (not simultaneous searches)
# 3. Increase timeout in app/config.py:
# CHROMA_TIMEOUT = 20  # increase from 10

# 4. Check logs for actual errors
docker-compose logs app --tail=50
```

### Issue: "PDF extraction failed: No text extracted"

**Problem:** PDF is scanned/image-based or corrupted

**Solution:**
```bash
# Symptoms: Resume uploaded but no text extracted

# Check logs
docker-compose logs app | grep -i "pdf\|pdfplumber"
# Should show: "pdfplumber failed" → "PyPDF2 fallback" → if still empty, "scanned PDF"

# Workaround:
# 1. Convert PDF to searchable format (Adobe Acrobat Pro)
# 2. Or use TXT/DOCX instead
# 3. Or upload plain text version in addition to PDF

# Test PDF extraction locally:
python << 'EOF'
from app.pipeline.ingest import read_resume
from pathlib import Path
text = read_resume(Path("your_resume.pdf"))
print(f"Extracted {len(text)} characters")
print(text[:500])  # show first 500 chars
EOF
```

### Issue: Agent outputs are falling back (not validated)

**Problem:** Agent validation failed, using fallback results

**Solution:**
```bash
# Check logs for validation failures
docker-compose logs app | grep -i "validation\|fallback"

# Common causes:
# 1. Agent output not numbered list format
#    Fix: Agent prompts explicitly require "1. Item\n2. Item"
#
# 2. Agent output references non-existent jobs
#    Fix: Agent RAG not properly grounded
#    Check: logs show which jobs are in context
#
# 3. Resume content is too short
#    Workaround: Provide longer resume with more details

# Debug agent output:
docker-compose exec app python << 'EOF'
from app.agents.crew import run_search_crew, SearchRequest
req = SearchRequest(
    role_description="Data Engineer",
    geo_preference="Remote",
    resume_text=None,
    extra_context=None
)
result = run_search_crew(req)
print("Validation status:", result.agent_validation)
print("Raw output (resume):", result.raw_agent_output.get("resume_recs", "")[:200])
EOF
```

### Issue: File upload fails with "File too large"

**Problem:** Upload exceeds 16MB limit

**Solution:**
```bash
# Check file size
ls -lh your_file.pdf
# If > 16MB, compress or split

# Limit is in app/validation.py:
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16 MB

# To change (not recommended):
# app/validation.py line 19
# app/routes.py line 120
```

### Issue: Rate limiting - "Too many searches"

**Problem:** Made >10 searches in 60 seconds

**Solution:**
```bash
# This is by design - limits abuse
# Current setting: 10 searches/minute per session

# To test/change:
# app/validation.py: MAX_SEARCHES_PER_MINUTE = 10
# app/routes.py: _check_rate_limit(..., max_per_minute=10)

# The limit is per session (per user), not global
# Each browser/session gets its own quota
```

---

## Test Scenarios

### Scenario 1: Happy Path (everything works)
```
1. Open http://localhost:5000
2. Upload data/demo/demo_resume.txt
3. Upload data/demo/demo_jobs.csv
4. Fill form:
   - Role: "Data Engineer with Python and SQL"
   - Geo: "Remote"
   - Extra: "Cloud platform experience preferred"
5. Click Search
6. Expected: ~25 jobs, ~10 recommendations, ~5 blind spots
   All should show [✓ Verified] badges
```

### Scenario 2: Resume with Blind Spots
```
1. Upload minimal resume (just skills, no descriptions)
2. Search for senior role
3. Expected: Many blind spots (missing soft skills, leadership)
4. Recommendations should suggest ways to demonstrate leadership
```

### Scenario 3: Geolocation Filtering
```
Test cases:
1. Geo: "NYC" → Should match "New York, NY", "New York, USA"
2. Geo: "San Francisco" → Should match "SF, CA", "SFO"
3. Geo: "Remote" → Should match "fully remote", "work from home"
4. Geo: "Los Angeles, CA" → Should NOT match "San Francisco"
```

### Scenario 4: Large File Processing
```
1. Create large jobs file (5000+ rows)
2. Upload and search
3. Expected: Takes <30s, handles gracefully
4. Check performance in logs
```

### Scenario 5: Error Recovery
```
1. Start without uploading jobs → Search fails gracefully
2. Upload invalid CSV (missing required columns)
   → Should show helpful error message
3. Upload valid CSV with special characters
   → Should handle encoding properly
```

---

## Performance Testing

### Baseline Expectations
| Operation | Target | Acceptable |
|-----------|--------|------------|
| App startup | <5s | <10s |
| Resume ingest (5KB) | <1s | <3s |
| Job ingest (1K rows) | <5s | <15s |
| Single search | <10s | <20s |
| Skill extraction (500 jobs) | <500ms | <1s |

### Load Testing
```bash
# Simulate 5 concurrent searches
for i in {1..5}; do
  curl -X POST http://localhost:5000/search \
    -F "role_description=Data Engineer" \
    -F "geo_preference=Remote" &
done
wait

# Expected: All complete without errors
# Check logs for performance metrics
```

---

## Debugging Checklist

When something goes wrong:

- [ ] Check Docker services are running: `docker-compose ps`
- [ ] Check service health: `curl http://localhost:5000/health`
- [ ] Check logs for errors: `docker-compose logs --tail=100`
- [ ] Check specific service: `docker-compose logs app` / `chromadb` / `ollama`
- [ ] Verify configuration: `cat .env | grep CHROMA`
- [ ] Check file permissions: `ls -la data/uploads/`
- [ ] Verify disk space: `df -h` (need >5GB)
- [ ] Check memory: `docker stats` (need 4-8GB)
- [ ] Restart services: `docker-compose restart`
- [ ] Full rebuild (nuclear option): `docker-compose down && docker volume prune && docker-compose up -d`

---

## Log Analysis

### Key Log Patterns

**Everything working:**
```
[2026-06-16 12:34:56] INFO - Connecting to ChromaDB at chromadb:8000
[2026-06-16 12:34:57] INFO - ✓ All agent outputs passed validation
[2026-06-16 12:35:03] INFO - Ingested 25 jobs
[2026-06-16 12:35:04] INFO - Search run logged to audit database
```

**Issues to watch for:**
```
WARNING - Resume chunk query failed (blind-spot analysis will skip resume)
WARNING - Agent validation failed for: resume_coach, career_strategist
ERROR - Failed to read resume: File not found
ERROR - ChromaDB timeout (check connection and retry)
ERROR - Email send failed (non-critical, search still works)
```

### Extracting Metrics from Logs
```bash
# Find all searches today
docker-compose logs app | grep "Search run logged" | wc -l

# Find all failures
docker-compose logs app | grep "ERROR\|CRITICAL" | wc -l

# Find average search time
docker-compose logs app | grep "seconds" | awk '{print $NF}' | awk '{sum+=$1} END {print sum/NR}'

# Check validation pass rate
docker-compose logs app | grep -c "passed validation"
docker-compose logs app | grep -c "validation failed"
```

---

## Local Development

### Running Without Docker

For development without full Docker stack:

```bash
# 1. Install ChromaDB locally
pip install chromadb

# 2. Start ChromaDB server (separate terminal)
chroma run --path ./chroma_data --port 8000

# 3. Update .env
CHROMA_HOST=localhost
OLLAMA_BASE_URL=http://localhost:11434

# 4. Start Ollama separately
ollama serve

# 5. Pull model
ollama pull phi4-mini

# 6. Run Flask app
FLASK_DEBUG=true python run.py
```

---

## Testing Checklist

Before deployment, verify:

### Core Functionality
- [ ] Resume upload works (TXT, PDF, DOCX)
- [ ] Jobs file upload works (CSV, XLSX)
- [ ] Search returns results (25 jobs)
- [ ] Resume recommendations appear (10 items)
- [ ] Blind spots identified (5 items)
- [ ] Download pipeline XLSX works
- [ ] Download merged file works (if jobs uploaded)

### Security
- [ ] Input validation works (try SQL injection: `'; DROP TABLE`)
- [ ] Rate limiting works (make 15 rapid searches)
- [ ] File size limit works (try 20MB file)
- [ ] Session isolation works (two browsers don't share data)
- [ ] SECRET_KEY is not default

### Reliability
- [ ] Service health check returns 200
- [ ] ChromaDB connection has timeout
- [ ] Error messages are user-friendly (no stack traces)
- [ ] Logs are created and rotating
- [ ] Audit database records searches

### Performance
- [ ] Search completes in <15 seconds
- [ ] Skill extraction is fast (<1s)
- [ ] Concurrent searches work (2-3 parallel)
- [ ] Memory usage stays stable (no leaks)

---

## Getting Help

### If issues persist:

1. **Check logs first:**
   ```bash
   docker-compose logs --since 10m
   ```

2. **Check configuration:**
   ```bash
   docker-compose config | head -50
   ```

3. **Restart everything:**
   ```bash
   docker-compose down -v
   docker-compose up -d
   ```

4. **Check GitHub Issues:**
   - Look for similar problems
   - Add issue if not found

5. **Enable debug mode (temporary):**
   ```bash
   # In .env:
   FLASK_DEBUG=true
   LLM_BACKEND=mock  # Use mock LLM for faster testing
   ```

---

## Performance Profiling

```python
# Add to run.py for timing analysis:
import time
from functools import wraps

def timeit(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        print(f"{func.__name__} took {duration:.2f}s")
        return result
    return wrapper

# Apply to slow operations:
@timeit
def run_search_crew(request):
    ...
```

---

**Generated:** 2026-06-16  
**Purpose:** Help developers test and debug the application  
**Maintained by:** Development Team
