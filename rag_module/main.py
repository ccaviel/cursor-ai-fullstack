import os
import subprocess
import logging
import traceback
import json
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from langchain_community.llms import HuggingFacePipeline, CTransformers
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, StorageContext, load_index_from_storage
from llama_index.core.node_parser import SimpleNodeParser
from langchain.cache import RedisSemanticCache
from langchain_core.documents import Document
from redis import Redis
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import torch

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)

# Global cache for the vector stores
cached_vector_store = None
cached_llama_index = None
cached_llm = None

# Configuration
USE_CPU_ONLY = os.getenv('USE_CPU_ONLY', 'false').lower() == 'true'
MODEL_TYPE = os.getenv('MODEL_TYPE', 'huggingface').lower()
MODEL_NAME = os.getenv('MODEL_NAME', 'mistralai/Mistral-7B-Instruct-v0.2')
EMBEDDING_MODEL = os.getenv(
    'EMBEDDING_MODEL', 'sentence-transformers/all-mpnet-base-v2')
TEMPERATURE = float(os.getenv('MODEL_TEMPERATURE', '0.7'))
MAX_TOKENS = int(os.getenv('MODEL_MAX_TOKENS', '2000'))
QUANTIZATION = int(os.getenv('MODEL_QUANTIZATION', '4'))
TEMPERATURE = float(os.getenv('AGENT_TEMPERATURE', '0.7'))
MAX_TOKENS = int(os.getenv('OPENAI_MAX_TOKENS', '2000'))
CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', '1000'))
CHUNK_OVERLAP = int(os.getenv('CHUNK_OVERLAP', '200'))
AGENT_MAX_STEPS = int(os.getenv('AGENT_MAX_STEPS', '10'))
AGENT_MEMORY_SIZE = int(os.getenv('AGENT_MEMORY_SIZE', '5'))
AGENT_CACHE_TTL = int(os.getenv('AGENT_CACHE_TTL', '3600'))

# Configuration from environment variables
CHROMA_DB_DIR = os.getenv('CHROMA_DB_DIR', './chroma_db')
LLAMA_INDEX_STORAGE_DIR = os.getenv('LLAMA_INDEX_STORAGE_DIR', './storage')
REPO_DIR = os.getenv('REPO_DIR', './repos')
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
CACHE_EXPIRATION = 3600  # 1 hour

REPOS = {
    'coderabbit': {
        'url': 'https://github.com/coderabbitai/coderabbit-docs.git',
        'local_path': os.path.join(REPO_DIR, 'coderabbit-docs')
    },
    'browser-use': {
        'url': 'https://github.com/browser-use/browser-use.git',
        'local_path': os.path.join(REPO_DIR, 'browser-use')
    },
    'augment-vim': {
        'url': 'https://github.com/augmentcode/augment.vim.git',
        'local_path': os.path.join(REPO_DIR, 'augment-vim')
    }
}

# Initialize caches
redis_client = Redis.from_url(REDIS_URL)
semantic_cache = RedisSemanticCache(
    redis_url=REDIS_URL,
    embedding=get_embeddings(),
    score_threshold=0.2
)

# Lightweight model options for CPU-only mode
CPU_FRIENDLY_MODELS = {
    'llm': 'TheBloke/Mistral-7B-Instruct-v0.2-GGUF',
    'embeddings': 'sentence-transformers/all-MiniLM-L6-v2'
}

# Initialize LLM


def get_llm():
    global cached_llm
    if cached_llm is not None:
        return cached_llm

    try:
        if USE_CPU_ONLY or not torch.cuda.is_available():
            logging.info("Using CPU-optimized model")
            if MODEL_TYPE == 'gguf':
                # Use GGUF model with CTransformers for CPU
                cached_llm = CTransformers(
                    model=CPU_FRIENDLY_MODELS['llm'],
                    model_type="mistral",
                    temperature=TEMPERATURE,
                    max_new_tokens=MAX_TOKENS,
                    config={'context_length': 2048}
                )
            else:
                # Use smaller model for CPU
                tokenizer = AutoTokenizer.from_pretrained(
                    "TinyLlama/TinyLlama-1.1B-Chat-v1.0")
                model = AutoModelForCausalLM.from_pretrained(
                    "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
                    device_map="cpu",
                    torch_dtype=torch.float32
                )
        else:
            logging.info("Using GPU-accelerated model")
            tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
            model = AutoModelForCausalLM.from_pretrained(
                MODEL_NAME,
                device_map="auto",
                torch_dtype=torch.float16,
                load_in_4bit=QUANTIZATION == 4,
                load_in_8bit=QUANTIZATION == 8
            )

        if not isinstance(cached_llm, CTransformers):
            pipe = pipeline(
                "text-generation",
                model=model,
                tokenizer=tokenizer,
                max_new_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                top_p=0.95,
                repetition_penalty=1.15
            )
            cached_llm = HuggingFacePipeline(pipeline=pipe)

        return cached_llm
    except Exception as e:
        logging.error(f"Error initializing LLM: {e}")
        # Fallback to TinyLlama if main model fails
        tokenizer = AutoTokenizer.from_pretrained(
            "TinyLlama/TinyLlama-1.1B-Chat-v1.0")
        model = AutoModelForCausalLM.from_pretrained(
            "TinyLlama/TinyLlama-1.1B-Chat-v1.0",
            device_map="cpu",
            torch_dtype=torch.float32
        )
        pipe = pipeline(
            "text-generation",
            model=model,
            tokenizer=tokenizer,
            max_new_tokens=MAX_TOKENS,
            temperature=TEMPERATURE
        )
        cached_llm = HuggingFacePipeline(pipeline=pipe)
        return cached_llm

# Initialize embeddings


def get_embeddings():
    if USE_CPU_ONLY or not torch.cuda.is_available():
        model_name = CPU_FRIENDLY_MODELS['embeddings']
    else:
        model_name = EMBEDDING_MODEL

    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={'device': 'cuda' if torch.cuda.is_available()
                      and not USE_CPU_ONLY else 'cpu'}
    )


def sync_repositories():
    """Sync all repositories and return their local paths."""
    for repo_name, repo_info in REPOS.items():
        repo_path = repo_info['local_path']
        if not os.path.exists(repo_path):
            try:
                subprocess.run(
                    ["git", "clone", repo_info['url'], repo_path], check=True)
                logging.info(f"Cloned {repo_name} repository.")
            except Exception as e:
                logging.error(f"Error cloning {repo_name} repository: {e}")
        else:
            try:
                subprocess.run(["git", "-C", repo_path, "pull"], check=True)
                logging.info(f"Updated {repo_name} repository.")
            except Exception as e:
                logging.error(f"Error pulling {repo_name} repository: {e}")


def build_llama_index():
    """Build LlamaIndex from all repositories."""
    global cached_llama_index

    if cached_llama_index is not None:
        logging.info("Using cached LlamaIndex.")
        return cached_llama_index

    # Check if we have a saved index
    if os.path.exists(LLAMA_INDEX_STORAGE_DIR):
        try:
            storage_context = StorageContext.from_defaults(
                persist_dir=LLAMA_INDEX_STORAGE_DIR)
            cached_llama_index = load_index_from_storage(storage_context)
            logging.info("Loaded LlamaIndex from storage.")
            return cached_llama_index
        except Exception as e:
            logging.error(f"Error loading saved index: {e}")

    # Sync repositories first
    sync_repositories()

    # Load documents from all repositories
    all_documents = []
    for repo_name, repo_info in REPOS.items():
        try:
            documents = SimpleDirectoryReader(
                repo_info['local_path']).load_data()
            all_documents.extend(documents)
            logging.info(f"Loaded documents from {repo_name}")
        except Exception as e:
            logging.error(f"Error loading documents from {repo_name}: {e}")

    # Create and save index
    parser = SimpleNodeParser()
    nodes = parser.get_nodes_from_documents(all_documents)
    index = VectorStoreIndex(nodes)
    index.storage_context.persist(LLAMA_INDEX_STORAGE_DIR)

    cached_llama_index = index
    return index


async def process_query(query: str) -> Dict[str, Any]:
    """Process a natural language query using RAG with semantic caching"""
    try:
        # Check semantic cache first
        cached_result = semantic_cache.lookup(query, "default_llm")
        if cached_result:
            logging.info(f"Semantic cache hit for query: {query}")
            return {
                "query": query,
                "answer": cached_result,
                "source": "cache"
            }

        # Load vector store and create retriever
        vector_store = await build_vector_store()
        retriever = vector_store.as_retriever(search_kwargs={"k": 3})

        # Initialize QA chain with configured LLM
        qa = RetrievalQA.from_chain_type(
            llm=get_llm(),
            chain_type="stuff",
            retriever=retriever,
            return_source_documents=True
        )

        # Get response
        result = await qa.ainvoke({"query": query})
        answer = result["result"]
        source_docs = result.get("source_documents", [])

        # Cache the result
        semantic_cache.update(query, "default_llm", answer)

        # Get execution plan with configured parameters
        plan = await agent_orchestrator(query)

        return {
            "query": query,
            "answer": answer,
            "source_documents": [doc.page_content for doc in source_docs],
            "plan": plan,
            "source": "live",
            "model": "huggingface",
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS
        }

    except Exception as e:
        logging.exception("Error processing query")
        return {
            "error": str(e),
            "stack_trace": traceback.format_exc()
        }


async def load_documents() -> List[Document]:
    """Load and process documents from multiple sources"""
    try:
        docs = []

        # Load from repositories
        for repo_name, repo_info in REPOS.items():
            repo_path = os.path.join(REPO_DIR, repo_name)

            # Skip if repo doesn't exist
            if not os.path.exists(repo_path):
                logging.warning(
                    f"Repository {repo_name} not found at {repo_path}")
                continue

            # Load markdown and text files
            for ext in [".md", ".txt", ".py", ".js", ".ts"]:
                for root, _, files in os.walk(repo_path):
                    for file in files:
                        if file.endswith(ext):
                            try:
                                file_path = os.path.join(root, file)
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    content = f.read()

                                # Create document with metadata
                                doc = Document(
                                    page_content=content,
                                    metadata={
                                        "source": repo_name,
                                        "file_path": file_path,
                                        "file_type": ext,
                                        "repo_url": repo_info.get("url", "")
                                    }
                                )
                                docs.append(doc)

                            except Exception as e:
                                logging.error(
                                    f"Error loading file {file_path}: {str(e)}")
                                continue

        # Load documentation files
        docs_dir = os.path.join(os.path.dirname(__file__), "documentation")
        if os.path.exists(docs_dir):
            for file in os.listdir(docs_dir):
                if file.endswith((".md", ".txt")):
                    try:
                        file_path = os.path.join(docs_dir, file)
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()

                        doc = Document(
                            page_content=content,
                            metadata={
                                "source": "documentation",
                                "file_path": file_path,
                                "file_type": os.path.splitext(file)[1]
                            }
                        )
                        docs.append(doc)

                    except Exception as e:
                        logging.error(
                            f"Error loading documentation file {file}: {str(e)}")
                        continue

        logging.info(f"Loaded {len(docs)} documents")
        return docs

    except Exception as e:
        logging.exception("Error loading documents")
        return []


async def build_vector_store(docs: Optional[List[Document]] = None) -> Chroma:
    """Build or retrieve cached vector store"""
    global cached_vector_store

    if cached_vector_store is not None:
        logging.info("Using cached vector store")
        return cached_vector_store

    if docs is None:
        docs = await load_documents()

    embeddings = get_embeddings()

    # Build Chroma vector store with persistence
    vector_store = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory=CHROMA_DB_DIR
    )
    vector_store.persist()

    cached_vector_store = vector_store
    return vector_store


def sync_and_load_documents():
    """Load local documentation and CodeRabbit docs by syncing the repository."""
    docs = []
    # Load local documentation from documentation.txt
    try:
        with open(os.path.join(os.path.dirname(__file__), 'documentation.txt'), 'r') as f:
            docs.append(f.read())
    except Exception as e:
        logging.error(f"Error reading documentation.txt: {e}")

    # Define the CodeRabbit docs repository URL and local directory
    # Placeholder URL; replace with actual if needed
    coderabbit_repo_url = "https://github.com/coderabbit-docs/coderabbit-docs.git"
    repo_dir = os.path.join(os.path.dirname(__file__), 'coderabbit-docs')

    # Clone the repository if it does not exist; otherwise, pull the latest changes
    if not os.path.exists(repo_dir):
        try:
            subprocess.run(
                ["git", "clone", coderabbit_repo_url, repo_dir], check=True)
            logging.info("Cloned CodeRabbit docs repository.")
        except Exception as e:
            logging.error(f"Error cloning CodeRabbit docs: {e}")
    else:
        try:
            subprocess.run(["git", "-C", repo_dir, "pull"], check=True)
            logging.info("Updated CodeRabbit docs repository.")
        except Exception as e:
            logging.error(f"Error pulling CodeRabbit docs: {e}")

    # Attempt to load a primary documentation file from the cloned repo (e.g., README.md)
    readme_path = os.path.join(repo_dir, 'README.md')
    if os.path.exists(readme_path):
        try:
            with open(readme_path, 'r') as f:
                docs.append(f.read())
        except Exception as e:
            logging.error(f"Error reading CodeRabbit README.md: {e}")
    else:
        logging.warning("CodeRabbit README.md not found in the repository.")

    return docs


async def agent_orchestrator(task_description: str) -> List[str]:
    """Break down a task into executable steps with caching"""
    try:
        # Check cache for existing plan
        cache_key = f"plan:{task_description}"
        cached_plan = redis_client.get(cache_key)
        if cached_plan:
            return json.loads(cached_plan)

        # Create planning prompt
        prompt = f"""Break down this task into clear executable steps:
        Task: {task_description}
        
        Requirements:
        1. Each step should be specific and actionable
        2. Include error handling where appropriate
        3. Consider dependencies between steps
        4. Aim for modularity and reusability
        
        Steps:"""

        # Get plan from LLM
        llm = get_llm()
        response = await llm.agenerate([prompt])
        steps = [step.strip() for step in response.generations[0].text.split(
            "\n") if step.strip()]

        # Cache the plan
        redis_client.setex(
            cache_key,
            AGENT_CACHE_TTL,
            json.dumps(steps)
        )

        return steps

    except Exception as e:
        logging.exception("Error in agent orchestration")
        return [
            f"Error generating plan: {str(e)}",
            "Falling back to direct query processing"
        ]
