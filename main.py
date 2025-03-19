import logging
from agents.coordinator import CoordinatorAgent
from services.email_service import EmailService
from services.nlp_service import NLPService
from knowledge.knowledge_base import KnowledgeBase

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main():
    # Initialize services and knowledge base
    email_service = EmailService()
    nlp_service = NLPService()
    knowledge_base = KnowledgeBase()
    
    # Initialize coordinator agent
    coordinator = CoordinatorAgent(
        email_service=email_service,
        nlp_service=nlp_service,
        knowledge_base=knowledge_base
    )
    
    # Start the system
    coordinator.start()
    
    try:
        # Keep the main thread running
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # Graceful shutdown
        coordinator.stop()
        print("System shutdown")

if __name__ == "__main__":
    main()