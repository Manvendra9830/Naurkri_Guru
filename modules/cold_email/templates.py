import random

TEMPLATES = [
    {
        "subject": "Inquiry regarding {role} role at {company}",
        "body": (
            "Dear {recruiter_name},\n\n"
            "I hope you are doing well.\n\n"
            "I recently applied for the {role} position at {company} via LinkedIn and wanted to express my strong interest in the opportunity.\n\n"
            "With my background in Computer Science, Machine Learning, and Software Engineering, I have hands-on experience building AI-driven applications, designing scalable pipelines, and working with PyTorch and LLMs. I am confident my technical skills align well with the team's needs.\n\n"
            "I have attached my resume and cover letter to this email for your review. I would appreciate the opportunity to speak with you about how my experience can contribute to {company}.\n\n"
            "Thank you for your time and consideration.\n\n"
            "Best regards,\n"
            "{applicant_name}\n"
            "manvendra9830@gmail.com | +91 9662789830"
        )
    },
    {
        "subject": "{role} Application - {applicant_name}",
        "body": (
            "Hi {recruiter_name},\n\n"
            "I hope this email finds you well.\n\n"
            "My name is {applicant_name}, and I'm reaching out to introduce myself as an applicant for the {role} role at {company}.\n\n"
            "As a B.Tech CSE student at IIIT Raichur, I have developed a strong foundation in software engineering, machine learning, and AI agent systems. Having interned at Darwix AI and IIT Madras, I have built real-world experience working on vector search (FAISS) and LLM-based application development.\n\n"
            "My resume and cover letter are attached. I would love to connect briefly to discuss how my skill set could benefit your team at {company}.\n\n"
            "Thank you so much for your time.\n\n"
            "Sincerely,\n"
            "{applicant_name}\n"
            "manvendra9830@gmail.com | +91 9662789830"
        )
    },
    {
        "subject": "Connecting regarding the {role} opening at {company}",
        "body": (
            "Dear {recruiter_name},\n\n"
            "I hope you're having a great week.\n\n"
            "I'm reaching out regarding the {role} position currently open at {company}.\n\n"
            "I bring solid experience in Python, C++, and AI/ML technologies. In my recent roles, I have optimized ML pipelines and deployed AI-driven automation workflows. Given {company}'s reputation for innovation, I am eager to bring my problem-solving skills to your engineering team.\n\n"
            "I have attached my resume and cover letter for reference. If your schedule allows, I would welcome the chance to connect for a short conversation.\n\n"
            "Thank you for your consideration.\n\n"
            "Warm regards,\n"
            "{applicant_name}\n"
            "manvendra9830@gmail.com | +91 9662789830"
        )
    }
]

class ColdEmailContent:
    def __init__(self, subject: str, body: str, generated_by: str):
        self.subject = subject
        self.body = body
        self.generated_by = generated_by

def get_fallback_email(job_data: dict) -> ColdEmailContent:
    company = job_data.get("company") or "your company"
    role = job_data.get("title") or "the open role"
    
    recruiter_name = job_data.get("recruiter_name") or ""
    if not recruiter_name or recruiter_name.lower().strip() == "unknown":
        recruiter_name = "Hiring Team"
    else:
        recruiter_name = recruiter_name.strip()
        
    applicant_name = "Manvendra Singh"
    
    template = random.choice(TEMPLATES)
    
    subject = template["subject"].format(
        company=company,
        role=role,
        applicant_name=applicant_name
    )
    
    body = template["body"].format(
        company=company,
        role=role,
        recruiter_name=recruiter_name,
        applicant_name=applicant_name
    )
    
    return ColdEmailContent(subject, body, "fallback_template")
