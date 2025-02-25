from typing import Dict, List, Any
import json
from langchain.prompts import PromptTemplate
from .base_agent import BaseAgent
from ..main import build_vector_store, build_llama_index

class RAGAgent(BaseAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vector_store = None
        self.llama_index = None
        
    def get_prompt(self) -> PromptTemplate:
        return PromptTemplate(
            input_variables=["task", "context", "query"],
            template="""You are an AI assistant powered by RAG (Retrieval Augmented Generation). 
Your task is to provide accurate answers based on the retrieved context.

Task: {task}

Retrieved Context:
{context}

Query: {query}

Please provide:
1. A direct answer to the query
2. Supporting evidence from the context
3. Any relevant code examples or documentation references
4. Suggestions for follow-up queries

Response:"""
        )
    
    async def plan(self, task: str) -> List[str]:
        return [
            "1. Initialize vector stores and indices",
            "2. Process query and retrieve relevant context",
            "3. Generate comprehensive response",
            "4. Cache results for future use"
        ]
    
    async def execute(self, task: str) -> Dict[str, Any]:
        self._increment_step()  # Step 1
        
        # Initialize stores if not already done
        if not self.vector_store:
            self.vector_store = await build_vector_store()
        if not self.llama_index:
            self.llama_index = await build_llama_index()
        
        # Step 2: Retrieve context
        self._increment_step()
        vector_results = await self._get_vector_results(task)
        index_results = await self._get_index_results(task)
        
        combined_context = self._merge_results(vector_results, index_results)
        
        # Step 3: Generate response
        self._increment_step()
        chain_response = await self.chain.arun(
            task=task,
            context=json.dumps(combined_context, indent=2),
            query=task
        )
        
        # Step 4: Return results
        self._increment_step()
        return {
            "query": task,
            "context": combined_context,
            "response": chain_response,
            "sources": {
                "vector_store": [str(doc) for doc in vector_results],
                "llama_index": [str(doc) for doc in index_results]
            }
        }
    
    async def _get_vector_results(self, query: str) -> List[Any]:
        """Get results from vector store"""
        retriever = self.vector_store.as_retriever(search_kwargs={"k": 3})
        docs = await retriever.aget_relevant_documents(query)
        return docs
    
    async def _get_index_results(self, query: str) -> List[Any]:
        """Get results from LlamaIndex"""
        query_engine = self.llama_index.as_query_engine()
        response = await query_engine.aquery(query)
        return response.source_nodes
        
    def _merge_results(self, vector_results: List[Any], index_results: List[Any]) -> Dict[str, Any]:
        """Merge and deduplicate results from different sources"""
        merged = {
            "vector_store_results": [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata
                } for doc in vector_results
            ],
            "llama_index_results": [
                {
                    "content": node.node.text,
                    "metadata": node.node.metadata
                } for node in index_results
            ]
        }
        return merged 