from typing import Dict, List, Any
import aiohttp
import json
import os
from langchain.prompts import PromptTemplate
from .base_agent import BaseAgent

class CodeReviewAgent(BaseAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.coderabbit_api_key = os.getenv("CODERABBIT_API_KEY")
        self.coderabbit_url = os.getenv("CODERABBIT_URL", "https://api.coderabbit.ai/v1")
        
    def get_prompt(self) -> PromptTemplate:
        return PromptTemplate(
            input_variables=["task", "code_context"],
            template="""You are a code review expert. Your task is to review code and provide detailed feedback.
            
Task: {task}

Code Context:
{code_context}

Please analyze the code and provide:
1. Overall assessment
2. Potential issues or bugs
3. Suggestions for improvement
4. Best practices that should be followed

Response:"""
        )
    
    async def plan(self, task: str) -> List[str]:
        return [
            "1. Extract code context and metadata",
            "2. Send code to CodeRabbit for analysis",
            "3. Process CodeRabbit feedback",
            "4. Generate comprehensive review"
        ]
    
    async def execute(self, task: str) -> Dict[str, Any]:
        self._increment_step()  # Step 1
        
        # Extract code context from task
        # This would typically come from a PR or specific file
        code_context = task  # For now, assume task contains the code
        
        # Step 2: Send to CodeRabbit
        self._increment_step()
        coderabbit_analysis = await self._analyze_with_coderabbit(code_context)
        
        # Step 3: Process feedback
        self._increment_step()
        chain_response = await self.chain.arun(
            task=task,
            code_context=json.dumps(coderabbit_analysis, indent=2)
        )
        
        # Step 4: Return results
        self._increment_step()
        return {
            "coderabbit_analysis": coderabbit_analysis,
            "review_summary": chain_response
        }
    
    async def _analyze_with_coderabbit(self, code: str) -> Dict[str, Any]:
        """Send code to CodeRabbit for analysis"""
        headers = {
            "Authorization": f"Bearer {self.coderabbit_api_key}",
            "Content-Type": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.coderabbit_url}/analyze",
                headers=headers,
                json={"code": code}
            ) as response:
                if response.status != 200:
                    raise Exception(f"CodeRabbit API error: {await response.text()}")
                return await response.json() 