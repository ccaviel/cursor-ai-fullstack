from typing import Dict, List, Any
import json
import logging
from langchain.prompts import PromptTemplate
from .base_agent import BaseAgent

class AutoAgent(BaseAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.task_history = []
        self.thought_process = []
        
    def get_prompt(self) -> PromptTemplate:
        return PromptTemplate(
            input_variables=["task", "thought_process", "task_history"],
            template="""You are an autonomous agent capable of breaking down complex tasks and executing them step by step.
Your goal is to complete tasks by thinking carefully about each step and its consequences.

Task: {task}

Previous Steps and Outcomes:
{task_history}

Current Thought Process:
{thought_process}

Please:
1. Analyze the current situation
2. Consider possible actions and their outcomes
3. Choose the most effective next step
4. Explain your reasoning

Response format:
THOUGHT: Your analysis of the situation
REASONING: Why you chose this approach
ACTION: The specific action to take
NEXT: What you expect to do after this step

Response:"""
        )
    
    async def plan(self, task: str) -> List[str]:
        # Generate initial plan
        prompt = f"""Break down this task into logical steps:
        Task: {task}
        
        Consider:
        1. Dependencies between steps
        2. Potential failure points
        3. Required resources
        4. Success criteria
        
        Steps:"""
        
        response = await self.llm.agenerate([prompt])
        steps = [step.strip() for step in response.generations[0].text.split("\n") if step.strip()]
        
        return steps
    
    async def execute(self, task: str) -> Dict[str, Any]:
        self._increment_step()  # Step 1
        
        # Get initial plan
        plan = await self.plan(task)
        self.thought_process.append({
            "step": "Planning",
            "details": plan
        })
        
        results = []
        for step in plan:
            self._increment_step()
            
            # Generate thought process for this step
            chain_response = await self.chain.arun(
                task=step,
                thought_process=json.dumps(self.thought_process, indent=2),
                task_history=json.dumps(self.task_history, indent=2)
            )
            
            # Parse response
            thought_components = self._parse_thought_response(chain_response)
            
            # Record the step
            self.task_history.append({
                "step": step,
                "thought": thought_components,
                "status": "completed"
            })
            
            # Add to results
            results.append({
                "step": step,
                "thought_process": thought_components,
                "outcome": "Success"  # In a real system, we'd verify the outcome
            })
            
            self.thought_process.append({
                "step": "Execution",
                "details": thought_components
            })
        
        return {
            "task": task,
            "plan": plan,
            "results": results,
            "thought_process": self.thought_process,
            "task_history": self.task_history
        }
    
    def _parse_thought_response(self, response: str) -> Dict[str, str]:
        """Parse the structured thought response"""
        components = {}
        current_key = None
        current_value = []
        
        for line in response.split("\n"):
            line = line.strip()
            if not line:
                continue
                
            if line.startswith(("THOUGHT:", "REASONING:", "ACTION:", "NEXT:")):
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