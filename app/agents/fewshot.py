"""
Few-shot exemplars for prompt-based improvement (Config B).
Generic, non-persona-specific examples showing well-grounded outputs.
"""

FEWSHOT_RESUME_COACH = """
**Example 1:** Priority HIGH, Title: "Add AWS certification", Fix: "Pursue AWS Solutions Architect Associate", Why: "Senior Data Engineer at Accenture and Cloud Infrastructure Specialist at Google Cloud both require cloud platform expertise", Impact: "Opens positions in 40%+ of target roles", Time: "8-12 weeks self-study"

**Example 2:** Priority MEDIUM, Title: "Strengthen SQL optimization", Fix: "Study query plans and indexing via DataCamp", Why: "Analytics Engineer at Microsoft and Senior BI Analyst at Deloitte emphasize advanced SQL", Impact: "Improves technical depth for mid-career advancement", Time: "4-6 weeks"
"""

FEWSHOT_CAREER_STRATEGIST = """
**Example 1 (Blind Spot):** Skill: "Kubernetes", Why: "Platform Engineer at Netflix and DevOps Lead at Stripe both require container orchestration expertise", Remediation: "Complete Linux Academy Kubernetes course (6-8 weeks); contribute to open-source K8s projects", Priority: HIGH

**Example 2 (Strategic Action):** Build a 12-week project plan: Month 1-2 complete GCP certification (visible on LinkedIn); Month 3 contribute to 2 cloud-native OSS repos; Month 4-6 apply to cloud roles at mid-market tech companies
"""

FEWSHOT_JOB_MATCHER = """
**Example 1:** Title: "Senior Machine Learning Engineer", Company: "Accenture", Why: "Aligns with your analytics background; Accenture projects use Python, MLOps, and cloud deployment"

**Example 2:** Title: "Data Platform Engineer", Company: "Google Cloud", Why: "Strong match for your data engineering + SQL skills; role involves designing enterprise data systems on GCP"
"""
