import os
import json
import warnings
with warnings.catch_warnings():
    warnings.simplefilter("ignore", FutureWarning)
    import google.generativeai as genai
from modules.helpers import print_lg
from modules.cold_email.templates import get_fallback_email, ColdEmailContent

GMAIL_ENV_PATH = "config/email/.env"

def _read_env_file(path: str) -> dict[str, str]:
    values: dict[str, str] = {}
    if not os.path.exists(path):
        return values
    try:
        with open(path, "r", encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    except Exception as e:
        print_lg(f"Error reading env file: {e}")
    return values

def load_gemini_api_key() -> str:
    env_values = _read_env_file(GMAIL_ENV_PATH)
    return env_values.get("GEMINI_API_KEY", "").strip()

def generate_cold_email(job_data: dict, resume_text: str) -> ColdEmailContent:
    """Generates personalized cold email using Gemini API, or falls back to templates on failure."""
    if job_data.get("recruiter_email_source") == "validation_seed":
        print_lg("Validation seed row detected. Using fallback cold email template for deterministic SMTP QA.")
        return get_fallback_email(job_data)

    api_key = load_gemini_api_key()
    if not api_key:
        print_lg("GEMINI_API_KEY is not set in config/email/.env. Using fallback template.")
        return get_fallback_email(job_data)
        
    try:
        genai.configure(api_key=api_key)
        
        # Prepare inputs
        company = job_data.get("company") or "your company"
        role = job_data.get("title") or "the open role"
        recruiter_name = job_data.get("recruiter_name") or ""
        if not recruiter_name or recruiter_name.lower().strip() == "unknown":
            recruiter_name = "Hiring Team"
            
        jd = job_data.get("job_description") or ""
        jd_summary = jd[:1000] if jd else "Not Available"
        
        skills_required = job_data.get("skills_required") or "Not Specified"
        work_style = job_data.get("work_style") or "Not Specified"
        
        prompt = f"""You are a professional outreach assistant. Your task is to generate a highly personalized, human-sounding, and concise cold outreach email to a recruiter for a job application.

Inputs:
- Recruiter Name: {recruiter_name}
- Job Title / Role: {role}
- Company: {company}
- Job Description (partial): {jd_summary}
- Skills Required: {skills_required}
- Work Style: {work_style}
- Applicant Name: Manvendra Singh
- Applicant Resume / Profile Summary: {resume_text[:2000] if resume_text else "Not Available"}

Requirements:
1. Tone must be professional, confident, human, and concise. Avoid buzzwords or spammy sales pitches.
2. Personalize the email based on the company's domain/role and the applicant's resume highlights. Keep the body short (under 150 words).
3. Do NOT make up false details about the applicant. Use the provided resume text as the ground truth.
4. Output the response in JSON format with two keys:
   - 'subject': A catchy, professional subject line.
   - 'body': The email body, addressing the recruiter.

JSON schema:
{{
  "subject": "...",
  "body": "..."
}}
"""
        
        model = genai.GenerativeModel("gemini-2.5-flash")
        
        # Call Gemini API
        print_lg(f"Requesting cold email generation from Gemini for {role} at {company}...")
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        result_text = response.text
        data = json.loads(result_text)
        
        subject = data.get("subject", "").strip()
        body = data.get("body", "").strip()
        
        if not subject or not body:
            raise ValueError("Gemini returned empty subject or body.")
            
        return ColdEmailContent(subject, body, "gemini")
        
    except Exception as e:
        print_lg(f"Gemini email generation failed safely: {e}. Falling back to templates.")
        return get_fallback_email(job_data)
