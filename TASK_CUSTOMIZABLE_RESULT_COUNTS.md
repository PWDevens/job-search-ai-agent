# TASK: Customizable Result Count Sliders

**Phase:** PHASE 3 (Nice-to-have Enhancements)  
**Priority:** Medium (improves user control + flexibility)  
**Estimated Effort:** 3.5 hours  
**Category:** Frontend + Backend Parameter Passing  

---

## OBJECTIVE

Allow users to specify the number of results displayed via interactive sliders on the search form, with sensible defaults and validation.

**User Story:**  
"As a job seeker, I want to control how many job matches, resume recommendations, and blind spots I see in each search, so I can tailor results to my needs (e.g., see 20 jobs for a broad search, or 5 for a focused review)."

---

## REQUIREMENTS

### Form Controls (Frontend)

Add three sliders to `templates/index.html` (search form section):

| Field | Min | Max | Default | Step | Display |
|-------|-----|-----|---------|------|---------|
| Top Job Matches | 5 | 25 | 10 | 1 | `<input type="range" name="top_jobs" min="5" max="25" value="10" step="1" />` |
| Resume Recommendations | 3 | 10 | 5 | 1 | `<input type="range" name="top_resume_recs" min="3" max="10" value="5" step="1" />` |
| Blind Spots | 1 | 10 | 5 | 1 | `<input type="range" name="top_blind_spots" min="1" max="10" value="5" step="1" />` |

**Display Behavior:**
- Each slider shows a **live count** next to it (updates as user drags)
- Label format: `"Show [N] top job matches"` with `[N]` updating in real-time
- Use HTML5 `<input type="range">` + JavaScript `oninput` listener for live updates

**Example HTML Structure:**
```html
<div class="form-group">
  <label for="top_jobs">Top Job Matches</label>
  <div class="slider-container">
    <input type="range" id="top_jobs" name="top_jobs" 
           min="5" max="25" value="10" step="1" />
    <span id="top_jobs_display">10</span>
  </div>
</div>
```

**Example JavaScript (in `static/search.js` or `<script>` tag):**
```javascript
document.querySelectorAll('input[type="range"]').forEach(slider => {
  slider.addEventListener('input', (e) => {
    const displayId = e.target.id + '_display';
    document.getElementById(displayId).textContent = e.target.value;
  });
});
```

---

### Backend Changes

#### 1. Update `app/routes.py` `/search` endpoint (lines 68–150)

**Current code:**
```python
role_description = request.form.get('role_description', '').strip()
geo_preference = request.form.get('geo_preference', '').strip()
extra_context = request.form.get('extra_context', '').strip()
# ... no current handling of result counts
```

**New code:**
```python
role_description = request.form.get('role_description', '').strip()
geo_preference = request.form.get('geo_preference', '').strip()
extra_context = request.form.get('extra_context', '').strip()

# Extract and validate result count parameters
try:
    top_jobs = int(request.form.get('top_jobs', 10))
    top_jobs = max(5, min(25, top_jobs))  # Clamp to [5, 25]
except (ValueError, TypeError):
    top_jobs = 10

try:
    top_resume_recs = int(request.form.get('top_resume_recs', 5))
    top_resume_recs = max(3, min(10, top_resume_recs))  # Clamp to [3, 10]
except (ValueError, TypeError):
    top_resume_recs = 5

try:
    top_blind_spots = int(request.form.get('top_blind_spots', 5))
    top_blind_spots = max(1, min(10, top_blind_spots))  # Clamp to [1, 10]
except (ValueError, TypeError):
    top_blind_spots = 5
```

**Pass to CrewAI pipeline:**
```python
search_req = SearchRequest(
    role_description=role_description,
    geo_preference=geo_preference,
    extra_context=extra_context,
    top_jobs=top_jobs,                    # NEW
    top_resume_recs=top_resume_recs,      # NEW
    top_blind_spots=top_blind_spots       # NEW
)
```

#### 2. Update `app/agents/crew.py` SearchRequest dataclass

**Current code (lines 10–22):**
```python
@dataclass
class SearchRequest:
    role_description: str
    geo_preference: Optional[str] = None
    extra_context: Optional[str] = None
```

**New code:**
```python
@dataclass
class SearchRequest:
    role_description: str
    geo_preference: Optional[str] = None
    extra_context: Optional[str] = None
    top_jobs: int = 10                    # NEW: Default 10
    top_resume_recs: int = 5              # NEW: Default 5
    top_blind_spots: int = 5              # NEW: Default 5
```

#### 3. Update agent task definitions in `crew.py` (lines 100–140)

**Current code:**
```python
search_task = Task(
    description=f"""Find the top 10 jobs matching the role...""",
    expected_output="...",
    agent=job_matcher_agent
)
```

**New code:**
```python
search_task = Task(
    description=f"""Find the top {search_request.top_jobs} jobs matching the role...""",
    expected_output=f"A prioritized list of {search_request.top_jobs} jobs...",
    agent=job_matcher_agent
)

resume_task = Task(
    description=f"""Analyze the resume and provide {search_request.top_resume_recs} personalized recommendations...""",
    expected_output=f"A list of {search_request.top_resume_recs} actionable recommendations...",
    agent=resume_coach_agent
)

blind_task = Task(
    description=f"""Identify the top {search_request.top_blind_spots} skills gaps...""",
    expected_output=f"A list of {search_request.top_blind_spots} blind spots with explanation...",
    agent=career_strategist_agent
)
```

#### 4. Update matcher fallback calls in `routes.py` (lines 135–147)

**Current code:**
```python
top_jobs_list = find_top_jobs(role_description, geo_preference, resume_text, n=TOP_JOBS)
resume_recs = find_resume_recommendations(role_description, resume_text, n=TOP_RESUME_RECS)
blind_spots = find_blind_spots(role_description, resume_text, n=TOP_BLIND_SPOTS)
```

**New code:**
```python
top_jobs_list = find_top_jobs(role_description, geo_preference, resume_text, n=top_jobs)
resume_recs = find_resume_recommendations(role_description, resume_text, n=top_resume_recs)
blind_spots = find_blind_spots(role_description, resume_text, n=top_blind_spots)
```

---

### Scheduler Integration

Update `app/scheduler.py` to use sensible defaults when running automated weekly searches:

```python
def _run_pipeline():
    """Execute full CrewAI pipeline with default result counts."""
    search_req = SearchRequest(
        role_description=SCHEDULED_ROLE,
        geo_preference=SCHEDULED_GEO,
        top_jobs=15,              # More results for automated weekly search
        top_resume_recs=5,        # Standard
        top_blind_spots=5         # Standard
    )
```

---

## IMPLEMENTATION STEPS

### Step 1: Frontend (0.5 hours)
- [ ] Edit `templates/index.html`: Add three `<input type="range">` sliders to search form
- [ ] Add labels and live count display (span elements)
- [ ] Add JavaScript `oninput` listeners to update display text in real-time
- [ ] Test sliders visually (drag, verify count updates)

### Step 2: Backend Parameter Extraction (1 hour)
- [ ] Edit `app/routes.py` `/search` endpoint
- [ ] Add parameter extraction + validation with clamping
- [ ] Log extracted values for debugging
- [ ] Test with curl/Postman: POST with custom `top_jobs=20` etc.

### Step 3: Data Model Update (0.5 hours)
- [ ] Edit `app/agents/crew.py` SearchRequest dataclass
- [ ] Add three new int fields with defaults
- [ ] Update agent task descriptions to use `search_request.top_jobs` etc.

### Step 4: Matcher Fallback Update (0.5 hours)
- [ ] Edit `app/routes.py` fallback calls (lines 135–147)
- [ ] Replace hardcoded `TOP_JOBS` constants with `top_jobs` variable

### Step 5: Scheduler Update (0.5 hours)
- [ ] Edit `app/scheduler.py` `_run_pipeline()` function
- [ ] Add result count parameters to SearchRequest

### Step 6: Testing & Verification (0.5 hours)
- [ ] Test with various slider values (min, max, mid-range)
- [ ] Verify clamping works (try values outside range via curl)
- [ ] Verify default values applied when form fields missing
- [ ] Test with small values (5 jobs, 1 blind spot) and large (25 jobs, 10 blind spots)
- [ ] Verify CrewAI agent descriptions reflect user-selected counts in output

---

## VALIDATION RULES

| Parameter | Valid Range | Default | Fallback |
|-----------|------------|---------|----------|
| `top_jobs` | 5–25 | 10 | 10 (if missing or invalid) |
| `top_resume_recs` | 3–10 | 5 | 5 (if missing or invalid) |
| `top_blind_spots` | 1–10 | 5 | 5 (if missing or invalid) |

**Validation Strategy:** Clamp with `max(min_val, min(max_val, parsed_value))` to silently handle out-of-range values without error messages.

---

## TESTING STRATEGY

### Unit Tests
```python
def test_search_request_defaults():
    """Default values should be 10, 5, 5."""
    req = SearchRequest(role_description="Python Dev")
    assert req.top_jobs == 10
    assert req.top_resume_recs == 5
    assert req.top_blind_spots == 5

def test_parameter_clamping():
    """Out-of-range values should be clamped."""
    # top_jobs=100 should be clamped to 25
    top_jobs = min(25, max(5, 100))
    assert top_jobs == 25
```

### Integration Tests
```python
def test_search_with_custom_counts(client):
    """POST /search with custom result counts should use those values."""
    response = client.post('/search', data={
        'role_description': 'Data Engineer',
        'top_jobs': '20',
        'top_resume_recs': '7',
        'top_blind_spots': '3'
    })
    # Verify response includes exactly 20 jobs, 7 recommendations, 3 blind spots
    # (check HTML or JSON output depending on response format)
```

### Manual Testing
1. Open search form
2. Drag each slider to various positions; verify count display updates in real-time
3. Submit form; verify results show correct counts
4. Test edge cases:
   - Drag to minimum (5, 3, 1)
   - Drag to maximum (25, 10, 10)
   - Verify counts in rendered output match slider values

---

## FILES TO MODIFY

| File | Lines | Change |
|------|-------|--------|
| `templates/index.html` | (search form section) | Add three `<input type="range">` sliders + JS listeners |
| `app/routes.py` | 68–150 | Extract and validate result count parameters |
| `app/routes.py` | 135–147 | Replace hardcoded `TOP_JOBS` etc. with variables |
| `app/agents/crew.py` | 10–22 | Update SearchRequest dataclass with new fields |
| `app/agents/crew.py` | 100–140 | Update task descriptions to use `search_request.top_*` |
| `app/scheduler.py` | 45–60 | Add result count parameters to scheduled SearchRequest |

---

## SUCCESS CRITERIA

✓ Users can adjust result counts via sliders (5–25 jobs, 3–10 recommendations, 1–10 blind spots)  
✓ Live count display updates as user drags  
✓ Default values are sensible and used when sliders not adjusted  
✓ Values clamped to valid range without errors  
✓ CrewAI pipeline respects user-selected counts  
✓ Fallback matcher uses same counts as CrewAI  
✓ Scheduler uses appropriate defaults (15 jobs, 5 recs, 5 blind spots)  
✓ All tests pass (unit + integration)  

---

## NOTES

- **Backward compatibility:** If user submits form without sliders (old HTML), defaults apply automatically
- **No database changes:** Values are ephemeral, not stored per-user
- **Scheduler optimization:** Weekly scheduled runs use slightly higher job count (15) to give more options without overwhelming
- **Future enhancement:** Could store user preferences in a user profile if multi-session support is added (PHASE 3+ feature)
