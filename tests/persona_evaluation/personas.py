"""
Synthetic personas for systematic evaluation of Job-Search AI Agent.
Each persona has a realistic resume, background, and search variants to test.
"""
from dataclasses import dataclass
from typing import List, Dict, Any
from pathlib import Path


@dataclass
class SearchVariant:
    """A specific search query variant for testing"""
    name: str
    role_description: str
    geo_preference: str = None
    use_resume: bool = True
    expected_job_fields: List[str] = None  # Expected job domains


@dataclass
class Persona:
    """A test persona with resume, background, and search variants"""
    name: str
    role: str
    years_experience: int
    resume_path: str
    search_variants: List[SearchVariant]
    target_job_titles: List[str]  # What "good match" looks like
    expected_blind_spots: List[str]  # Known skill gaps to validate
    stay_in_field_titles: List[str] = None  # Realistic same-profession target roles
    stay_in_field_blind_spots: List[str] = None  # Realistic same-profession skill gaps


# Load resume files from synthetic data directory
RESUME_DIR = Path(__file__).parent.parent.parent / "data" / "synthetic"


def load_resume(filename: str) -> str:
    """Load persona resume from file"""
    path = RESUME_DIR / filename
    if not path.exists():
        return f"[Resume file not found: {path}]"
    return path.read_text()


# Define the 5 personas
NURSE = Persona(
    name="Nurse",
    role="Registered Nurse",
    years_experience=8,
    resume_path=str(RESUME_DIR / "nurse_resume.txt"),
    search_variants=[
        SearchVariant(
            name="informatics_with_resume",
            role_description="Nursing informaticist with healthcare IT and EHR experience transitioning to data analytics",
            geo_preference="Remote",
            use_resume=True,
            expected_job_fields=["healthcare", "clinical_it", "health_data"],
        ),
        SearchVariant(
            name="data_analyst_with_resume",
            role_description="Healthcare data analyst with clinical background looking to leverage patient outcome analysis skills",
            geo_preference="Washington DC",
            use_resume=True,
            expected_job_fields=["healthcare", "analytics"],
        ),
        SearchVariant(
            name="clinical_specialist_no_resume",
            role_description="Clinical IT specialist with 8 years nursing experience and basic data skills",
            geo_preference=None,
            use_resume=False,
            expected_job_fields=["healthcare", "clinical"],
        ),
    ],
    target_job_titles=[
        "Healthcare Data Analyst",
        "Clinical Informatics Specialist",
        "Health Information Manager",
        "Population Health Analyst",
    ],
    expected_blind_spots=["Python", "SQL", "machine learning", "statistical analysis"],
    stay_in_field_titles=[
        "ICU Registered Nurse",
        "Charge Nurse",
        "Nurse Manager",
        "Clinical Nurse Educator",
    ],
    stay_in_field_blind_spots=["patient", "nursing", "care", "assessment"],
)

TEACHER = Persona(
    name="Teacher",
    role="High School Mathematics Teacher",
    years_experience=10,
    resume_path=str(RESUME_DIR / "teacher_resume.txt"),
    search_variants=[
        SearchVariant(
            name="learning_analytics_with_resume",
            role_description="High school mathematics teacher seeking transition to learning analytics and educational data",
            geo_preference="Remote",
            use_resume=True,
            expected_job_fields=["education", "analytics", "learning_analytics"],
        ),
        SearchVariant(
            name="ed_tech_with_resume",
            role_description="Curriculum designer with data analysis experience looking for educational technology role",
            geo_preference="San Francisco",
            use_resume=True,
            expected_job_fields=["education", "technology"],
        ),
        SearchVariant(
            name="instructional_designer_no_resume",
            role_description="Instructional designer with 10 years education experience and Google Classroom proficiency",
            geo_preference=None,
            use_resume=False,
            expected_job_fields=["education", "instructional_design"],
        ),
    ],
    target_job_titles=[
        "Learning Analytics Manager",
        "Education Technology Specialist",
        "Educational Data Scientist",
        "Instructional Designer Analyst",
    ],
    expected_blind_spots=["Python", "SQL", "machine learning", "statistical software"],
    stay_in_field_titles=[
        "High School Mathematics Teacher",
        "Curriculum Developer",
        "Instructional Coach",
        "Department Chair",
    ],
    stay_in_field_blind_spots=["curriculum", "classroom", "instruction", "coaching"],
)

CONSULTANT = Persona(
    name="Consultant",
    role="Management Consultant (Strategy)",
    years_experience=6,
    resume_path=str(RESUME_DIR / "consultant_resume.txt"),
    search_variants=[
        SearchVariant(
            name="data_scientist_with_resume",
            role_description="Management consultant with 6 years BCG experience and MBA seeking senior data scientist role",
            geo_preference="Remote",
            use_resume=True,
            expected_job_fields=["analytics", "data_science", "strategy"],
        ),
        SearchVariant(
            name="analytics_leader_with_resume",
            role_description="Strategy consultant with financial modeling and Tableau experience transitioning to analytics leadership",
            geo_preference="New York",
            use_resume=True,
            expected_job_fields=["analytics", "leadership"],
        ),
        SearchVariant(
            name="quantitative_analyst_no_resume",
            role_description="Quantitative analyst with MBA and 6 years consulting experience",
            geo_preference=None,
            use_resume=False,
            expected_job_fields=["analytics", "quantitative"],
        ),
    ],
    target_job_titles=[
        "Data Scientist",
        "Senior Data Scientist",
        "Analytics Manager",
        "Quantitative Analyst",
        "Analytics Consultant",
    ],
    expected_blind_spots=["Python", "SQL", "machine learning", "data engineering"],
    stay_in_field_titles=[
        "Management Consultant",
        "Strategy Manager",
        "Engagement Manager",
        "Operations Consultant",
    ],
    stay_in_field_blind_spots=["strategy", "engagement", "client", "consulting"],
)

ENGINEER = Persona(
    name="Civil Engineer",
    role="Civil Engineer (Infrastructure)",
    years_experience=9,
    resume_path=str(RESUME_DIR / "engineer_resume.txt"),
    search_variants=[
        SearchVariant(
            name="geospatial_with_resume",
            role_description="Civil engineer with 9 years infrastructure experience and GIS/ArcGIS skills seeking geospatial data analytics role",
            geo_preference="Remote",
            use_resume=True,
            expected_job_fields=["infrastructure", "geospatial", "gis"],
        ),
        SearchVariant(
            name="infrastructure_analytics_with_resume",
            role_description="Infrastructure engineer with AutoCAD and project management experience looking for data analytics in transportation",
            geo_preference="Washington DC",
            use_resume=True,
            expected_job_fields=["infrastructure", "analytics"],
        ),
        SearchVariant(
            name="water_resources_no_resume",
            role_description="PE-licensed civil engineer with water infrastructure background and ArcGIS experience",
            geo_preference=None,
            use_resume=False,
            expected_job_fields=["infrastructure", "water"],
        ),
    ],
    target_job_titles=[
        "Infrastructure Data Analyst",
        "Geospatial Data Scientist",
        "Water Resources Data Analyst",
        "Transportation Planner Data Analytics",
        "Infrastructure Analytics Manager",
    ],
    expected_blind_spots=["Python", "SQL", "machine learning", "data engineering", "cloud platforms"],
    stay_in_field_titles=[
        "Structural Engineer",
        "Transportation Engineer",
        "Water Resources Engineer",
        "Civil Project Manager",
    ],
    stay_in_field_blind_spots=["AutoCAD", "scheduling", "structural", "permitting"],
)

DESIGNER = Persona(
    name="Digital Designer",
    role="UX/Product Designer",
    years_experience=5,
    resume_path=str(RESUME_DIR / "designer_resume.txt"),
    search_variants=[
        SearchVariant(
            name="product_analytics_with_resume",
            role_description="Product designer with 5 years UX experience and user research skills seeking product analytics role",
            geo_preference="Remote",
            use_resume=True,
            expected_job_fields=["product", "analytics", "design"],
        ),
        SearchVariant(
            name="design_analytics_with_resume",
            role_description="UX designer with Figma and Google Analytics experience transitioning to design analytics or research data",
            geo_preference="San Francisco",
            use_resume=True,
            expected_job_fields=["design", "analytics"],
        ),
        SearchVariant(
            name="growth_analyst_no_resume",
            role_description="Designer with 5 years product experience and user engagement analysis skills",
            geo_preference=None,
            use_resume=False,
            expected_job_fields=["product", "growth"],
        ),
    ],
    target_job_titles=[
        "Product Data Analyst",
        "Design Analytics Manager",
        "UX Research Data Scientist",
        "Product Analytics Lead",
        "Analytics Engineer",
    ],
    expected_blind_spots=["Python", "SQL", "machine learning", "data engineering"],
    stay_in_field_titles=[
        "UX Designer",
        "Product Designer",
        "Senior UX Researcher",
        "Design Lead",
    ],
    stay_in_field_blind_spots=["Figma", "user research", "design systems", "prototyping"],
)


ACCOUNTANT = Persona(
    name="Accountant",
    role="Certified Public Accountant",
    years_experience=9,
    resume_path=str(RESUME_DIR / "accountant_resume.txt"),
    search_variants=[
        SearchVariant(
            name="financial_analyst_with_resume",
            role_description="CPA with 9 years accounting and financial planning seeking transition to finance analytics role",
            geo_preference="Remote",
            use_resume=True,
            expected_job_fields=["accounting", "finance", "financial analysis"],
        ),
        SearchVariant(
            name="controller_with_resume",
            role_description="Senior accountant with strong financial analysis and budgeting expertise looking for controller or finance leadership role",
            geo_preference="New York",
            use_resume=True,
            expected_job_fields=["finance", "accounting", "leadership"],
        ),
        SearchVariant(
            name="audit_analyst_no_resume",
            role_description="CPA with audit and financial reporting background interested in internal audit or compliance roles",
            geo_preference=None,
            use_resume=False,
            expected_job_fields=["audit", "compliance"],
        ),
    ],
    target_job_titles=[
        "Senior Accountant",
        "Financial Analyst",
        "Controller",
        "Audit Manager",
        "Corporate Finance Manager",
    ],
    expected_blind_spots=["power bi", "sql", "python", "business intelligence", "data analytics"],
    stay_in_field_titles=[
        "Staff Accountant",
        "Senior Accountant",
        "Controller",
        "Cost Accountant",
    ],
    stay_in_field_blind_spots=["GAAP", "reconciliation", "audit", "variance"],
)

SALES_MANAGER = Persona(
    name="Sales Manager",
    role="Sales Manager",
    years_experience=11,
    resume_path=str(RESUME_DIR / "sales_manager_resume.txt"),
    search_variants=[
        SearchVariant(
            name="vp_sales_with_resume",
            role_description="Sales director with 11 years leading teams generating $50M+ revenue seeking VP Sales or revenue leadership role",
            geo_preference="Remote",
            use_resume=True,
            expected_job_fields=["sales", "leadership", "revenue"],
        ),
        SearchVariant(
            name="account_executive_with_resume",
            role_description="Senior sales manager with enterprise account management and Salesforce expertise looking for account executive or sales management role",
            geo_preference="San Francisco",
            use_resume=True,
            expected_job_fields=["sales", "account management"],
        ),
        SearchVariant(
            name="business_development_no_resume",
            role_description="Sales leader with business development and partnership building background interested in BD manager roles",
            geo_preference=None,
            use_resume=False,
            expected_job_fields=["sales", "business development"],
        ),
    ],
    target_job_titles=[
        "Regional Sales Director",
        "Sales Account Executive",
        "Business Development Manager",
        "Territory Sales Manager",
        "Area Sales Manager",
    ],
    expected_blind_spots=["sql", "tableau", "power bi", "python", "data analytics"],
    stay_in_field_titles=[
        "Account Executive",
        "Regional Sales Manager",
        "Business Development Manager",
        "Enterprise Account Executive",
    ],
    stay_in_field_blind_spots=["enterprise sales", "pipeline", "negotiation", "forecasting"],
)

ELECTRICIAN = Persona(
    name="Electrician",
    role="Licensed Journeyman Electrician",
    years_experience=12,
    resume_path=str(RESUME_DIR / "electrician_resume.txt"),
    search_variants=[
        SearchVariant(
            name="supervisor_with_resume",
            role_description="Journeyman electrician with 12 years commercial and industrial experience seeking electrical supervisor or project management role",
            geo_preference="Remote",
            use_resume=True,
            expected_job_fields=["electrical", "supervisor", "management"],
        ),
        SearchVariant(
            name="facilities_with_resume",
            role_description="Electrician with troubleshooting expertise and apprentice training experience looking for facilities or building management role",
            geo_preference="Denver",
            use_resume=True,
            expected_job_fields=["electrical", "facilities"],
        ),
        SearchVariant(
            name="master_electrician_no_resume",
            role_description="Licensed electrician with commercial and industrial systems knowledge interested in master electrician or engineering technician roles",
            geo_preference=None,
            use_resume=False,
            expected_job_fields=["electrical", "engineering"],
        ),
    ],
    target_job_titles=[
        "Licensed Electrician",
        "Master Electrician",
        "Electrical Supervisor",
        "Facilities Electrician",
        "Plant Electrician",
    ],
    expected_blind_spots=["cad", "autocad", "python", "project management software"],
    stay_in_field_titles=[
        "Journeyman Electrician",
        "Master Electrician",
        "Electrical Foreman",
        "Industrial Electrician",
    ],
    stay_in_field_blind_spots=["NEC code", "electrical installation", "troubleshooting", "conduit"],
)

HR_MANAGER = Persona(
    name="HR Manager",
    role="HR Manager",
    years_experience=10,
    resume_path=str(RESUME_DIR / "hr_manager_resume.txt"),
    search_variants=[
        SearchVariant(
            name="talent_director_with_resume",
            role_description="HR manager with 10 years leading talent acquisition and employee engagement seeking HR director or talent leadership role",
            geo_preference="Remote",
            use_resume=True,
            expected_job_fields=["hr", "recruiting", "talent"],
        ),
        SearchVariant(
            name="compensation_analyst_with_resume",
            role_description="HR professional with compensation analysis and benefits management experience looking for comp analyst or benefits role",
            geo_preference="New York",
            use_resume=True,
            expected_job_fields=["hr", "compensation", "benefits"],
        ),
        SearchVariant(
            name="employee_relations_no_resume",
            role_description="HR specialist with employee relations and engagement background interested in employee relations or organizational development roles",
            geo_preference=None,
            use_resume=False,
            expected_job_fields=["hr", "employee relations"],
        ),
    ],
    target_job_titles=[
        "HR Manager",
        "Talent Acquisition Manager",
        "HR Business Partner",
        "Compensation Analyst",
        "Employee Relations Manager",
    ],
    expected_blind_spots=["tableau", "power bi", "sql", "python", "data analytics"],
    stay_in_field_titles=[
        "HR Generalist",
        "HR Business Partner",
        "Corporate Recruiter",
        "Talent Acquisition Manager",
    ],
    stay_in_field_blind_spots=["talent", "employee relations", "recruiting", "benefits"],
)

OPERATIONS_MANAGER = Persona(
    name="Operations Manager",
    role="Operations Manager",
    years_experience=10,
    resume_path=str(RESUME_DIR / "operations_manager_resume.txt"),
    search_variants=[
        SearchVariant(
            name="supply_chain_director_with_resume",
            role_description="Operations manager with 10 years supply chain and process optimization seeking supply chain director or VP operations role",
            geo_preference="Remote",
            use_resume=True,
            expected_job_fields=["operations", "supply_chain", "logistics"],
        ),
        SearchVariant(
            name="logistics_manager_with_resume",
            role_description="Operations professional with lean six sigma and cost reduction expertise looking for logistics manager or continuous improvement role",
            geo_preference="Columbus",
            use_resume=True,
            expected_job_fields=["operations", "logistics"],
        ),
        SearchVariant(
            name="warehouse_manager_no_resume",
            role_description="Operations manager with inventory and process management background interested in warehouse or distribution center management roles",
            geo_preference=None,
            use_resume=False,
            expected_job_fields=["operations", "warehouse"],
        ),
    ],
    target_job_titles=[
        "Operations Manager",
        "Supply Chain Manager",
        "Warehouse Manager",
        "Process Improvement Manager",
        "Logistics Coordinator",
    ],
    expected_blind_spots=["tableau", "power bi", "sql", "python", "advanced analytics"],
    stay_in_field_titles=[
        "Operations Manager",
        "Supply Chain Manager",
        "Logistics Coordinator",
        "Process Improvement Manager",
    ],
    stay_in_field_blind_spots=["process improvement", "inventory", "supply chain", "logistics"],
)

TECHNICAL_WRITER = Persona(
    name="Technical Writer",
    role="Technical Writer",
    years_experience=8,
    resume_path=str(RESUME_DIR / "technical_writer_resume.txt"),
    search_variants=[
        SearchVariant(
            name="content_strategist_with_resume",
            role_description="Technical writer with 8 years documentation experience seeking content strategy or information architecture role",
            geo_preference="Remote",
            use_resume=True,
            expected_job_fields=["technical_writing", "content", "documentation"],
        ),
        SearchVariant(
            name="api_documentation_with_resume",
            role_description="Documentation specialist with API and developer portal experience looking for technical writing or developer relations role",
            geo_preference="San Francisco",
            use_resume=True,
            expected_job_fields=["technical_writing", "documentation"],
        ),
        SearchVariant(
            name="instructional_design_no_resume",
            role_description="Technical writer with training materials and user guide background interested in instructional design or content creation roles",
            geo_preference=None,
            use_resume=False,
            expected_job_fields=["documentation", "content"],
        ),
    ],
    target_job_titles=[
        "Technical Writer",
        "Documentation Manager",
        "API Documentation Specialist",
        "Content Strategist",
        "Instructional Design Writer",
    ],
    expected_blind_spots=["tableau", "sql", "python", "data analytics"],
    stay_in_field_titles=[
        "Technical Writer",
        "Senior Technical Writer",
        "Documentation Manager",
        "API Documentation Specialist",
    ],
    stay_in_field_blind_spots=["documentation", "technical writing", "editing", "content strategy"],
)

# ── Tier-1 market-demand personas (iter6) ─────────────────────────────────────
# Added to make the eval represent high-EMPLOYMENT occupations (BLS): healthcare
# support (#1 occupation), computer/math (#2 growth), office/admin. Mobility is
# realistic (ladder-up/adjacent), NOT forced "-> analytics"; gaps emphasize the
# certification/license path that the CareerOneStop layer will serve.

HOME_HEALTH_AIDE = Persona(
    name="Home Health Aide",
    role="Home Health Aide",
    years_experience=5,
    resume_path=str(RESUME_DIR / "home_health_aide_resume.txt"),
    search_variants=[
        SearchVariant(
            name="cna_transition_with_resume",
            role_description="Home health aide with 5 years personal care experience seeking certified nursing assistant or patient care role",
            geo_preference="Phoenix",
            use_resume=True,
            expected_job_fields=["healthcare", "patient_care", "nursing_support"],
        ),
        SearchVariant(
            name="medical_assistant_with_resume",
            role_description="Caregiver with vital signs and activities-of-daily-living experience looking for medical assistant or patient care coordinator role",
            geo_preference="Remote",
            use_resume=True,
            expected_job_fields=["healthcare", "patient_care"],
        ),
        SearchVariant(
            name="caregiver_no_resume",
            role_description="Personal care aide with CPR certification and 5 years home care experience",
            geo_preference=None,
            use_resume=False,
            expected_job_fields=["healthcare", "personal_care"],
        ),
    ],
    target_job_titles=[
        "Certified Nursing Assistant",
        "Medical Assistant",
        "Patient Care Coordinator",
        "Licensed Practical Nurse",
    ],
    expected_blind_spots=["CNA certification", "phlebotomy", "EKG", "Basic Life Support"],
    stay_in_field_titles=[
        "Home Health Aide",
        "Personal Care Aide",
        "Caregiver",
        "Hospice Aide",
    ],
    stay_in_field_blind_spots=["patient care", "vital signs", "ADLs", "CPR"],
)

SOFTWARE_DEVELOPER = Persona(
    name="Software Developer",
    role="Software Developer",
    years_experience=6,
    resume_path=str(RESUME_DIR / "software_developer_resume.txt"),
    search_variants=[
        SearchVariant(
            name="senior_engineer_with_resume",
            role_description="Software developer with 6 years Python and web application experience seeking senior software engineer role",
            geo_preference="Remote",
            use_resume=True,
            expected_job_fields=["software", "engineering", "backend"],
        ),
        SearchVariant(
            name="backend_platform_with_resume",
            role_description="Full-stack developer with REST API and PostgreSQL experience looking for backend or platform engineering role",
            geo_preference="Austin",
            use_resume=True,
            expected_job_fields=["software", "backend"],
        ),
        SearchVariant(
            name="devops_no_resume",
            role_description="Software engineer with 6 years building web applications interested in DevOps or platform engineering roles",
            geo_preference=None,
            use_resume=False,
            expected_job_fields=["software", "devops"],
        ),
    ],
    target_job_titles=[
        "Senior Software Engineer",
        "Backend Engineer",
        "Full Stack Developer",
        "DevOps Engineer",
        "Platform Engineer",
    ],
    expected_blind_spots=["Kubernetes", "AWS", "Docker", "CI/CD"],
    stay_in_field_titles=[
        "Software Developer",
        "Software Engineer",
        "Backend Developer",
        "Web Developer",
    ],
    stay_in_field_blind_spots=["Python", "JavaScript", "REST APIs", "Git"],
)

CUSTOMER_SERVICE_REP = Persona(
    name="Customer Service Rep",
    role="Customer Service Representative",
    years_experience=4,
    resume_path=str(RESUME_DIR / "customer_service_resume.txt"),
    search_variants=[
        SearchVariant(
            name="ops_coordinator_with_resume",
            role_description="Customer service representative with 4 years experience seeking operations coordinator or office administrator role",
            geo_preference="Charlotte",
            use_resume=True,
            expected_job_fields=["operations", "administration", "support"],
        ),
        SearchVariant(
            name="customer_success_with_resume",
            role_description="Client support specialist with CRM and account experience looking for customer success or account manager role",
            geo_preference="Remote",
            use_resume=True,
            expected_job_fields=["customer_success", "account_management"],
        ),
        SearchVariant(
            name="admin_assistant_no_resume",
            role_description="Customer service professional with 4 years call center experience interested in administrative or office coordinator roles",
            geo_preference=None,
            use_resume=False,
            expected_job_fields=["administration", "office"],
        ),
    ],
    target_job_titles=[
        "Operations Coordinator",
        "Administrative Assistant",
        "Customer Success Specialist",
        "Office Manager",
        "Account Manager",
    ],
    expected_blind_spots=["Salesforce", "CRM software", "data analysis", "project coordination"],
    stay_in_field_titles=[
        "Customer Service Representative",
        "Client Support Specialist",
        "Call Center Agent",
        "Customer Support Associate",
    ],
    stay_in_field_blind_spots=["customer service", "CRM", "communication", "ticketing"],
)

# Collection of all personas for testing
ALL_PERSONAS = [NURSE, TEACHER, CONSULTANT, ENGINEER, DESIGNER, ACCOUNTANT, SALES_MANAGER, ELECTRICIAN, HR_MANAGER, OPERATIONS_MANAGER, TECHNICAL_WRITER,
                HOME_HEALTH_AIDE, SOFTWARE_DEVELOPER, CUSTOMER_SERVICE_REP]


# Stay-in-field queries: each persona searches its OWN profession (not pivoting to
# analytics). Used by the staying-in-field eval (#3/#4) against the stay-in-field
# job market. Geo intentionally None = nationwide demand for the role.
STAY_IN_FIELD_QUERIES = {
    "Nurse":              "Registered nurse with ICU and critical care experience seeking RN or charge nurse role",
    "Teacher":            "High school mathematics teacher seeking classroom teaching or curriculum developer role",
    "Consultant":         "Management consultant with strategy and operations experience seeking consulting or strategy manager role",
    "Civil Engineer":     "Licensed civil engineer with infrastructure and structural design experience seeking civil engineering role",
    "Digital Designer":   "Product and UX designer with user research and Figma experience seeking UX or product design role",
    "Accountant":         "CPA with accounting and financial reporting experience seeking senior accountant or controller role",
    "Sales Manager":      "Sales leader with enterprise account and team management experience seeking sales manager or director role",
    "Electrician":        "Journeyman electrician with commercial and industrial experience seeking electrician or electrical supervisor role",
    "HR Manager":         "HR professional with employee relations and talent experience seeking HR generalist or manager role",
    "Operations Manager": "Operations leader with supply chain and process improvement experience seeking operations manager role",
    "Technical Writer":   "Technical writer with software documentation experience seeking technical writing or documentation role",
    "Home Health Aide":   "Home health aide with personal care and vital signs experience seeking home health aide or caregiver role",
    "Software Developer": "Software developer with Python, web, and REST API experience seeking software developer or engineer role",
    "Customer Service Rep": "Customer service representative with call center and CRM experience seeking customer service or client support role",
}


def get_persona_by_name(name: str) -> Persona:
    """Get a persona by name"""
    for persona in ALL_PERSONAS:
        if persona.name.lower() == name.lower():
            return persona
    raise ValueError(f"Persona '{name}' not found. Available: {[p.name for p in ALL_PERSONAS]}")


if __name__ == "__main__":
    # Utility: print persona info for debugging
    print(f"=== JOB-SEARCH AI AGENT PERSONA EVALUATION SUITE ===")
    print(f"Total Personas: {len(ALL_PERSONAS)}")
    print(f"Total Search Variants: {sum(len(p.search_variants) for p in ALL_PERSONAS)}")
    print(f"Coverage: {len(set([field for p in ALL_PERSONAS for v in p.search_variants for field in (v.expected_job_fields or [])]))} unique job fields")
    print()

    for i, persona in enumerate(ALL_PERSONAS, 1):
        print(f"{i}. {persona.name} ({persona.role}) - {persona.years_experience} years")
        print(f"   Resume: {persona.resume_path}")
        print(f"   Search variants: {len(persona.search_variants)}")
        for variant in persona.search_variants:
            print(f"     - {variant.name}: '{variant.role_description[:60]}...'")
        print(f"   Target roles: {', '.join(persona.target_job_titles[:3])}")
        print(f"   Expected blind spots: {', '.join(persona.expected_blind_spots[:3])}")
        print()
