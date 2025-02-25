from typing import Dict, List, Any
import json
import os
import aiohttp
import logging
from langchain.prompts import PromptTemplate
from .base_agent import BaseAgent

class N8nAgent(BaseAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.n8n_webhook_url = os.getenv('N8N_WEBHOOK_URL')
        self.n8n_webhook_id = os.getenv('N8N_WEBHOOK_ID')
        self.n8n_cloud_url = os.getenv('N8N_CLOUD_URL')
        
        if not all([self.n8n_webhook_url, self.n8n_webhook_id, self.n8n_cloud_url]):
            raise ValueError("Missing required n8n environment variables")
        
    def get_prompt(self) -> PromptTemplate:
        return PromptTemplate(
            input_variables=["task", "workflow_context", "webhook_data"],
            template="""You are an n8n workflow orchestrator. Your task is to manage and execute n8n workflows.

Task: {task}

Workflow Context:
{workflow_context}

Webhook Data:
{webhook_data}

Please provide:
1. Workflow execution plan
2. Required webhook parameters
3. Expected workflow outcomes
4. Error handling considerations

Response format:
WORKFLOW: Name and purpose of the workflow
PARAMETERS: Required webhook parameters
EXECUTION: Steps to execute
VALIDATION: How to validate success

Response:"""
        )
    
    async def plan(self, task: str) -> List[str]:
        return [
            "1. Validate n8n connection and webhook configuration",
            "2. Prepare workflow parameters and payload",
            "3. Execute workflow through webhook",
            "4. Monitor execution and handle responses"
        ]
    
    async def execute(self, task: str) -> Dict[str, Any]:
        self._increment_step()  # Step 1
        
        # Validate connection
        await self._validate_n8n_connection()
        
        # Step 2: Prepare workflow context
        self._increment_step()
        workflow_context = {
            "webhook_url": self.n8n_webhook_url,
            "webhook_id": self.n8n_webhook_id,
            "cloud_url": self.n8n_cloud_url
        }
        
        # Generate webhook parameters
        chain_response = await self.chain.arun(
            task=task,
            workflow_context=json.dumps(workflow_context, indent=2),
            webhook_data="{}"  # Initial empty data
        )
        
        # Parse the response
        workflow_config = self._parse_workflow_response(chain_response)
        
        # Step 3: Execute workflow
        self._increment_step()
        execution_result = await self._execute_workflow(workflow_config)
        
        # Step 4: Monitor and return results
        self._increment_step()
        return {
            "task": task,
            "workflow_config": workflow_config,
            "execution_result": execution_result,
            "webhook_url": self.n8n_webhook_url
        }
    
    async def _validate_n8n_connection(self):
        """Validate n8n connection and webhook configuration"""
        async with aiohttp.ClientSession() as session:
            try:
                # Test n8n cloud connection
                async with session.get(f"{self.n8n_cloud_url}/healthz") as response:
                    if response.status != 200:
                        raise Exception(f"n8n health check failed: {response.status}")
                    
                logging.info("n8n connection validated successfully")
                
            except Exception as e:
                logging.error(f"n8n connection validation failed: {str(e)}")
                raise
    
    async def _execute_workflow(self, workflow_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute n8n workflow through webhook"""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-N8N-Webhook-ID": self.n8n_webhook_id
        }
        
        # Prepare payload from workflow configuration
        payload = {
            "workflow": workflow_config["workflow"],
            "parameters": workflow_config["parameters"],
            "execution": workflow_config["execution"]
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    self.n8n_webhook_url,
                    headers=headers,
                    json=payload
                ) as response:
                    if response.status >= 400:
                        error_text = await response.text()
                        raise Exception(f"Workflow execution failed: {error_text}")
                        
                    return await response.json()
                    
            except Exception as e:
                logging.error(f"Workflow execution error: {str(e)}")
                raise
    
    def _parse_workflow_response(self, response: str) -> Dict[str, Any]:
        """Parse the structured workflow response"""
        components = {}
        current_key = None
        current_value = []
        
        for line in response.split("\n"):
            line = line.strip()
            if not line:
                continue
                
            if line.startswith(("WORKFLOW:", "PARAMETERS:", "EXECUTION:", "VALIDATION:")):
                if current_key:
                    components[current_key] = "\n".join(current_value).strip()
                current_key = line.split(":")[0].lower()
                current_value = [line.split(":", 1)[1].strip()]
            else:
                if current_key:
                    current_value.append(line)
                    
        if current_key:
            components[current_key] = "\n".join(current_value).strip()
            
        return components 