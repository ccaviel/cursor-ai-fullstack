from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import logging
from langchain.schema import BaseMemory
from langchain.memory import ConversationBufferMemory
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

class BaseAgent(ABC):
    def __init__(
        self,
        name: str,
        llm: Any,
        memory: Optional[BaseMemory] = None,
        max_steps: int = 10,
        verbose: bool = False
    ):
        self.name = name
        self.llm = llm
        self.memory = memory or ConversationBufferMemory()
        self.max_steps = max_steps
        self.verbose = verbose
        self.step_count = 0
        
        # Initialize chain with base prompt
        self.chain = LLMChain(
            llm=self.llm,
            prompt=self.get_prompt(),
            memory=self.memory,
            verbose=verbose
        )
    
    @abstractmethod
    def get_prompt(self) -> PromptTemplate:
        """Return the prompt template for this agent"""
        pass
    
    @abstractmethod
    async def plan(self, task: str) -> List[str]:
        """Create a plan to accomplish the task"""
        pass
    
    @abstractmethod
    async def execute(self, task: str) -> Dict[str, Any]:
        """Execute the task and return results"""
        pass
    
    async def run(self, task: str) -> Dict[str, Any]:
        """Main entry point to run the agent on a task"""
        try:
            # Create plan
            plan = await self.plan(task)
            if self.verbose:
                logging.info(f"Agent {self.name} created plan: {plan}")
            
            # Execute plan
            self.step_count = 0
            results = await self.execute(task)
            
            return {
                "agent": self.name,
                "task": task,
                "plan": plan,
                "results": results,
                "steps_taken": self.step_count
            }
            
        except Exception as e:
            logging.error(f"Error in agent {self.name}: {str(e)}")
            return {
                "agent": self.name,
                "task": task,
                "error": str(e),
                "steps_taken": self.step_count
            }
    
    def _increment_step(self):
        """Increment step counter and check limits"""
        self.step_count += 1
        if self.step_count > self.max_steps:
            raise Exception(f"Agent {self.name} exceeded maximum steps ({self.max_steps})") 