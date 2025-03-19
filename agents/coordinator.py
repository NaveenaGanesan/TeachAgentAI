import logging
import threading
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

from services.email_service import EmailService
from services.nlp_service import NLPService
from agents.email_agent import EmailAgent
from knowledge.knowledge_base import KnowledgeBase
from models.email_message import EmailMessage
from models.student import Student
from config.settings import OVERSIGHT_CONFIG

logger = logging.getLogger(__name__)

class CoordinatorAgent:
    """
    Coordinator Agent that orchestrates the entire system.
    Routes tasks to appropriate specialized agents and maintains system state.
    """
    
    def __init__(self, email_service: EmailService, nlp_service: NLPService, 
                 knowledge_base: KnowledgeBase):
        self.email_service = email_service
        self.nlp_service = nlp_service
        self.knowledge_base = knowledge_base
        
        # Initialize specialized agents
        self.email_agent = EmailAgent(knowledge_base, nlp_service)
        
        # Initialize tracking variables
        self.active = False
        self.email_counter = 0
        self.max_emails_per_day = OVERSIGHT_CONFIG["max_auto_emails_per_day"]
        self.last_reset_date = datetime.now().date()
        self.pending_approvals = []
        self.students = {}  # Dictionary to store student information
        
        # Initialize threading locks
        self.counter_lock = threading.Lock()
    
    def start(self):
        """Start the coordinator agent and all services."""
        if self.active:
            logger.warning("Coordinator agent is already running")
            return
        
        logger.info("Starting coordinator agent")
        self.active = True
        
        # Start monitoring for new emails
        self.email_service.start_monitoring(self.handle_new_emails)
        
        # Start a background thread for daily counter reset
        self.counter_thread = threading.Thread(target=self._reset_counter_daily)
        self.counter_thread.daemon = True
        self.counter_thread.start()
        
        logger.info("Coordinator agent started successfully")
    
    def stop(self):
        """Stop the coordinator agent and all services."""
        if not self.active:
            return
        
        logger.info("Stopping coordinator agent")
        self.active = False
        
        # Stop email monitoring
        self.email_service.stop_monitoring_emails()
        
        # Disconnect from email servers
        self.email_service.disconnect()
        
        logger.info("Coordinator agent stopped")
    
    def handle_new_emails(self, emails: List[EmailMessage]):
        """
        Handle new incoming emails by routing them to the appropriate agent.
        
        Args:
            emails: List of new email messages
        """
        for email_msg in emails:
            try:
                # Check if this is a student email
                if not email_msg.is_student_email:
                    logger.info(f"Skipping non-student email from {email_msg.sender}")
                    continue
                
                logger.info(f"Processing email from {email_msg.sender_email}: {email_msg.subject}")
                
                # Get or create student record
                student = self._get_or_create_student(email_msg.sender_email, email_msg.sender_name)
                
                # Classify the email intent
                intent, confidence = self.nlp_service.classify_intent(email_msg.subject, email_msg.body)
                
                # Route the email based on intent
                if "assignment" in intent or "conceptual" in intent:
                    # Academic questions go to the email agent
                    self._handle_via_email_agent(email_msg, student, intent, confidence)
                    
                elif "grade" in intent:
                    # Grade inquiries might need human review
                    if confidence < OVERSIGHT_CONFIG["confidence_threshold"]:
                        self._queue_for_approval(email_msg, student, intent)
                    else:
                        self._handle_via_email_agent(email_msg, student, intent, confidence)
                        
                elif "administrative" in intent:
                    # Administrative queries handled by email agent
                    self._handle_via_email_agent(email_msg, student, intent, confidence)
                    
                elif "technical" in intent:
                    # Technical issues handled by email agent
                    self._handle_via_email_agent(email_msg, student, intent, confidence)
                    
                elif "personal" in intent:
                    # Personal circumstances usually need human review
                    self._queue_for_approval(email_msg, student, intent)
                    
                else:
                    # Default to email agent for other intents
                    self._handle_via_email_agent(email_msg, student, intent, confidence)
                
            except Exception as e:
                logger.error(f"Error processing email {email_msg.message_id}: {str(e)}")
    
    def _handle_via_email_agent(self, email_msg: EmailMessage, student: Student, 
                              intent: str, confidence: float):
        """
        Handle an email using the Email Response Agent.
        
        Args:
            email_msg: The email message to handle
            student: The student record
            intent: The classified intent
            confidence: The confidence score of the intent classification
        """
        # Check daily email limit
        with self.counter_lock:
            if self.email_counter >= self.max_emails_per_day:
                logger.warning("Daily email limit reached, queuing for approval")
                self._queue_for_approval(email_msg, student, intent)
                return
            
            # Check if human approval is required based on settings
            if OVERSIGHT_CONFIG["require_approval"]:
                self._queue_for_approval(email_msg, student, intent)
                return
            
            # Increment the counter
            self.email_counter += 1
        
        # Generate a response using the email agent
        response = self.email_agent.generate_response(email_msg, student, intent)
        
        # Send the response
        if response:
            success = self.email_service.send_response(email_msg, response)
            
            if success:
                logger.info(f"Sent response to {email_msg.sender_email}")
                
                # Update student conversation history
                student.update_conversation(email_msg, response, intent)
                
                # Update student record in knowledge base
                self.knowledge_base.update_student(student)
            else:
                logger.error(f"Failed to send response to {email_msg.sender_email}")
        else:
            logger.warning(f"No response generated for email from {email_msg.sender_email}")
    
    def _queue_for_approval(self, email_msg: EmailMessage, student: Student, intent: str):
        """
        Queue an email for human approval.
        
        Args:
            email_msg: The email message to queue
            student: The student record
            intent: The classified intent
        """
        # Generate a draft response
        draft_response = self.email_agent.generate_response(email_msg, student, intent)
        
        # Add to pending approvals queue
        approval_item = {
            "email": email_msg,
            "student": student,
            "intent": intent,
            "draft_response": draft_response,
            "timestamp": datetime.now()
        }
        
        self.pending_approvals.append(approval_item)
        
        # If there's an approval email configured, send the draft there
        if OVERSIGHT_CONFIG["approval_email"]:
            self._send_for_approval(approval_item)
        
        logger.info(f"Queued email from {email_msg.sender_email} for approval")
    
    def _send_for_approval(self, approval_item: Dict[str, Any]):
        """
        Send an email for approval to the designated approval email address.
        
        Args:
            approval_item: The approval item containing email and draft response
        """
        email_msg = approval_item["email"]
        draft_response = approval_item["draft_response"]
        intent = approval_item["intent"]
        
        # Create approval email content
        subject = f"APPROVAL NEEDED: Response to {email_msg.sender_name} - {intent}"
        
        body = f"The following student email needs your approval before sending a response:\n\n"
        body += f"FROM: {email_msg.sender}\n"
        body += f"SUBJECT: {email_msg.subject}\n"
        body += f"INTENT: {intent}\n\n"
        body += f"ORIGINAL MESSAGE:\n{email_msg.body}\n\n"
        body += f"DRAFT RESPONSE:\n{draft_response}\n\n"
        body += f"To approve, reply with 'APPROVE'. To modify, reply with 'REVISE:' followed by your revised response."
        
        # Send approval request
        self.email_service.send_email(
            to=OVERSIGHT_CONFIG["approval_email"],
            subject=subject,
            body=body
        )
    
    def approve_response(self, approval_id: int, revised_response: Optional[str] = None):
        """
        Approve a queued response.
        
        Args:
            approval_id: The index of the approval item in the queue
            revised_response: Optional revised response text
        
        Returns:
            bool: True if approved and sent successfully, False otherwise
        """
        if approval_id < 0 or approval_id >= len(self.pending_approvals):
            logger.error(f"Invalid approval ID: {approval_id}")
            return False
        
        approval_item = self.pending_approvals[approval_id]
        email_msg = approval_item["email"]
        student = approval_item["student"]
        intent = approval_item["intent"]
        
        # Use the revised response if provided, otherwise use the draft
        response = revised_response if revised_response else approval_item["draft_response"]
        
        # Send the response
        success = self.email_service.send_response(email_msg, response)
        
        if success:
            logger.info(f"Sent approved response to {email_msg.sender_email}")
            
            # Update student conversation history
            student.update_conversation(email_msg, response, intent)
            
            # Update student record in knowledge base
            self.knowledge_base.update_student(student)
            
            # Remove from pending approvals
            self.pending_approvals.pop(approval_id)
            
            return True
        else:
            logger.error(f"Failed to send approved response to {email_msg.sender_email}")
            return False
    
    def _get_or_create_student(self, email: str, name: str = "") -> Student:
        """
        Get or create a student record.
        
        Args:
            email: Student email address
            name: Student name (optional)
            
        Returns:
            Student: The student record
        """
        if email in self.students:
            return self.students[email]
        
        # Try to get from knowledge base
        student = self.knowledge_base.get_student(email)
        
        if not student:
            # Create new student record
            student = Student(email=email, name=name)
            self.knowledge_base.add_student(student)
        
        # Add to local cache
        self.students[email] = student
        
        return student
    
    def _reset_counter_daily(self):
        """Background thread function to reset the email counter daily."""
        while self.active:
            try:
                current_date = datetime.now().date()
                
                # Reset counter if it's a new day
                if current_date != self.last_reset_date:
                    with self.counter_lock:
                        self.email_counter = 0
                        self.last_reset_date = current_date
                        logger.info(f"Reset daily email counter for {current_date}")
            
            except Exception as e:
                logger.error(f"Error in counter reset thread: {str(e)}")
            
            # Sleep for a while (check every hour)
            time.sleep(3600)