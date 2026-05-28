######################################################  NAUKRI_GURU — APPLICATION INPUTS  ######################################################
# Naukri_Guru: AI-Powered Job Automation Platform
# Developer: Manvendra Singh | IIIT Raichur
######################################################################################################################


# >>>>>>>>>>> Easy Apply Questions & Inputs <<<<<<<<<<<

# Give an relative path of your default resume to be uploaded. If file in not found, will continue using your previously uploaded resume in LinkedIn.
default_resume_path = "all resumes\\Manvendra_Resume.pdf"      # (In Development)

# What do you want to answer for questions that ask about years of experience you have, this is different from current_experience? 
years_of_experience = "0"          # A number in quotes Eg: "0","1","2","3","4", etc.
months_of_experience = "8"

# Do you need visa sponsorship now or in future?
require_visa = "No"               # "Yes" or "No"

# What is the link to your portfolio website, leave it empty as "", if you want to leave this question unanswered
website = "https://my-portfolio-puce-gamma-77.vercel.app/"                        # "www.example.bio" or "" and so on....

# Please provide the link to your LinkedIn profile.
linkedIn = "https://www.linkedin.com/in/manvendra-singh-837874290"       # "https://www.linkedin.com/in/example" or "" and so on...

# Please provide the link to your Github profile.
github = "https://github.com/manvendrasingh"       # "https://github.com/example" or "" and so on...

# What is the status of your citizenship? # If left empty as "", tool will not answer the question. However, note that some companies make it compulsory to be answered
# Valid options are: "U.S. Citizen/Permanent Resident", "Non-citizen allowed to work for any employer", "Non-citizen allowed to work for current employer", "Non-citizen seeking work authorization", "Canadian Citizen/Permanent Resident" or "Other"
us_citizenship = "Other"



## SOME ANNOYING QUESTIONS BY COMPANIES 🫠 ##

# What to enter in your desired salary question (American and European), What is your expected CTC (South Asian and others)?, only enter in numbers as some companies only allow numbers,
desired_salary = 900000          # 80000, 90000, 100000 or 120000 and so on... Do NOT use quotes
'''
Note: If question has the word "lakhs" in it (Example: What is your expected CTC in lakhs), 
then it will add '.' before last 5 digits and answer. Examples: 
* 2400000 will be answered as "24.00"
* 850000 will be answered as "8.50"
And if asked in months, then it will divide by 12 and answer. Examples:
* 2400000 will be answered as "200000"
* 850000 will be answered as "70833"
'''

# What is your current CTC? Some companies make it compulsory to be answered in numbers...
current_ctc = 360000            # 800000, 900000, 1000000 or 1200000 and so on... Do NOT use quotes
'''
Note: If question has the word "lakhs" in it (Example: What is your current CTC in lakhs), 
then it will add '.' before last 5 digits and answer. Examples: 
* 2400000 will be answered as "24.00"
* 850000 will be answered as "8.50"
# And if asked in months, then it will divide by 12 and answer. Examples:
# * 2400000 will be answered as "200000"
# * 850000 will be answered as "70833"
'''

# (In Development) # Currency of salaries you mentioned. Companies that allow string inputs will add this tag to the end of numbers. Eg: 
# currency = "INR"                 # "USD", "INR", "EUR", etc.

# What is your notice period in days?
notice_period = 15                  # Any number >= 0 without quotes. Eg: 0, 7, 15, 30, 45, etc.
'''
Note: If question has 'month' or 'week' in it (Example: What is your notice period in months), 
then it will divide by 30 or 7 and answer respectively. Examples:
* For notice_period = 66:
  - "66" OR "2" if asked in months OR "9" if asked in weeks
* For notice_period = 15:"
  - "15" OR "0" if asked in months OR "2" if asked in weeks
* For notice_period = 0:
  - "0" OR "0" if asked in months OR "0" if asked in weeks
'''

# Your LinkedIn headline in quotes Eg: "Software Engineer @ Google, Masters in Computer Science", "Recent Grad Student @ MIT, Computer Science"
linkedin_headline = "AI/ML Enginree with Bachelors in Computer Science and 1 years of experience" # "Headline" or "" to leave this question unanswered

# Your summary in quotes, use \n to add line breaks if using single quotes "Summary".You can skip \n if using triple quotes """Summary"""
linkedin_summary = """
AI/ML Enginree with hands-on experience building LLM-based systems, scalable backend pipelines, and intelligent applications.

Currently working as an AI Intern at Darwix AI, developing RAG-based systems, automation workflows, and agent-driven solutions.

Experienced in machine learning, deep learning, and full-stack development with a strong focus on real-world problem solving and system design.
"""

'''
Note: If left empty as "", the tool will not answer the question. However, note that some companies make it compulsory to be answered. Use \n to add line breaks.
''' 

# Your cover letter in quotes, use \n to add line breaks if using single quotes "Cover Letter".You can skip \n if using triple quotes """Cover Letter""" (This question makes sense though)
cover_letter = """
Manvendra Singh
manvendra9830@gmail.com | +91-9662789830

Dear Hiring Manager,

I am a B.Tech Computer Science student at IIIT Raichur (2026) with hands-on experience in
building real-world AI/ML systems, particularly in LLM-based applications, Retrieval-Augmented
Generation (RAG), and scalable ML pipelines. Currently, as an AI Intern at Darwix AI, I am
developing LLM-driven applications and automation workflows using AI agents, focusing on
integrating embeddings, vector search, and prompt engineering for production-ready systems.

Previously, at IIT Madras (WSDSAI), I built a scalable Visual Place Recognition pipeline using deep
learning and FAISS for efficient large-scale retrieval, along with optimization techniques like pruning
and quantization. My projects further demonstrate strong practical exposure—developing an AI
agent system (Empathy Engine) using RAG, building LLM-based persona generation systems, and
applying LSTM models for time-series forecasting in environmental analysis.

My core strengths include Python, PyTorch, ML system design, vector search, and end-to-end
pipeline development. I am particularly interested in building scalable AI systems that bridge
research and real-world deployment. I am eager to contribute to impactful AI/ML projects while
continuing to grow as an engineer.

Sincerely,
Manvendra Singh
"""
##> ------ Dheeraj Deshwal : dheeraj9811 Email:dheeraj20194@iiitd.ac.in/dheerajdeshwal9811@gmail.com - Feature ------

# Your user_information_all letter in quotes, use \n to add line breaks if using single quotes "user_information_all".You can skip \n if using triple quotes """user_information_all""" (This question makes sense though)
# We use this to pass to AI to generate answer from information , Assuing Information contians eg: resume  all the information like name, experience, skills, Country, any illness etc. 
user_information_all ="""
Manvendra Singh
Email: manvendra9830@gmail.com | Phone: +91 9662789830 | Portfolio: https://my-portfolio-puce-gamma-77.vercel.app/
GitHub: github.com/Manvendra9830 | LinkedIn: linkedin.com/in/manvendra-singh-837874290/

Education
Indian Institute of Information Technology Raichur - B.Tech in CSE, CGPA: 8.41/10 2022 - 2026

Skills and Tools
Programming & Frameworks: Python, C++, JavaScript, Flask, Django, React.js
Machine Learning & Deep Learning: PyTorch, TensorFlow
NLP & LLMs: Transformers, Embeddings, Prompt Engineering, RAG, N8N, LangChain, LLM Application Development
ML Engineering & MLOps: Data Pipelines, FAISS (Vector Search), Model Deployment (APIs)
Data & Visualization: Pandas, NumPy, Scikit-learn, Matplotlib, Seaborn
Tools & Platforms: Git, Docker, Linux, Jupyter Notebook, VS Code, Postman

Work Experience
AI Intern (Darwix AI, Mar 2026 - Present): Developing LLM-based applications using RAG and vector search.
Research Intern (IIT Madras, May 2025 - Nov 2025): Designed visual place recognition pipeline and FAISS search.

Projects
Empathy Engine (AI Agent System, Mar 2026): Built AI agent system using RAG.
Visual Place Recognition Pipeline (May 2025): Built image retrieval pipeline.
"""
##<
'''
Note: If left empty as "", the tool will not answer the question. However, note that some companies make it compulsory to be answered. Use \n to add line breaks.
''' 

# Name of your most recent employer
recent_employer = "Darwix AI" # "", "Lala Company", "Google", "Snowflake", "Databricks"

# Example question: "On a scale of 1-10 how much experience do you have building web or mobile applications? 1 being very little or only in school, 10 being that you have built and launched applications to real users"
confidence_level = "8"             # Any number between "1" to "10" including 1 and 10, put it in quotes ""
##



# >>>>>>>>>>> RELATED SETTINGS <<<<<<<<<<<

## Allow Manual Inputs
# Should the tool pause before every submit application during easy apply to let you check the information?
pause_before_submit = True         # True or False, Note: True or False are case-sensitive
'''
Note: Will be treated as False if `run_in_background = True`
'''

# Should the tool pause if it needs help in answering questions during easy apply?
# Note: If set as False will answer randomly...
pause_at_failed_question = True    # True or False, Note: True or False are case-sensitive
'''
Note: Will be treated as False if `run_in_background = True`
'''
##

# Do you want to overwrite previous answers?
overwrite_previous_answers = False # True or False, Note: True or False are case-sensitive



# End of configuration