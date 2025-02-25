import os
import json
import requests
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential, ClientSecretCredential
from msgraph.core import GraphClient
from azure.core.exceptions import ClientAuthenticationError

# Load environment variables
load_dotenv()

# Azure AD Configuration
TENANT_ID = os.getenv('AZURE_TENANT_ID')
CLIENT_ID = os.getenv('AZURE_CLIENT_ID')
CLIENT_SECRET = os.getenv('AZURE_CLIENT_SECRET')
SUBSCRIPTION_ID = os.getenv('AZURE_SUBSCRIPTION_ID')

# GitHub Configuration
GITHUB_ACCESS_TOKEN = os.getenv('GITHUB_ACCESS_TOKEN')
REPO_OWNER = os.getenv('GITHUB_REPO_OWNER', 'ccaviel')
REPO_NAME = os.getenv('GITHUB_REPO_NAME', 'cursor-ai-fullstack')

def get_graph_client():
    """Initialize Microsoft Graph client"""
    try:
        # Try DefaultAzureCredential first (works with managed identities, CLI login, etc.)
        credential = DefaultAzureCredential()
        return GraphClient(credential=credential)
    except ClientAuthenticationError:
        # Fall back to client secret if default credentials aren't available
        credential = ClientSecretCredential(
            tenant_id=TENANT_ID,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET
        )
        return GraphClient(credential=credential)

def create_logic_app_workflow():
    """Create Azure Logic App workflow for GitHub integration"""
    workflow_definition = {
        "definition": {
            "$schema": "https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#",
            "actions": {
                "Parse_GitHub_Event": {
                    "type": "ParseJson",
                    "inputs": {
                        "content": "@triggerBody()",
                        "schema": {
                            "properties": {
                                "action": {"type": "string"},
                                "pull_request": {"type": "object"},
                                "issue": {"type": "object"},
                                "comment": {"type": "object"},
                                "repository": {"type": "object"}
                            },
                            "type": "object"
                        }
                    }
                },
                "Process_with_RAG": {
                    "type": "Http",
                    "inputs": {
                        "method": "POST",
                        "uri": "http://localhost:8081/api/rag",
                        "body": {
                            "query": "@{if(contains(triggerBody(), 'pull_request'), concat('Analyze PR: ', triggerBody()?['pull_request']?['title'], '\\n\\nDescription: ', triggerBody()?['pull_request']?['body']), concat('Analyze Issue: ', triggerBody()?['issue']?['title'], '\\n\\nDescription: ', triggerBody()?['issue']?['body']))}"
                        }
                    }
                },
                "Post_GitHub_Comment": {
                    "type": "Http",
                    "inputs": {
                        "method": "POST",
                        "uri": "@{if(contains(triggerBody(), 'pull_request'), triggerBody()?['pull_request']?['comments_url'], triggerBody()?['issue']?['comments_url'])}",
                        "headers": {
                            "Authorization": "Bearer @{environment().GITHUB_ACCESS_TOKEN}",
                            "Content-Type": "application/json"
                        },
                        "body": {
                            "body": "## Analysis Results\\n\\n@{body('Process_with_RAG')}"
                        }
                    }
                }
            },
            "triggers": {
                "github_webhook": {
                    "type": "Request",
                    "kind": "Http",
                    "inputs": {
                        "schema": {
                            "properties": {
                                "action": {"type": "string"},
                                "pull_request": {"type": "object"},
                                "issue": {"type": "object"},
                                "comment": {"type": "object"},
                                "repository": {"type": "object"}
                            },
                            "type": "object"
                        }
                    }
                }
            }
        }
    }

    # Get Graph client
    client = get_graph_client()

    try:
        # Create workflow
        workflow = client.post(
            "/workflows",
            json=workflow_definition
        )
        
        print("\nWorkflow created successfully!")
        print(f"Workflow ID: {workflow.json()['id']}")
        
        # Get webhook URL
        trigger = client.get(f"/workflows/{workflow.json()['id']}/triggers/github_webhook")
        webhook_url = trigger.json()['properties']['inputs']['triggerUrl']
        
        print(f"Webhook URL: {webhook_url}")
        
        # Update GitHub repository with webhook
        setup_github_webhook(webhook_url)
        
        # Save configuration to .env
        update_env_file(workflow.json()['id'], webhook_url)
        
        return workflow.json()['id']
        
    except Exception as e:
        print(f"\nError creating workflow: {str(e)}")
        raise

def setup_github_webhook(webhook_url):
    """Configure GitHub repository webhook"""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {GITHUB_ACCESS_TOKEN}"
    }

    webhook_config = {
        "name": "web",
        "active": True,
        "events": [
            "pull_request",
            "issues",
            "issue_comment",
            "pull_request_review",
            "pull_request_review_comment"
        ],
        "config": {
            "url": webhook_url,
            "content_type": "json",
            "insecure_ssl": "0"
        }
    }

    try:
        response = requests.post(
            f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/hooks",
            headers=headers,
            json=webhook_config
        )
        response.raise_for_status()
        
        print("\nGitHub webhook configured successfully!")
        print(f"Webhook ID: {response.json()['id']}")
        
        return response.json()['id']
        
    except requests.exceptions.RequestException as e:
        print(f"\nError configuring GitHub webhook: {str(e)}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        raise

def update_env_file(workflow_id, webhook_url):
    """Update .env file with workflow configuration"""
    env_path = os.path.join(os.path.dirname(__file__), "../.env")
    
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            env_content = f.read()
            
        # Update or add Azure workflow configuration
        env_updates = f"""
# Azure Logic App Configuration
AZURE_WORKFLOW_ID={workflow_id}
AZURE_WEBHOOK_URL={webhook_url}
"""
        
        if "AZURE_WORKFLOW_ID" in env_content:
            # Replace existing configuration
            lines = env_content.splitlines()
            updated_lines = []
            skip_next = False
            for line in lines:
                if skip_next:
                    skip_next = False
                    continue
                if line.startswith("# Azure Logic App Configuration"):
                    updated_lines.append(env_updates)
                    skip_next = True
                else:
                    updated_lines.append(line)
            env_content = "\n".join(updated_lines)
        else:
            # Add new configuration
            env_content += env_updates
            
        with open(env_path, "w") as f:
            f.write(env_content)
            
        print("\nUpdated .env file with workflow configuration")

def test_workflow(workflow_id):
    """Test the workflow with a sample PR event"""
    client = get_graph_client()
    
    test_event = {
        "action": "opened",
        "pull_request": {
            "title": "Test PR for workflow",
            "body": "This is a test pull request to verify the workflow.",
            "comments_url": f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues/1/comments"
        }
    }
    
    try:
        response = client.post(
            f"/workflows/{workflow_id}/triggers/github_webhook/run",
            json=test_event
        )
        
        print("\nTest event sent successfully!")
        print("Response:", response.json())
        
    except Exception as e:
        print(f"\nError testing workflow: {str(e)}")
        raise

if __name__ == "__main__":
    print("\nSetting up Azure Logic App workflow...")
    
    # Validate required environment variables
    if not all([TENANT_ID, CLIENT_ID, CLIENT_SECRET, GITHUB_ACCESS_TOKEN]):
        raise ValueError("Missing required environment variables. Please check AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, and GITHUB_ACCESS_TOKEN")
    
    try:
        # Create and configure workflow
        workflow_id = create_logic_app_workflow()
        
        # Test the workflow
        print("\nTesting workflow...")
        test_workflow(workflow_id)
        
        print("\nWorkflow setup completed successfully!")
        
    except Exception as e:
        print(f"\nError: {str(e)}")
        exit(1) 