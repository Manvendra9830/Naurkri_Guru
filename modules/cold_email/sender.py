import os
import smtplib
from datetime import datetime
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from modules.helpers import print_lg
from modules.email.auth import load_email_credentials, EmailCredentials

@dataclass
class SendResult:
    success: bool
    error: str | None
    timestamp: str

def find_first_pdf(directory: str) -> str | None:
    if not os.path.exists(directory):
        return None
    try:
        for file in os.listdir(directory):
            if file.lower().endswith(".pdf"):
                return os.path.join(directory, file)
    except Exception as e:
        print_lg(f"Error searching directory {directory}: {e}")
    return None

def send_cold_email(
    recipient_email: str,
    content, # ColdEmailContent
    sender_credentials: EmailCredentials | None = None,
    resume_path: str | None = None,
    cover_letter_path: str | None = None,
) -> SendResult:
    """Sends a cold email to the recipient with resume and cover letter attachments using Gmail SMTP."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        # Load credentials if not provided
        if not sender_credentials:
            sender_credentials = load_email_credentials()
            
        if not sender_credentials.address or not sender_credentials.app_password:
            return SendResult(
                success=False,
                error="SMTP credentials are empty",
                timestamp=timestamp
            )
            
        # Initialize paths if not provided
        from config.settings import COLD_EMAIL_RESUME_DIR, COLD_EMAIL_COVER_LETTER_DIR
        if resume_path is None:
            resume_path = find_first_pdf(COLD_EMAIL_RESUME_DIR)
        if cover_letter_path is None:
            cover_letter_path = find_first_pdf(COLD_EMAIL_COVER_LETTER_DIR)
            
        # Create Message
        msg = MIMEMultipart("mixed")
        msg["From"] = sender_credentials.address
        msg["To"] = recipient_email
        msg["Subject"] = content.subject
        
        # Body section (alternative)
        msg_body = MIMEMultipart("alternative")
        
        # Plain text
        plain_text = content.body
        msg_body.attach(MIMEText(plain_text, "plain", "utf-8"))
        
        # HTML version
        html_text = f"""
        <html>
        <body>
            <div style="font-family: Arial, sans-serif; font-size: 14.5px; line-height: 1.6; color: #1f2937;">
                {content.body.replace(chr(10), "<br>")}
            </div>
        </body>
        </html>
        """
        msg_body.attach(MIMEText(html_text, "html", "utf-8"))
        msg.attach(msg_body)
        
        # Attach Resume
        if resume_path and os.path.exists(resume_path):
            try:
                with open(resume_path, "rb") as f:
                    part = MIMEBase("application", "pdf")
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                filename = os.path.basename(resume_path)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename= {filename}",
                )
                msg.attach(part)
                print_lg(f"Attached resume: {filename}")
            except Exception as e:
                print_lg(f"Failed to attach resume {resume_path}: {e}")
                
        # Attach Cover Letter
        if cover_letter_path and os.path.exists(cover_letter_path):
            try:
                with open(cover_letter_path, "rb") as f:
                    part = MIMEBase("application", "pdf")
                    part.set_payload(f.read())
                encoders.encode_base64(part)
                filename = os.path.basename(cover_letter_path)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename= {filename}",
                )
                msg.attach(part)
                print_lg(f"Attached cover letter: {filename}")
            except Exception as e:
                print_lg(f"Failed to attach cover letter {cover_letter_path}: {e}")
                
        # Connect & Send
        print_lg(f"Connecting to Gmail SMTP server for sending to {recipient_email}...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(sender_credentials.address, sender_credentials.app_password)
            server.sendmail(sender_credentials.address, recipient_email, msg.as_string())
            
        print_lg(f"Cold email sent successfully to {recipient_email}")
        return SendResult(success=True, error=None, timestamp=timestamp)
        
    except Exception as e:
        error_msg = f"SMTP send failed: {type(e).__name__}: {str(e)}"
        print_lg(error_msg)
        return SendResult(success=False, error=error_msg, timestamp=timestamp)
