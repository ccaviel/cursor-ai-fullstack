import asyncio
import logging
import os
from dotenv import load_dotenv
from agents.orchestrator import AgentOrchestrator
from main import get_llm  # Import our existing LLM configuration

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Load environment variables
load_dotenv()

async def main():
    # Initialize LLM using our existing configuration
    llm = get_llm()
    
    # Create orchestrator
    orchestrator = AgentOrchestrator(llm=llm, verbose=True)
    
    # Example complex task that includes n8n workflow
    task = """Create a workflow that:
    1. Monitors our GitHub repository for new pull requests
    2. Uses RAG to analyze the changes and provide context
    3. Triggers a code review using CodeRabbit
    4. Posts the combined analysis as a PR comment
    """
    
    # Run the complete workflow
    logging.info("Running complete workflow...")
    workflow_result = await orchestrator.run_workflow(task)
    
    logging.info("\nWorkflow Results:")
    logging.info("=================")
    logging.info(f"Task: {workflow_result['task']}")
    
    logging.info("\nPlan:")
    for i, step in enumerate(workflow_result['plan'], 1):
        logging.info(f"{i}. {step}")
    
    logging.info("\nStep Results:")
    for i, result in enumerate(workflow_result['workflow_results'], 1):
        logging.info(f"\nStep {i}: {result['step']}")
        
        if 'code_review' in result:
            logging.info("\nCode Review Results:")
            logging.info(result['code_review'])
            
        if 'workflow' in result:
            logging.info("\nWorkflow Results:")
            logging.info(f"Workflow Config: {result['workflow']['workflow_config']}")
            logging.info(f"Execution Result: {result['workflow']['execution_result']}")
            
        logging.info("\nContext from RAG:")
        logging.info(result['context']['response'])
    
    logging.info("\nThought Process:")
    for thought in workflow_result['thought_process']:
        logging.info(f"\n{thought['step']}:")
        logging.info(thought['details'])

if __name__ == "__main__":
    asyncio.run(main()) 