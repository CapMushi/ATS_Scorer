"""
LLM prompt templates for CV extraction and JD analysis.
All prompts return structured JSON for reliable parsing.

v2: Restructured for DETERMINISTIC skill evaluation.
The prompt forces the LLM to evaluate EACH required skill individually
with a found: true/false field, eliminating open-ended ambiguity.
"""


def build_cv_extraction_prompt(cv_text: str, required_skills: list[str]) -> str:
    """
    Build a prompt that extracts ALL structured data from a CV in ONE call.
    Returns: name, contact, skill_evaluation (forced per-skill), experience, YOE, education, summary.
    
    KEY CHANGE: Instead of open-ended "skills_found", the LLM MUST evaluate
    EVERY required skill with found=true/false. This eliminates non-determinism.
    """
    # Build the explicit skill evaluation instruction
    if required_skills:
        skills_instruction = "REQUIRED SKILLS TO EVALUATE (you MUST include ALL of these in skill_evaluation, even if missing):\n"
        for i, skill in enumerate(required_skills, 1):
            skills_instruction += f"  {i}. {skill}\n"
        skills_instruction += "\nFor EACH skill above, you MUST return an entry in skill_evaluation with found=true or found=false."
    else:
        skills_instruction = "No specific skills to evaluate. Return an empty skill_evaluation array."

    return f"""You are a CV parser. Extract structured data from the CV below and return ONLY a single valid JSON object. No extra text before or after the JSON.

RULES:
- Return ONLY the JSON object, nothing else
- No trailing commas
- No comments
- Use empty string "" for missing string fields
- Use 0 for missing numeric fields
- Use [] for missing array fields
- If a field cannot be determined, use its default value
- CRITICAL: You MUST evaluate EVERY required skill listed below. Do NOT skip any.

{skills_instruction}

For each skill, classify its context:
- "project" = skill is USED in a described project, role, or achievement (e.g., "Built REST API using Flask" means Python is used in a project)
- "mentioned" = skill is only LISTED in a skills section or mentioned without usage context
- "missing" = skill is NOT found anywhere in the CV (set found=false)

For experience_entries, extract EACH job/role with its start and end dates.
Calculate the months field as the number of months between start and end.
If end is "present" or "current", use September 2026 as the end date.
CRITICAL: Do NOT include education, degrees, or university coursework in experience_entries.
If the candidate has no professional experience, set experience_entries to [] and total_yoe to 0.0.

CV TEXT:
---
{cv_text}
---

Return EXACTLY this JSON structure with ALL fields filled:
{{
  "candidate_name": "Full Name Here",
  "email": "",
  "phone": "",
  "linkedin": "",
  "github": "",
  "portfolio": "",
  "location": "",
  "skill_evaluation": [
    {{"name": "Python", "found": true, "context": "project", "evidence": "Built REST API with Flask"}},
    {{"name": "React", "found": false, "context": "missing", "evidence": ""}},
    {{"name": "AWS", "found": true, "context": "mentioned", "evidence": "Listed in skills section"}}
  ],
  "experience_entries": [
    {{
      "role": "Job Title",
      "company": "Company Name",
      "start": "YYYY-MM",
      "end": "YYYY-MM or present",
      "months": 24,
      "key_work": "One-line description of main achievement"
    }}
  ],
  "total_yoe": 0.0,
  "current_role": "",
  "education": [
    {{"degree": "BS Computer Science", "institution": "University Name", "year": "2018-2022"}}
  ],
  "certifications": [],
  "candidate_summary": "2-3 sentence professional summary highlighting key strengths and main technologies."
}}

IMPORTANT: The skill_evaluation array MUST contain EXACTLY {len(required_skills)} entries — one for EACH required skill listed above. Do NOT add extra skills. Do NOT skip any."""


def build_jd_extraction_prompt(jd_text: str) -> str:
    """
    Build a prompt to extract structured requirements from a Job Description.
    """
    return f"""You are a job description parser. Extract structured requirements from the JD below and return ONLY a single valid JSON object. No extra text.

RULES:
- Return ONLY the JSON object
- No trailing commas, no comments
- Use [] for empty arrays, 1.0 for unknown YOE

JOB DESCRIPTION:
---
{jd_text[:4000]}
---

Return EXACTLY this JSON structure:
{{
  "must_have_skills": ["Skill1", "Skill2"],
  "nice_to_have_skills": ["Skill1", "Skill2"],
  "required_yoe": 3.0,
  "role_title": "Job Title",
  "key_requirements": ["Requirement 1", "Requirement 2"]
}}

Rules for skill extraction:
- must_have_skills: Technical skills explicitly required or repeatedly mentioned
- nice_to_have_skills: Skills mentioned as "preferred", "bonus", or "nice to have"
- required_yoe: Minimum years of experience mentioned (default 1.0 if not specified)
- Use canonical skill names (e.g., "React" not "ReactJS", "AWS" not "Amazon Web Services")"""
