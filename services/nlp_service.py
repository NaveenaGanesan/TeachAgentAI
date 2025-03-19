import logging
import json
from typing import Dict, List, Tuple, Any, Optional
import anthropic

from config.settings import AI_CONFIG

logger = logging.getLogger(__name__)

class NLPService:
    """Service for natural language processing tasks like intent classification using Claude API."""
    
    def __init__(self):
        self.api_key = AI_CONFIG.get("anthropic_api_key")
        self.model = AI_CONFIG.get("claude_model", "claude-3-sonnet-20240229")
        self.client = anthropic.Anthropic(api_key=self.api_key)
        
        # Define intent categories and examples
        self.intents = {
            "assignment_question": [
                "When is assignment 3 due?",
                "Can you explain problem 2 in homework 4?",
                "I'm having trouble with the last part of the lab.",
                "What are the requirements for the final project?",
                "Is it okay if I submit my assignment late?"
            ],
            "grade_inquiry": [
                "Why did I lose points on question 3?",
                "I think there's a mistake in my midterm grade.",
                "Can you explain the grading for the last assignment?",
                "When will our exam grades be posted?",
                "How is the final grade calculated?"
            ],
            "conceptual_question": [
                "Can you explain how recursion works?",
                "I'm confused about the difference between arrays and linked lists.",
                "What's the time complexity of quicksort?",
                "How does inheritance work in object-oriented programming?",
                "Could you elaborate on the concept discussed in lecture 5?"
            ],
            "administrative": [
                "When are your office hours?",
                "Can I schedule a meeting to discuss my progress?",
                "Will class be canceled next Monday?",
                "Where can I find the syllabus?",
                "How do I join the course Discord?"
            ],
            "technical_issue": [
                "The course website isn't loading for me.",
                "I can't submit my assignment through the portal.",
                "The autograder is giving me an error.",
                "My code works locally but fails on the submission system.",
                "I'm having trouble accessing the lecture videos."
            ],
            "personal_circumstance": [
                "I have a medical appointment during the next exam.",
                "I've been sick and couldn't complete the assignment.",
                "Can I get an extension due to family emergency?",
                "I need accommodations for my disability.",
                "I'll be representing the university at a conference next week."
            ],
            "other": [
                "Just wanted to say thanks for your help!",
                "Could you forward this to the professor?",
                "I'm interested in research opportunities in this field.",
                "Can you recommend resources for learning more about this topic?",
                "I noticed a typo in the lecture slides."
            ]
        }
    
    def classify_intent(self, email_subject: str, email_body: str) -> Tuple[str, float]:
        """
        Classify the intent of an email based on subject and body using Claude.
        
        Args:
            email_subject: The subject line of the email
            email_body: The body text of the email
            
        Returns:
            Tuple containing (intent_category, confidence_score)
        """
        try:
            # Prepare the prompt for classification
            prompt = self._create_classification_prompt(email_subject, email_body)
            
            # Call the Claude API for classification
            response = self.client.messages.create(
                model=self.model,
                max_tokens=150,
                temperature=0.2,  # Low temperature for consistent classification
                system="You are an expert teaching assistant helping classify student emails.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Extract the response
            result_text = response.content[0].text
            
            # Parse the result
            intent, confidence = self._parse_classification_result(result_text)
            
            logger.info(f"Classified email intent as '{intent}' with confidence {confidence}")
            return intent, confidence
            
        except Exception as e:
            logger.error(f"Error classifying email intent with Claude: {str(e)}")
            return "other", 0.0
    
    def _create_classification_prompt(self, email_subject: str, email_body: str) -> str:
        """Create a prompt for the classification model."""
        # Create examples section
        examples = ""
        for intent, example_list in self.intents.items():
            for example in example_list[:2]:  # Use just a couple examples per category
                examples += f"Example: \"{example}\"\nIntent: {intent}\n\n"
        
        # Create the full prompt
        prompt = f"""Classify the following student email into exactly one of these categories:
- assignment_question: Questions about homework, projects, or assignments
- grade_inquiry: Questions about grades, scoring, or feedback
- conceptual_question: Questions about course concepts or material
- administrative: Questions about course logistics, scheduling, or policies
- technical_issue: Problems with course technology or systems
- personal_circumstance: Student sharing personal situations that affect coursework
- other: Anything that doesn't fit the above categories

Here are some examples of classifications:

{examples}

Now classify this email:
Subject: {email_subject}
Body:
{email_body}

Return your answer in this exact format:
Intent: [category]
Confidence: [decimal between 0 and 1]

The confidence should reflect how certain you are that this is the correct classification.
"""
        return prompt
    
    def _parse_classification_result(self, result_text: str) -> Tuple[str, float]:
        """
        Parse the classification result from Claude.
        
        Args:
            result_text: The text response from Claude
            
        Returns:
            Tuple of (intent, confidence)
        """
        intent = "other"
        confidence = 0.0
        
        try:
            # Extract intent
            if "Intent:" in result_text:
                intent_line = [line for line in result_text.split('\n') if "Intent:" in line][0]
                intent = intent_line.split("Intent:")[1].strip().lower()
            
            # Extract confidence
            if "Confidence:" in result_text:
                confidence_line = [line for line in result_text.split('\n') if "Confidence:" in line][0]
                confidence_str = confidence_line.split("Confidence:")[1].strip()
                confidence = float(confidence_str)
            
            # Validate intent
            if intent not in self.intents:
                logger.warning(f"Unrecognized intent '{intent}', defaulting to 'other'")
                intent = "other"
                
            # Validate confidence
            if not (0 <= confidence <= 1):
                logger.warning(f"Invalid confidence value {confidence}, clamping to range [0,1]")
                confidence = max(0, min(confidence, 1))
                
        except Exception as e:
            logger.error(f"Error parsing classification result: {str(e)}")
            logger.error(f"Result text was: {result_text}")
        
        return intent, confidence
    
    def generate_email_response(self, email_content: str, student_info: Dict[str, Any], 
                               course_info: Dict[str, Any], intent: str) -> str:
        """
        Generate an email response using Claude.
        
        Args:
            email_content: The content of the email to respond to
            student_info: Information about the student
            course_info: Information about the course
            intent: The classified intent of the email
            
        Returns:
            str: The generated response
        """
        try:
            # Create a context for Claude based on the model context protocol
            context = self._build_response_context(email_content, student_info, course_info, intent)
            
            # Call the Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1000,
                temperature=0.7,
                system=context["system_prompt"],
                messages=[
                    {"role": "user", "content": context["user_prompt"]}
                ]
            )
            
            # Return the generated response
            return response.content[0].text.strip()
            
        except Exception as e:
            logger.error(f"Error generating response with Claude: {str(e)}")
            return "I apologize, but I'm unable to provide a response at this time. Your message has been forwarded to the TA for review."
    
    def _build_response_context(self, email_content: str, student_info: Dict[str, Any],
                              course_info: Dict[str, Any], intent: str) -> Dict[str, str]:
        """
        Build the context for the response generation using the model context protocol.
        
        Args:
            email_content: The content of the email to respond to
            student_info: Information about the student
            course_info: Information about the course
            intent: The classified intent of the email
            
        Returns:
            Dict with system_prompt and user_prompt
        """
        # Format student conversation history if available
        conversation_history = ""
        if "conversation_history" in student_info and student_info["conversation_history"]:
            for i, conv in enumerate(student_info["conversation_history"][-3:]):  # Last 3 conversations
                conversation_history += f"Conversation {i+1}:\n"
                conversation_history += f"Student: {conv.get('message', {}).get('body', 'No message')}\n"
                conversation_history += f"TA: {conv.get('response', 'No response')}\n\n"
        
        # Create system prompt using the model context protocol
        system_prompt = f"""You are a helpful teaching assistant for {course_info.get('name', 'the course')}.
You are responding to student emails on behalf of {course_info.get('ta_name', 'the TA')}.

GUIDELINES:
- Be professional but friendly
- Be concise but thorough
- Provide clear, accurate information
- If you're unsure about something, acknowledge it and offer to find out
- For complex or sensitive issues, suggest meeting during office hours
- Address the student by name when possible
- For assignment-specific questions, refer to course materials and guidelines
- Don't make promises on behalf of the professor
- Don't share one student's information with another

COURSE INFORMATION:
Course: {course_info.get('name', 'N/A')}
Professor: {course_info.get('professor', 'N/A')}
Term: {course_info.get('term', 'N/A')}
"""

        # Add any course policies or resources if available
        if "policies" in course_info:
            system_prompt += "\nCOURSE POLICIES:\n"
            for policy_name, policy_text in course_info["policies"].items():
                system_prompt += f"- {policy_name}: {policy_text}\n"
        
        if "resources" in course_info:
            system_prompt += "\nCOURSE RESOURCES:\n"
            for resource_name, resource_link in course_info["resources"].items():
                system_prompt += f"- {resource_name}: {resource_link}\n"
        
        # Create user prompt with the specific email content
        user_prompt = f"""I'm responding to a student email with the intent classified as: {intent}

STUDENT INFORMATION:
Name: {student_info.get('name', 'Student')}
Email: {student_info.get('email', 'N/A')}

PREVIOUS CONVERSATION HISTORY:
{conversation_history if conversation_history else "No previous conversations."}

EMAIL CONTENT:
{email_content}

Please draft a helpful, concise response that addresses the student's concerns. 
Focus on being accurate, supportive, and directing the student to resources when appropriate.
"""
    
        return {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt
        }