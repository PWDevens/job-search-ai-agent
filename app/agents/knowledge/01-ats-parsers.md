# How ATS Parsers Read Resumes

Applicant Tracking Systems (ATS) parse resumes by extracting text and mapping it to
structured fields: contact info, work history, education, and skills. Most modern ATS
platforms (Workday, Greenhouse, Lever, iCIMS, Taleo) combine rule-based patterns with
ML classifiers. These rules apply to every field — nursing, trades, finance, sales,
education, tech, and beyond.

Key parsing rules:
1. FILE FORMAT: Submit PDF or DOCX. PDFs created from Word/Google Docs parse cleanly.
   PDFs exported from image editors or scanned documents fail badly. Never use tables,
   text boxes, headers/footers, or multi-column layouts — these confuse almost every parser.
2. SECTION HEADERS: Use plain headers — "Work Experience," "Education," "Skills,"
   "Licenses & Certifications." Creative names like "My Journey" are frequently skipped.
3. DATES: Use a consistent Month Year format (e.g., Jan 2022 – Mar 2024). Always include
   both start and end.
4. JOB TITLES: Match the exact title or close variants used in the posting. ATS systems
   score exact matches higher than synonyms.
5. KEYWORDS: ATS scores resumes by keyword density relative to the job description.
   Include both acronyms and full forms (e.g., "RN" and "Registered Nurse"; "PE" and
   "Professional Engineer").
6. SKILLS / LICENSES SECTION: A clearly labeled Skills, Technical Skills, or Licenses &
   Certifications section dramatically improves extraction. List items as a comma-separated
   or bulleted list, not buried in paragraphs.
