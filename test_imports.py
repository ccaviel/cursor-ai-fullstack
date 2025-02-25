import os
import sys

# Add the current directory to Python path
current_dir = os.path.abspath(os.path.dirname(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from rag_module.main import process_query, agent_orchestrator
    print("Successfully imported from rag_module!")
except Exception as e:
    print(f"Error importing from rag_module: {e}")
    print(f"Current directory: {current_dir}")
    print(f"Python path: {sys.path}")
    print(f"Directory contents: {os.listdir(current_dir)}")
