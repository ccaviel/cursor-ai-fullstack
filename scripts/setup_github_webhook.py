import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
GITHUB_ACCESS_TOKEN = os.getenv('GITHUB_ACCESS_TOKEN')
BACKEND_URL = os.getenv('WEBHOOK_PUBLIC_URL', 'https://your-public-url.com')  # Public URL for webhook
REPO_OWNER = os.getenv('GITHUB_REPO_OWNER', 'ccaviel')  # Your GitHub username
REPO_NAME = os.getenv('GITHUB_REPO_NAME', 'cursor-ai-fullstack')  # Your repository name
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'your-webhook-secret')  # Secret for webhook signature

# Debug output
print("\nCurrent configuration:")
print(f"GitHub Token: {'*' * 8}{GITHUB_ACCESS_TOKEN[-4:] if GITHUB_ACCESS_TOKEN else 'Not set'}")
print(f"Repository Owner: {REPO_OWNER}")
print(f"Repository Name: {REPO_NAME}")
print(f"Webhook URL: {BACKEND_URL}/api/webhook")

if not GITHUB_ACCESS_TOKEN:
    raise ValueError("GITHUB_ACCESS_TOKEN is required. Please check your .env file.")

if BACKEND_URL == 'https://your-public-url.com':
    print("\nWARNING: Using placeholder URL. Please set WEBHOOK_PUBLIC_URL in your .env file.")
    print("The webhook URL must be accessible from the internet.")
    print("You can use services like ngrok or a cloud-hosted server.")
    choice = input("\nDo you want to continue with the placeholder URL? (y/n): ")
    if choice.lower() != 'y':
        print("Exiting. Please set WEBHOOK_PUBLIC_URL and try again.")
        exit(1)

# Test GitHub API access
def test_github_access():
    """Test GitHub API access with current token"""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {GITHUB_ACCESS_TOKEN}"
    }
    
    try:
        # Try to get user info
        response = requests.get(
            "https://api.github.com/user",
            headers=headers
        )
        response.raise_for_status()
        user_data = response.json()
        print(f"\nSuccessfully authenticated as: {user_data['login']}")
        
        # Try to access the repository
        response = requests.get(
            f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}",
            headers=headers
        )
        response.raise_for_status()
        repo_data = response.json()
        print(f"Repository access confirmed: {repo_data['full_name']}")
        
        return True
    except requests.exceptions.RequestException as e:
        print(f"\nError testing GitHub access: {str(e)}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        return False

def setup_github_webhook():
    """Set up GitHub webhook"""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {GITHUB_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    # Webhook configuration
    webhook_config = {
        "name": "web",  # This is required by GitHub
        "active": True,
        "events": [
            "pull_request",
            "push",
            "issues",
            "issue_comment",
            "pull_request_review",
            "pull_request_review_comment"
        ],
        "config": {
            "url": f"{BACKEND_URL}/api/webhook",
            "content_type": "json",
            "secret": WEBHOOK_SECRET,  # For webhook signature verification
            "insecure_ssl": "0"  # Require SSL validation
        }
    }

    try:
        # Create webhook
        response = requests.post(
            f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/hooks",
            headers=headers,
            json=webhook_config
        )
        response.raise_for_status()
        
        webhook_data = response.json()
        webhook_id = webhook_data["id"]
        
        print(f"\nSuccessfully created GitHub webhook!")
        print(f"Webhook ID: {webhook_id}")
        print(f"Webhook URL: {webhook_config['config']['url']}")
        
        # Save webhook info to .env
        with open("../.env", "a") as f:
            f.write(f"\nGITHUB_WEBHOOK_ID={webhook_id}\n")
            f.write(f"GITHUB_WEBHOOK_URL={webhook_config['config']['url']}\n")
            f.write(f"WEBHOOK_SECRET={webhook_config['config']['secret']}\n")
        
        # Test the webhook
        test_webhook(webhook_id, headers)
        
        return webhook_id
        
    except requests.exceptions.RequestException as e:
        print(f"\nError creating webhook: {str(e)}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        raise

def test_webhook(webhook_id, headers):
    """Test the webhook by sending a ping event"""
    try:
        response = requests.post(
            f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/hooks/{webhook_id}/tests",
            headers=headers
        )
        response.raise_for_status()
        print("\nWebhook test triggered successfully!")
        
    except requests.exceptions.RequestException as e:
        print(f"\nError testing webhook: {str(e)}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")

def list_webhooks():
    """List existing webhooks"""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {GITHUB_ACCESS_TOKEN}"
    }
    
    try:
        response = requests.get(
            f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/hooks",
            headers=headers
        )
        response.raise_for_status()
        
        webhooks = response.json()
        print("\nExisting webhooks:")
        for webhook in webhooks:
            print(f"ID: {webhook['id']}")
            print(f"URL: {webhook['config']['url']}")
            print(f"Events: {', '.join(webhook['events'])}")
            print(f"Active: {webhook['active']}")
            print("---")
        
        return webhooks
        
    except requests.exceptions.RequestException as e:
        print(f"\nError listing webhooks: {str(e)}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        raise

def delete_webhook(webhook_id):
    """Delete a webhook by ID"""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {GITHUB_ACCESS_TOKEN}"
    }
    
    try:
        response = requests.delete(
            f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/hooks/{webhook_id}",
            headers=headers
        )
        response.raise_for_status()
        print(f"\nSuccessfully deleted webhook {webhook_id}")
        
    except requests.exceptions.RequestException as e:
        print(f"\nError deleting webhook: {str(e)}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        raise

if __name__ == "__main__":
    print("\nTesting GitHub API access...")
    if not test_github_access():
        print("\nPlease check your GitHub token and repository settings.")
        exit(1)
    
    # First, list existing webhooks
    print("\nListing existing webhooks...")
    try:
        existing_webhooks = list_webhooks()
    except Exception as e:
        print(f"\nError listing webhooks: {str(e)}")
        exit(1)
    
    # Ask user what to do
    print("\nWhat would you like to do?")
    print("1. Create new webhook")
    print("2. Delete existing webhook")
    print("3. Test existing webhook")
    print("4. Exit")
    choice = input("Enter your choice (1-4): ")
    
    try:
        if choice == "1":
            setup_github_webhook()
        elif choice == "2":
            webhook_id = input("Enter webhook ID to delete: ")
            delete_webhook(webhook_id)
        elif choice == "3":
            webhook_id = input("Enter webhook ID to test: ")
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"Bearer {GITHUB_ACCESS_TOKEN}"
            }
            test_webhook(webhook_id, headers)
        elif choice == "4":
            print("Exiting...")
        else:
            print("Invalid choice")
    except Exception as e:
        print(f"\nError: {str(e)}")
        exit(1) 