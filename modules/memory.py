import json
import os
import re
from datetime import datetime

MEMORY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'memory.json')

class UserCancelledException(Exception):
    """Raised when the user cancels the input prompt for an unknown question."""
    pass

def load_memory() -> dict:
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Upgrade legacy format if needed
                updated = False
                for k, v in list(data.items()):
                    if isinstance(v, str):
                        data[k] = {"answer": v, "category": infer_category(k), "confidence": 1.0, "source": "user_input", "last_used": datetime.now().isoformat()}
                        updated = True
                    elif isinstance(v, dict):
                        # Ensure fields exist
                        if "confidence" not in v:
                            v["confidence"] = 1.0
                            updated = True
                        if "source" not in v:
                            v["source"] = "user_input"
                            updated = True
                        if "last_used" not in v:
                            v["last_used"] = datetime.now().isoformat()
                            updated = True
                if updated:
                    save_memory(data)
                return data
        except Exception:
            return {}
    return {}

def save_memory(memory: dict):
    with open(MEMORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(memory, f, indent=4)

def normalize_question(question: str) -> str:
    # Basic normalization to improve matching
    q = question.lower()
    q = re.sub(r'[^a-z0-9\s]', '', q)
    q = re.sub(r'\s+', ' ', q).strip()
    return q

def infer_category(question: str) -> str:
    q = question.lower()
    if 'experience' in q or 'years' in q: return 'experience'
    if 'sponsor' in q or 'visa' in q: return 'sponsorship'
    if 'relocat' in q: return 'relocation'
    if 'salary' in q or 'ctc' in q or 'compensation' in q: return 'salary'
    if 'notice' in q: return 'notice_period'
    if 'educat' in q or 'degree' in q or 'university' in q: return 'education'
    if 'authoriz' in q or 'citizenship' in q or 'legally' in q: return 'work_authorization'
    if 'remote' in q or 'hybrid' in q or 'onsite' in q: return 'work_mode'
    return 'generic'


SKILL_EXPERIENCE_KEYWORDS = [
    'python', 'react', 'machine learning', 'ml', 'ai', 'generative ai', 'genai',
    'deep learning', 'nlp', 'javascript', 'typescript', 'java', 'c++', 'c#',
    'sql', 'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'django', 'flask',
    'node', 'backend', 'frontend', 'fullstack', 'full-stack', 'data science',
    'tensorflow', 'pytorch', 'selenium', 'automation'
]


def skill_experience_memory_key(question: str) -> str | None:
    q = normalize_question(question)
    if not any(token in q for token in ('experience', 'years', 'year')):
        return None
    for skill in SKILL_EXPERIENCE_KEYWORDS:
        normalized_skill = normalize_question(skill)
        if normalized_skill in q:
            if normalized_skill == 'ml':
                normalized_skill = 'ml'
            return f"{normalized_skill} experience"
    return None


def is_skill_specific_experience_question(question: str) -> bool:
    return skill_experience_memory_key(question) is not None

def get_answer_from_memory(question: str, memory: dict) -> str | None:
    from datetime import datetime
    norm_q = normalize_question(question)
    # Exact match on normalized
    if norm_q in memory and isinstance(memory[norm_q], dict):
        memory[norm_q]['last_used'] = datetime.now().isoformat()
        save_memory(memory)
        return memory[norm_q].get('answer')
    
    # Simple fuzzy: check if memory key is inside the question or vice versa
    for key, val in memory.items():
        if key and len(key) > 3 and (key in norm_q or norm_q in key):
            if isinstance(val, dict):
                val['last_used'] = datetime.now().isoformat()
                save_memory(memory)
                return val.get('answer')
            return str(val)
            
    return None

def add_answer_to_memory(question: str, answer: str, memory: dict):
    from datetime import datetime
    norm_q = normalize_question(question)
    category = infer_category(question)
    memory[norm_q] = {
        "answer": answer,
        "category": category,
        "confidence": 1.0,
        "source": "user_input",
        "last_used": datetime.now().isoformat()
    }
    save_memory(memory)


def get_or_prompt_skill_experience_answer(question: str, memory: dict) -> str:
    key = skill_experience_memory_key(question)
    if not key:
        return prompt_user_for_answer(question, memory)
    cached = get_answer_from_memory(key, memory)
    if cached:
        return cached
    return prompt_user_for_answer(key, memory)

def prompt_user_for_answer(question: str, memory: dict) -> str:
    from modules.helpers import print_lg, is_automation_context, safe_prompt
    print_lg(f"[MEMORY-MISS] Unknown question encountered: '{question}'. Pausing for user input.")
    
    # In automation/headless mode, skip GUI prompts entirely
    if is_automation_context():
        print_lg(f"[MEMORY-SKIP] Automation context detected. Cannot prompt for '{question}'. Skipping.")
        raise UserCancelledException(f"Unanswered question (automation mode): {question}")
    
    ans = safe_prompt(
        text=f"The bot doesn't know the answer to:\n\n'{question}'\n\nPlease enter the correct answer below. It will be saved permanently.\nIf you cancel, the application will be safely skipped.",
        title="Naukri_Guru - Unknown Question"
    )
    
    if ans is not None and str(ans).strip() != "":
        ans = str(ans).strip()
        add_answer_to_memory(question, ans, memory)
        print_lg(f"[MEMORY-LEARNED] Saved answer '{ans}' for question '{question}' under category '{infer_category(question)}'.")
        return ans
    print_lg(f"[MEMORY-CANCELED] User cancelled or provided empty input for '{question}'. Safely skipping.")
    raise UserCancelledException(f"Unanswered question: {question}")
