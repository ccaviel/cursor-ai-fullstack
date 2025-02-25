import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
N8N_CLOUD_URL = os.getenv('N8N_CLOUD_URL')
N8N_WEBHOOK_ID = os.getenv('N8N_WEBHOOK_ID')
GITHUB_ACCESS_TOKEN = os.getenv('GITHUB_ACCESS_TOKEN')
N8N_AUTH_TOKEN = os.getenv('N8N_AUTH_TOKEN')

if not all([N8N_CLOUD_URL, N8N_WEBHOOK_ID, GITHUB_ACCESS_TOKEN, N8N_AUTH_TOKEN]):
    raise ValueError("Missing required environment variables. Please check N8N_CLOUD_URL, N8N_WEBHOOK_ID, GITHUB_ACCESS_TOKEN, and N8N_AUTH_TOKEN")

# GitHub Webhook Workflow Definition
WORKFLOW = {
    "name": "GitHub Webhook Handler",
    "nodes": [
        {
            "name": "GitHub Trigger",
            "type": "n8n-nodes-base.github",
            "parameters": {
                "authentication": "bearerAuth",
                "options": {
                    "bearerAuth": {
                        "value": GITHUB_ACCESS_TOKEN
                    }
                },
                "resource": "webhook",
                "webhookUri": "={{$node.Webhook.json.webhookUrl}}",
                "events": [
                    "pull_request",
                    "push",
                    "issues",
                    "issue_comment",
                    "pull_request_review",
                    "pull_request_review_comment"
                ]
            }
        },
        {
            "name": "Webhook",
            "type": "n8n-nodes-base.webhook",
            "parameters": {
                "path": "github-webhook",
                "responseMode": "lastNode",
                "options": {}
            }
        },
        {
            "name": "Event Router",
            "type": "n8n-nodes-base.switch",
            "parameters": {
                "rules": {
                    "rules": [
                        {
                            "value1": "={{$json.action}}",
                            "value2": "opened",
                            "operation": "equal",
                            "output": "Pull Request Opened"
                        },
                        {
                            "value1": "={{$json.action}}",
                            "value2": "created",
                            "operation": "equal",
                            "output": "Comment Created"
                        },
                        {
                            "value1": "={{$json.action}}",
                            "value2": "push",
                            "operation": "equal",
                            "output": "Push Event"
                        }
                    ]
                }
            }
        },
        {
            "name": "Process PR",
            "type": "n8n-nodes-base.httpRequest",
            "parameters": {
                "url": "http://localhost:8081/api/rag",
                "method": "POST",
                "authentication": "bearerAuth",
                "options": {
                    "bearerAuth": {
                        "value": GITHUB_ACCESS_TOKEN
                    }
                },
                "body": {
                    "query": "=Analyze PR: {{$json.pull_request.title}}\n\nDescription: {{$json.pull_request.body}}"
                }
            }
        },
        {
            "name": "Format Response",
            "type": "n8n-nodes-base.function",
            "parameters": {
                "functionCode": """
                const data = $input.item(0)?.json;
                let response = '';
                
                if (data.pull_request) {
                    response = `## Pull Request Analysis
                    
                    ${data.response || 'No analysis available'}
                    
                    ### Context and References
                    ${(data.sources || []).join('\\n')}`;
                } else if (data.comment) {
                    response = `## Comment Analysis
                    
                    ${data.response || 'No analysis available'}`;
                } else if (data.commits) {
                    response = `## Push Analysis
                    
                    Changes detected in ${data.commits.length} commit(s)
                    ${data.response || 'No analysis available'}`;
                }
                
                return { json: { analysis: response } };
                """
            }
        },
        {
            "name": "GitHub Comment",
            "type": "n8n-nodes-base.github",
            "parameters": {
                "authentication": "bearerAuth",
                "options": {
                    "bearerAuth": {
                        "value": GITHUB_ACCESS_TOKEN
                    }
                },
                "resource": "issue",
                "operation": "createComment",
                "owner": "={{$json.repository.owner.login}}",
                "repository": "={{$json.repository.name}}",
                "issueNumber": "={{$json.pull_request ? $json.pull_request.number : $json.issue.number}}",
                "body": "={{$node['Format Response'].json.analysis}}"
            }
        }
    ],
    "connections": {
        "Webhook": {
            "main": [
                [
                    {
                        "node": "GitHub Trigger",
                        "type": "main",
                        "index": 0
                    }
                ]
            ]
        },
        "GitHub Trigger": {
            "main": [
                [
                    {
                        "node": "Event Router",
                        "type": "main",
                        "index": 0
                    }
                ]
            ]
        },
        "Event Router": {
            "main": [
                [
                    {
                        "node": "Process PR",
                        "type": "main",
                        "index": 0
                    }
                ]
            ]
        },
        "Process PR": {
            "main": [
                [
                    {
                        "node": "Format Response",
                        "type": "main",
                        "index": 0
                    }
                ]
            ]
        },
        "Format Response": {
            "main": [
                [
                    {
                        "node": "GitHub Comment",
                        "type": "main",
                        "index": 0
                    }
                ]
            ]
        }
    },
    "settings": {
        "saveExecutionProgress": True,
        "saveManualExecutions": True,
        "callerPolicy": "workflowsFromSameOwner"
    },
    "tags": ["github", "webhook", "automation"]
}

def import_workflow():
    """Import the workflow into n8n"""
    if not N8N_AUTH_TOKEN:
        raise ValueError("N8N_AUTH_TOKEN is required for importing workflows to n8n")
        
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-N8N-API-KEY": N8N_AUTH_TOKEN
    }
    
    try:
        # Create new workflow
        response = requests.post(
            f"{N8N_CLOUD_URL}/api/v1/workflows",
            headers=headers,
            json=WORKFLOW
        )
        response.raise_for_status()
        
        workflow_data = response.json()
        workflow_id = workflow_data["id"]
        
        print(f"\nSuccessfully imported workflow with ID: {workflow_id}")
        print(f"Webhook URL: {N8N_CLOUD_URL}/webhook/{workflow_id}")
        
        # Activate the workflow
        response = requests.post(
            f"{N8N_CLOUD_URL}/api/v1/workflows/{workflow_id}/activate",
            headers=headers
        )
        response.raise_for_status()
        
        print("\nWorkflow activated successfully!")
        
        # Save the workflow ID and webhook URL to .env
        with open("../.env", "a") as f:
            f.write(f"\nN8N_WORKFLOW_ID={workflow_id}\n")
            f.write(f"N8N_WEBHOOK_URL={N8N_CLOUD_URL}/webhook/{workflow_id}\n")
        
        return workflow_id
        
    except requests.exceptions.RequestException as e:
        print(f"\nError importing workflow: {str(e)}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        raise

if __name__ == "__main__":
    import_workflow()