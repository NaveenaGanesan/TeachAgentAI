import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Email configuration
EMAIL_CONFIG = {
    "imap_server": os.getenv("EMAIL_IMAP_SERVER", "imap.gmail.com"),
    "smtp_server": os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com"),
    "imap_port": int(os.getenv("EMAIL_IMAP_PORT", 993)),
    "smtp_port": int(os.getenv("EMAIL_SMTP_PORT", 587)),
    "username": os.getenv("EMAIL_USERNAME"),
    "password": os.getenv("EMAIL_PASSWORD"),
    "check_frequency": int(os.getenv("EMAIL_CHECK_FREQUENCY", 300)),  # in seconds
    "student_domain": os.getenv("STUDENT_EMAIL_DOMAIN", "university.edu")
}

# AI model configuration
AI_CONFIG = {
    "model_name": os.getenv("AI_MODEL_NAME", "gpt-4"),
    "api_key": os.getenv("OPENAI_API_KEY"),
    "max_tokens": int(os.getenv("MAX_TOKENS", 500)),
    "temperature": float(os.getenv("TEMPERATURE", 0.7)),
    "system_prompt_template": """
You are a helpful teaching assistant for {course_name}. 
You are responding to student emails on behalf of {ta_name}, the course TA.
Current date: {current_date}

COURSE INFORMATION:
{course_info}

STUDENT INFORMATION:
{student_info}

CONVERSATION HISTORY:
{conversation_history}

RESPONDING TO EMAIL:
Subject: {email_subject}
Content: {email_content}

Respond in a helpful, concise, and professional manner. If you don't know the answer or the question requires TA judgment, indicate that the message will be forwarded to the human TA.
"""
}

# Course information
COURSE_INFO = {
    "name": os.getenv("COURSE_NAME", "Computer Science 101"),
    "professor": os.getenv("PROFESSOR_NAME", "Dr. Smith"),
    "term": os.getenv("TERM", "Spring 2025"),
    "ta_name": os.getenv("TA_NAME", "Teaching Assistant"),
    "email_signature": os.getenv("EMAIL_SIGNATURE", 
        "\n\nBest regards,\n{ta_name}\nTeaching Assistant, {course_name}")
}

# Human oversight configuration
OVERSIGHT_CONFIG = {
    "confidence_threshold": float(os.getenv("CONFIDENCE_THRESHOLD", 0.7)),
    "require_approval": os.getenv("REQUIRE_APPROVAL", "False").lower() == "true",
    "approval_email": os.getenv("APPROVAL_EMAIL"),  # Where to send emails for approval
    "max_auto_emails_per_day": int(os.getenv("MAX_AUTO_EMAILS_PER_DAY", 50))
}

# Knowledge base configuration
KB_CONFIG = {
    "materials_path": os.getenv("MATERIALS_PATH", "data/course_materials"),
    "templates_path": os.getenv("TEMPLATES_PATH", "data/templates"),
    "kb_path": os.getenv("KB_PATH", "data/knowledge_base")
}