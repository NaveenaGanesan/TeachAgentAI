import imaplib
import smtplib
import email
import logging
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import decode_header
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
import threading

from config.settings import EMAIL_CONFIG, COURSE_INFO
from models.email_message import EmailMessage

logger = logging.getLogger(__name__)

class EmailService:
    """Service for handling email operations: retrieving and sending emails."""
    
    def __init__(self):
        self.imap_server = EMAIL_CONFIG["imap_server"]
        self.smtp_server = EMAIL_CONFIG["smtp_server"]
        self.imap_port = EMAIL_CONFIG["imap_port"]
        self.smtp_port = EMAIL_CONFIG["smtp_port"]
        self.username = EMAIL_CONFIG["username"]
        self.password = EMAIL_CONFIG["password"]
        self.check_frequency = EMAIL_CONFIG["check_frequency"]
        self.student_domain = EMAIL_CONFIG["student_domain"]
        
        self.imap_client = None
        self.smtp_client = None
        self.last_check_time = datetime.now() - timedelta(days=1)
        self.monitoring_thread = None
        self.stop_monitoring = threading.Event()
        self.new_email_callback = None
    
    def connect_imap(self) -> bool:
        """Connect to the IMAP server."""
        try:
            self.imap_client = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
            self.imap_client.login(self.username, self.password)
            logger.info(f"Connected to IMAP server {self.imap_server}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to IMAP server: {str(e)}")
            return False
    
    def connect_smtp(self) -> bool:
        """Connect to the SMTP server."""
        try:
            self.smtp_client = smtplib.SMTP(self.smtp_server, self.smtp_port)
            self.smtp_client.ehlo()
            self.smtp_client.starttls()
            self.smtp_client.ehlo()
            self.smtp_client.login(self.username, self.password)
            logger.info(f"Connected to SMTP server {self.smtp_server}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to SMTP server: {str(e)}")
            return False
    
    def disconnect(self):
        """Disconnect from both IMAP and SMTP servers."""
        if self.imap_client:
            try:
                self.imap_client.close()
                self.imap_client.logout()
                logger.info("Disconnected from IMAP server")
            except Exception as e:
                logger.error(f"Error disconnecting from IMAP server: {str(e)}")
            finally:
                self.imap_client = None
                
        if self.smtp_client:
            try:
                self.smtp_client.quit()
                logger.info("Disconnected from SMTP server")
            except Exception as e:
                logger.error(f"Error disconnecting from SMTP server: {str(e)}")
            finally:
                self.smtp_client = None
    
    def fetch_new_emails(self) -> List[EmailMessage]:
        """Fetch new emails from the inbox."""
        if not self.imap_client and not self.connect_imap():
            return []
        
        emails = []
        
        try:
            # Select the inbox
            self.imap_client.select("INBOX")
            
            # Create search criteria for new emails
            since_date = self.last_check_time.strftime("%d-%b-%Y")
            search_criteria = f'(SINCE "{since_date}")'
            
            # Search for matching emails
            status, messages = self.imap_client.search(None, search_criteria)
            
            if status != "OK":
                logger.warning(f"No messages found or search failed with status: {status}")
                return []
            
            # Convert message IDs to a list
            message_ids = messages[0].split()
            
            # Update the last check time
            self.last_check_time = datetime.now()
            
            # Process each message
            for msg_id in message_ids:
                email_obj = self._fetch_email_by_id(msg_id)
                if email_obj:
                    emails.append(email_obj)
            
            logger.info(f"Retrieved {len(emails)} new emails")
            
        except Exception as e:
            logger.error(f"Error fetching emails: {str(e)}")
            # Try to reconnect
            self.disconnect()
            self.connect_imap()
        
        return emails
    
    def _fetch_email_by_id(self, msg_id: bytes) -> Optional[EmailMessage]:
        """Fetch a specific email by ID."""
        try:
            status, msg_data = self.imap_client.fetch(msg_id, "(RFC822)")
            
            if status != "OK":
                logger.warning(f"Failed to fetch message {msg_id}")
                return None
            
            raw_email = msg_data[0][1]
            email_message = email.message_from_bytes(raw_email)
            
            # Extract basic headers
            subject = self._decode_header(email_message["Subject"])
            sender = self._decode_header(email_message["From"])
            recipient = self._decode_header(email_message["To"])
            date_str = self._decode_header(email_message["Date"])
            message_id = self._decode_header(email_message["Message-ID"])
            in_reply_to = self._decode_header(email_message.get("In-Reply-To"))
            references = self._decode_header(email_message.get("References"))
            
            # Parse CC recipients
            cc = []
            if email_message["Cc"]:
                cc_str = self._decode_header(email_message["Cc"])
                cc = [addr.strip() for addr in cc_str.split(",")]
            
            # Extract body
            body = self._get_email_body(email_message)
            
            # Extract attachments
            attachments = self._get_attachments(email_message)
            
            # Parse date
            try:
                date_obj = email.utils.parsedate_to_datetime(date_str)
            except:
                date_obj = datetime.now()
            
            # Create EmailMessage object
            return EmailMessage(
                message_id=message_id,
                subject=subject,
                sender=sender,
                recipient=recipient,
                body=body,
                date=date_obj,
                raw_content=raw_email.decode('utf-8', errors='replace'),
                cc=cc,
                attachments=attachments,
                references=references,
                in_reply_to=in_reply_to,
                thread_id=message_id  # Use message_id as thread_id for now
            )
            
        except Exception as e:
            logger.error(f"Error parsing email {msg_id}: {str(e)}")
            return None
    
    def _decode_header(self, header: Optional[str]) -> str:
        """Decode email header."""
        if header is None:
            return ""
            
        decoded_header = decode_header(header)[0][0]
        if isinstance(decoded_header, bytes):
            try:
                return decoded_header.decode()
            except:
                return decoded_header.decode("latin1")
        return decoded_header
    
    def _get_email_body(self, msg: email.message.Message) -> str:
        """Extract the email body from a message."""
        body = ""
        
        if msg.is_multipart():
            # Handle multipart messages
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                # Skip attachments
                if "attachment" in content_disposition:
                    continue
                
                # Get the body text (prefer plain text)
                if content_type == "text/plain":
                    try:
                        body = part.get_payload(decode=True).decode()
                        break
                    except:
                        pass
                elif content_type == "text/html" and not body:
                    try:
                        body = part.get_payload(decode=True).decode()
                    except:
                        pass
        else:
            # Handle non-multipart messages
            try:
                body = msg.get_payload(decode=True).decode()
            except:
                body = msg.get_payload()
        
        return body
    
    def _get_attachments(self, msg: email.message.Message) -> List[Dict[str, Any]]:
        """Extract attachments from an email message."""
        attachments = []
        
        if not msg.is_multipart():
            return attachments
        
        for part in msg.walk():
            content_disposition = str(part.get("Content-Disposition"))
            
            if "attachment" in content_disposition:
                filename = part.get_filename()
                if filename:
                    content_type = part.get_content_type()
                    payload = part.get_payload(decode=True)
                    
                    attachments.append({
                        "filename": filename,
                        "content_type": content_type,
                        "data": payload
                    })
        
        return attachments
    
    def send_email(self, to: str, subject: str, body: str, cc: List[str] = None, 
                  reply_to: str = None, attachments: List[Dict[str, Any]] = None) -> bool:
        """Send an email."""
        if not self.smtp_client and not self.connect_smtp():
            return False
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg["From"] = self.username
            msg["To"] = to
            msg["Subject"] = subject
            
            if cc:
                msg["Cc"] = ", ".join(cc)
                recipients = [to] + cc
            else:
                recipients = [to]
            
            if reply_to:
                msg["Reply-To"] = reply_to
            
            # Add personalized signature
            email_body = body
            if COURSE_INFO["email_signature"]:
                signature = COURSE_INFO["email_signature"].format(
                    ta_name=COURSE_INFO["ta_name"],
                    course_name=COURSE_INFO["name"]
                )
                email_body += signature
            
            msg.attach(MIMEText(email_body, "plain"))
            
            # Add attachments
            if attachments:
                for attachment in attachments:
                    part = MIMEText(attachment["data"])
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename= {attachment['filename']}",
                    )
                    msg.attach(part)
            
            # Send the email
            self.smtp_client.sendmail(self.username, recipients, msg.as_string())
            logger.info(f"Email sent to {to}")
            return True
        
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            # Try to reconnect
            try:
                self.disconnect()
                if self.connect_smtp():
                    # Try again
                    msg = MIMEMultipart()
                    msg["From"] = self.username
                    msg["To"] = to
                    msg["Subject"] = subject
                    
                    if cc:
                        msg["Cc"] = ", ".join(cc)
                        recipients = [to] + cc
                    else:
                        recipients = [to]
                    
                    if reply_to:
                        msg["Reply-To"] = reply_to
                    
                    # Add personalized signature
                    email_body = body
                    if COURSE_INFO["email_signature"]:
                        signature = COURSE_INFO["email_signature"].format(
                            ta_name=COURSE_INFO["ta_name"],
                            course_name=COURSE_INFO["name"]
                        )
                        email_body += signature
                    
                    msg.attach(MIMEText(email_body, "plain"))
                    
                    # Send the email
                    self.smtp_client.sendmail(self.username, recipients, msg.as_string())
                    logger.info(f"Email sent to {to} on second attempt")
                    return True
            except Exception as e2:
                logger.error(f"Error sending email on second attempt: {str(e2)}")
                return False
            
            return False
    
    def send_response(self, original_email: EmailMessage, response_text: str) -> bool:
        """Send a response to an email."""
        subject = "Re: " + original_email.subject if not original_email.subject.startswith("Re:") else original_email.subject
        
        # Format the response to include the original message
        full_response = response_text + "\n\n"
        full_response += "---------- Original Message ----------\n"
        full_response += f"From: {original_email.sender}\n"
        full_response += f"Date: {original_email.date}\n"
        full_response += f"Subject: {original_email.subject}\n\n"
        full_response += original_email.body
        
        return self.send_email(
            to=original_email.sender_email, 
            subject=subject, 
            body=full_response
        )
    
    def start_monitoring(self, callback):
        """
        Start monitoring for new emails in a background thread.
        
        Args:
            callback: Function to call when new emails are received
        """
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            logger.warning("Email monitoring is already running")
            return
        
        self.new_email_callback = callback
        self.stop_monitoring.clear()
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        logger.info("Started email monitoring thread")
    
    def stop_monitoring_emails(self):
        """Stop the email monitoring thread."""
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.stop_monitoring.set()
            self.monitoring_thread.join(timeout=10)
            logger.info("Stopped email monitoring thread")
    
    def _monitoring_loop(self):
        """Background thread function to check for new emails periodically."""
        while not self.stop_monitoring.is_set():
            try:
                new_emails = self.fetch_new_emails()
                if new_emails and self.new_email_callback:
                    self.new_email_callback(new_emails)
            except Exception as e:
                logger.error(f"Error in email monitoring loop: {str(e)}")
            
            # Sleep until next check
            time.sleep(self.check_frequency)