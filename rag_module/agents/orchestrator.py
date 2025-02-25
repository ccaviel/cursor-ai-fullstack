from typing import Dict, List, Any, Type
import asyncio
import logging
from langchain.llms.base import BaseLLM
from .base_agent import BaseAgent
from .code_review_agent import CodeReviewAgent
from .rag_agent import RAGAgent
from .auto_agent import AutoAgent
from .n8n_agent import N8nAgent

class AgentOrchestrator:
    def __init__(self, llm: BaseLLM, verbose: bool = False):
        self.llm = llm
        self.verbose = verbose
        self.agents: Dict[str, BaseAgent] = {}
        
        # Register default agents
        self.register_agent("code_review", CodeReviewAgent)
        self.register_agent("rag", RAGAgent)
        self.register_agent("auto", AutoAgent)
        self.register_agent("n8n", N8nAgent)
        
    def register_agent(self, name: str, agent_class: Type[BaseAgent]):
        """Register a new agent type"""
        self.agents[name] = agent_class(
            name=name,
            llm=self.llm,
            verbose=self.verbose
        )
        if self.verbose:
            logging.info(f"Registered agent: {name}")
    
    async def run_agent(self, agent_name: str, task: str) -> Dict[str, Any]:
        """Run a specific agent on a task"""
        if agent_name not in self.agents:
            raise ValueError(f"Unknown agent: {agent_name}")
            
        agent = self.agents[agent_name]
        if self.verbose:
            logging.info(f"Running agent {agent_name} on task: {task}")
            
        return await agent.run(task)
    
    async def run_multiple_agents(
        self,
        tasks: Dict[str, str]
    ) -> Dict[str, Dict[str, Any]]:
        """Run multiple agents concurrently
        
        Args:
            tasks: Dict mapping agent names to their tasks
            
        Returns:
            Dict mapping agent names to their results
        """
        # Validate all agents exist
        unknown_agents = set(tasks.keys()) - set(self.agents.keys())
        if unknown_agents:
            raise ValueError(f"Unknown agents: {unknown_agents}")
        
        # Create tasks for each agent
        coroutines = [
            self.run_agent(agent_name, task)
            for agent_name, task in tasks.items()
        ]
        
        # Run all tasks concurrently
        results = await asyncio.gather(*coroutines, return_exceptions=True)
        
        # Process results
        return {
            agent_name: result if not isinstance(result, Exception) else {"error": str(result)}
            for agent_name, result in zip(tasks.keys(), results)
        }
    
    def get_available_agents(self) -> List[str]:
        """Get list of registered agent names"""
        return list(self.agents.keys())
        
    async def run_workflow(self, task: str) -> Dict[str, Any]:
        """Run a complete workflow using multiple agents
        
        This method orchestrates multiple agents to complete a complex task:
        1. Auto agent breaks down the task and creates a plan
        2. RAG agent provides relevant context for each step
        3. Code review agent analyzes any code changes
        4. n8n agent executes any required workflows
        """
        # First, use auto agent to break down the task
        auto_result = await self.run_agent("auto", task)
        plan = auto_result["plan"]
        
        workflow_results = []
        for step in plan:
            # Get context from RAG
            rag_result = await self.run_agent("rag", step)
            
            step_result = {
                "step": step,
                "context": rag_result
            }
            
            # Check if step needs code review
            if any(code_keyword in step.lower() for code_keyword in ["code", "function", "class", "implement"]):
                code_result = await self.run_agent("code_review", step)
                step_result["code_review"] = code_result
            
            # Check if step needs n8n workflow
            if any(workflow_keyword in step.lower() for workflow_keyword in ["workflow", "automation", "trigger", "webhook"]):
                workflow_result = await self.run_agent("n8n", step)
                step_result["workflow"] = workflow_result
            
            workflow_results.append(step_result)
        
        return {
            "task": task,
            "plan": plan,
            "workflow_results": workflow_results,
            "thought_process": auto_result.get("thought_process", [])
        } 