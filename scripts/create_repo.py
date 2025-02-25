import os
import json
import base64
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
GITHUB_ACCESS_TOKEN = os.getenv('GITHUB_ACCESS_TOKEN')
REPO_NAME = "cursor-ai-fullstack"

if not GITHUB_ACCESS_TOKEN:
    raise ValueError("GITHUB_ACCESS_TOKEN is required. Please check your .env file.")

def check_repository_exists():
    """Check if repository already exists"""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {GITHUB_ACCESS_TOKEN}"
    }
    
    try:
        response = requests.get(
            f"https://api.github.com/repos/{get_user_name()}/{REPO_NAME}",
            headers=headers
        )
        return response.status_code == 200
    except:
        return False

def get_user_name():
    """Get authenticated user's GitHub username"""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {GITHUB_ACCESS_TOKEN}"
    }
    
    response = requests.get(
        "https://api.github.com/user",
        headers=headers
    )
    response.raise_for_status()
    return response.json()['login']

def create_repository():
    """Create a new GitHub repository"""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {GITHUB_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    # Repository configuration
    repo_config = {
        "name": REPO_NAME,
        "description": "Cursor AI Fullstack Project with GitHub Integration",
        "private": False,  # Make it public
        "has_issues": True,
        "has_projects": True,
        "has_wiki": True,
        "auto_init": True  # Initialize with README
    }

    try:
        # Create repository
        response = requests.post(
            "https://api.github.com/user/repos",
            headers=headers,
            json=repo_config
        )
        response.raise_for_status()
        
        repo_data = response.json()
        print(f"\nSuccessfully created repository!")
        print(f"Repository URL: {repo_data['html_url']}")
        print(f"Clone URL: {repo_data['clone_url']}")
        
        # Save repository info to .env
        with open("../.env", "a") as f:
            f.write(f"\nGITHUB_REPO_NAME={repo_data['name']}\n")
            f.write(f"GITHUB_REPO_URL={repo_data['html_url']}\n")
        
        # Initialize with project files
        init_repository(repo_data['full_name'])
        
        return repo_data
        
    except requests.exceptions.RequestException as e:
        print(f"\nError creating repository: {str(e)}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        raise

def init_repository(full_name):
    """Initialize repository with project files"""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {GITHUB_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    files = {
        "README.md": """# Cursor AI Fullstack Project

A fullstack project integrating:
- Flask backend with RAG capabilities
- GitHub webhook integration
- Automated PR and issue analysis
- Intelligent code review system

## Setup
1. Clone the repository
2. Install dependencies
3. Configure environment variables
4. Run the backend server

## Features
- Automated PR analysis
- Issue tracking with AI assistance
- Code review automation
- Webhook integration
""",
        ".gitignore": """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Environment variables
.env

# IDE
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
""",
        "requirements.txt": """flask>=2.0.1
requests>=2.31.0
python-dotenv>=1.0.0
redis>=4.5.4
"""
    }

    try:
        for filename, content in files.items():
            # Check if file exists
            try:
                response = requests.get(
                    f"https://api.github.com/repos/{full_name}/contents/{filename}",
                    headers=headers
                )
                if response.status_code == 200:
                    print(f"File {filename} already exists, skipping...")
                    continue
            except:
                pass
            
            # Create file with proper base64 encoding
            content_bytes = content.encode('utf-8')
            content_base64 = base64.b64encode(content_bytes).decode('utf-8')
            
            response = requests.put(
                f"https://api.github.com/repos/{full_name}/contents/{filename}",
                headers=headers,
                json={
                    "message": f"Initialize {filename}",
                    "content": content_base64
                }
            )
            response.raise_for_status()
            print(f"Created {filename}")
            
    except requests.exceptions.RequestException as e:
        print(f"\nError initializing repository: {str(e)}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        raise

if __name__ == "__main__":
    print("\nChecking GitHub repository...")
    try:
        username = get_user_name()
        if check_repository_exists():
            print(f"\nRepository already exists at: https://github.com/{username}/{REPO_NAME}")
            print("Updating repository files...")
            init_repository(f"{username}/{REPO_NAME}")
            print("\nRepository update complete!")
        else:
            repo_data = create_repository()
            print("\nRepository setup complete!")
        print("You can now clone the repository and start working on it.")
    except Exception as e:
        print(f"\nError: {str(e)}")
        exit(1) 