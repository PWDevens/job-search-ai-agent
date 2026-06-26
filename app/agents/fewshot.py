"""
Few-shot exemplars for prompt-based improvement (PROMPT_FEWSHOT).
Generic, non-persona-specific examples that demonstrate the STRUCTURE of a well-grounded
output. Deliberately span tech AND non-tech fields (healthcare, skilled trades, finance)
so the examples teach grounding/citation form without biasing the agent toward tech
skills on non-tech personas. They cite generic illustrative employers, not any eval
persona's actual targets — they model format, not answers.
"""

FEWSHOT_RESUME_COACH = """
**Example 1 (tech):** Priority HIGH, Title: "Add cloud certification", Fix: "Pursue AWS Solutions Architect Associate", Why: "Two target postings (Data Engineer, Platform Engineer) list cloud platform expertise as required", Impact: "Qualifies for ~40% more of the matched roles", Time: "8-12 weeks self-study"

**Example 2 (healthcare):** Priority HIGH, Title: "Surface BLS/ACLS certifications", Fix: "List current ACLS and PALS credentials in a Certifications section", Why: "The matched Charge Nurse and ICU RN postings name ACLS as a hard requirement", Impact: "Clears an ATS knockout filter present in most of the matched roles", Time: "1 day (already certified — formatting only)"

**Example 3 (skilled trade):** Priority MEDIUM, Title: "Quantify project scope", Fix: "Add voltage/scale of systems worked on (e.g., '480V three-phase, 200+ device installs')", Why: "The matched Master Electrician and Industrial Electrician postings ask for commercial/industrial scale", Impact: "Differentiates from residential-only candidates", Time: "2-3 hours"
"""

FEWSHOT_CAREER_STRATEGIST = """
**Example 1 (tech blind spot):** Skill: "Kubernetes", Why: "Two matched postings (Platform Engineer, DevOps Lead) require container orchestration", Remediation: "Complete a Kubernetes course (6-8 weeks); deploy a personal project to a cluster", Priority: HIGH

**Example 2 (non-tech blind spot):** Skill: "value-based care metrics", Why: "The matched Nurse Manager postings name HCAHPS/quality-outcome reporting", Remediation: "Take an employer LMS module on quality metrics; shadow a unit's reporting cycle", Priority: MEDIUM

**Example (strategic action):** Build a 12-week plan tied to the gaps the postings actually name — earn the single most-cited missing credential first, then add one portfolio/work artifact that demonstrates it.
"""

FEWSHOT_JOB_MATCHER = """
**Example 1 (tech):** Title: "Data Platform Engineer", Company: "(matched posting)", Why: "Strong fit for your SQL + data-pipeline background; the posting names the same warehouse tooling on your resume"

**Example 2 (non-tech):** Title: "Senior Accountant", Company: "(matched posting)", Why: "Direct fit for your GAAP + month-end-close experience; the posting lists the reconciliations you already own"
"""
