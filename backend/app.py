from rag_module.main import process_query, agent_orchestrator
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import asyncio
import redis
import json
import os
import sys
import subprocess
import requests
from dotenv import load_dotenv
from flask_login import login_required

# Add the parent directory to Python path using absolute path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
CORS(app)

# Initialize Redis cache with environment variables
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))
CACHE_EXPIRATION = 3600  # Cache expiration in seconds (1 hour)

cache = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True
)

# Server configuration
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', 8081))
N8N_HOST = os.getenv('N8N_HOST', 'localhost')
N8N_PORT = int(os.getenv('N8N_PORT', 5678))
N8N_PROTOCOL = os.getenv('N8N_PROTOCOL', 'http')
N8N_AUTH_TOKEN = os.getenv('N8N_AUTH_TOKEN')


@app.route('/api/execute', methods=['POST'])
def execute_command():
    data = request.get_json()
    command = data.get('command', '')

    # Check cache first
    cache_key = f"cmd:{command}"
    cached_result = cache.get(cache_key)
    if cached_result:
        logging.info(f"Cache hit for command: {command}")
        return jsonify(json.loads(cached_result))

    logging.info(f"Received command: {command}")
    # Simulated execution (in a real system, this would control Cursor AI)
    result = f"Simulated execution of command: {command}"

    # Cache the result
    cache.setex(cache_key, CACHE_EXPIRATION, json.dumps({'result': result}))
    return jsonify({'result': result})


@app.route('/api/rag', methods=['POST'])
def run_rag():
    data = request.get_json()
    query = data.get('query', '')

    # Check cache first
    cache_key = f"rag:{query}"
    cached_result = cache.get(cache_key)
    if cached_result:
        logging.info(f"Cache hit for RAG query: {query}")
        return jsonify(json.loads(cached_result))

    logging.info(f"Received RAG query: {query}")
    try:
        result = asyncio.run(process_query(query))
        # Cache the result
        cache.setex(cache_key, CACHE_EXPIRATION, json.dumps(result))
        return jsonify(result)
    except Exception as e:
        logging.exception("Error processing RAG query")
        return jsonify({"error": str(e)}), 500


@app.route('/api/orchestrate', methods=['POST'])
def orchestrate():
    data = request.get_json()
    task_description = data.get('task', '')

    # Check cache first
    cache_key = f"task:{task_description}"
    cached_result = cache.get(cache_key)
    if cached_result:
        logging.info(f"Cache hit for task: {task_description}")
        return jsonify(json.loads(cached_result))

    logging.info(f"Received orchestration task: {task_description}")
    try:
        plan = asyncio.run(agent_orchestrator(task_description))
        # Cache the result
        cache.setex(cache_key, CACHE_EXPIRATION, json.dumps(plan))
        return jsonify(plan)
    except Exception as e:
        logging.exception("Error in orchestration")
        return jsonify({"error": str(e)}), 500

# New endpoint: Git Pull


@app.route('/api/git-pull', methods=['POST'])
def git_pull():
    import subprocess
    try:
        # Execute 'git pull' from the repository root (assuming backend is in a subfolder)
        process = subprocess.run(
            ['git', 'pull'], capture_output=True, text=True, cwd='..')
        return jsonify({'result': process.stdout, 'error': process.stderr})
    except Exception as e:
        logging.exception('Error during git pull')
        return jsonify({'error': str(e)}), 500

# New endpoint: n8n Run


@app.route('/api/n8n-run', methods=['POST'])
def n8n_run():
    import requests
    data = request.get_json() or {}
    webhook_url = data.get(
        'webhook_url', f'{N8N_PROTOCOL}://{N8N_HOST}:{N8N_PORT}/webhook/trigger')
    payload = data.get('payload', {'message': 'Triggered from Cursor AI'})

    headers = {
        'Content-Type': 'application/json',
        'X-N8N-Auth-Token': N8N_AUTH_TOKEN
    }

    try:
        response = requests.post(webhook_url, json=payload, headers=headers)
        try:
            response_data = response.json()
        except Exception:
            response_data = response.text
        return jsonify({
            'status': response.status_code,
            'response': response_data
        })
    except Exception as e:
        logging.exception('Error triggering n8n workflow')
        return jsonify({'error': str(e)}), 500


@app.route('/api/docker/run', methods=['POST'])
def run_docker():
    """Run Docker commands through Cursor AI's Docker utility."""
    data = request.get_json()
    command = data.get('command', '')

    try:
        # Execute Docker command through Cursor AI
        process = subprocess.run(['cursor', 'docker', command],
                                 capture_output=True,
                                 text=True)

        return jsonify({
            'stdout': process.stdout,
            'stderr': process.stderr,
            'status': process.returncode
        })
    except Exception as e:
        logging.exception('Error running Docker command')
        return jsonify({'error': str(e)}), 500


@app.route('/api/docker/compose', methods=['POST'])
def run_docker_compose():
    """Run Docker Compose commands through Cursor AI's Docker utility."""
    data = request.get_json()
    # Default to 'up' if no command specified
    command = data.get('command', 'up')

    try:
        # Execute Docker Compose command through Cursor AI
        process = subprocess.run(['cursor', 'docker-compose', command],
                                 capture_output=True,
                                 text=True,
                                 cwd=os.path.dirname(os.path.dirname(__file__)))  # Run from project root

        return jsonify({
            'stdout': process.stdout,
            'stderr': process.stderr,
            'status': process.returncode
        })
    except Exception as e:
        logging.exception('Error running Docker Compose command')
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Docker."""
    try:
        # Check Redis connection
        redis_status = cache.ping()

        # Check RAG module by making a simple query
        rag_status = asyncio.run(process_query("test"))

        # Check n8n availability
        n8n_url = f"{N8N_PROTOCOL}://{N8N_HOST}:{N8N_PORT}/healthz"
        n8n_status = requests.get(n8n_url, timeout=5).status_code == 200

        return jsonify({
            'status': 'healthy',
            'redis': bool(redis_status),
            'rag_module': 'error' not in rag_status,
            'n8n': n8n_status
        })
    except Exception as e:
        logging.exception("Health check failed")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500


@app.route('/api/webhook', methods=['POST'])
def github_webhook():
    """Handle GitHub webhook events"""
    # Verify webhook signature if secret is configured
    if os.getenv('WEBHOOK_SECRET'):
        signature = request.headers.get('X-Hub-Signature-256')
        if not signature:
            return jsonify({"error": "No signature provided"}), 401
            
        # Verify signature
        import hmac
        import hashlib
        
        secret = os.getenv('WEBHOOK_SECRET').encode()
        expected_signature = 'sha256=' + hmac.new(
            secret,
            request.data,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            return jsonify({"error": "Invalid signature"}), 401
    
    # Get the event type
    event_type = request.headers.get('X-GitHub-Event')
    if not event_type:
        return jsonify({"error": "No event type provided"}), 400
        
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
        
    try:
        # Process different event types
        if event_type == 'pull_request':
            return handle_pull_request(data)
        elif event_type == 'push':
            return handle_push(data)
        elif event_type == 'issues':
            return handle_issue(data)
        elif event_type == 'issue_comment':
            return handle_comment(data)
        elif event_type == 'pull_request_review':
            return handle_review(data)
        elif event_type == 'ping':
            return jsonify({"message": "Webhook configured successfully!"}), 200
        else:
            return jsonify({"message": f"Event type {event_type} not handled"}), 200
            
    except Exception as e:
        logging.exception(f"Error processing webhook: {str(e)}")
        return jsonify({"error": str(e)}), 500

def handle_pull_request(data):
    """Handle pull request events"""
    action = data.get('action')
    pr = data.get('pull_request', {})
    
    if action == 'opened' or action == 'synchronize':
        # Analyze PR using RAG
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            query = f"Analyze PR: {pr.get('title')}\n\nDescription: {pr.get('body')}"
            result = loop.run_until_complete(process_query(query))
            
            # Post comment with analysis
            comment = f"## PR Analysis\n\n{result.get('answer', 'No analysis available')}"
            if result.get('source_documents'):
                comment += "\n\n### References\n" + "\n".join(result['source_documents'])
                
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"Bearer {GITHUB_ACCESS_TOKEN}"
            }
            
            response = requests.post(
                pr['comments_url'],
                headers=headers,
                json={"body": comment}
            )
            response.raise_for_status()
            
            return jsonify({
                "message": "PR analyzed and comment posted",
                "analysis": result
            }), 200
            
        finally:
            loop.close()
    
    return jsonify({"message": f"PR action {action} processed"}), 200

def handle_push(data):
    """Handle push events"""
    commits = data.get('commits', [])
    if not commits:
        return jsonify({"message": "No commits to analyze"}), 200
        
    # Analyze commits using RAG
    commit_messages = "\n".join(f"- {commit['message']}" for commit in commits)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        query = f"Analyze commits:\n{commit_messages}"
        result = loop.run_until_complete(process_query(query))
        return jsonify({
            "message": "Push event analyzed",
            "analysis": result
        }), 200
    finally:
        loop.close()

def handle_issue(data):
    """Handle issue events"""
    action = data.get('action')
    issue = data.get('issue', {})
    
    if action == 'opened':
        # Analyze issue using RAG
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            query = f"Analyze issue: {issue.get('title')}\n\nDescription: {issue.get('body')}"
            result = loop.run_until_complete(process_query(query))
            
            # Post comment with analysis
            comment = f"## Issue Analysis\n\n{result.get('answer', 'No analysis available')}"
            if result.get('source_documents'):
                comment += "\n\n### References\n" + "\n".join(result['source_documents'])
                
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "Authorization": f"Bearer {GITHUB_ACCESS_TOKEN}"
            }
            
            response = requests.post(
                issue['comments_url'],
                headers=headers,
                json={"body": comment}
            )
            response.raise_for_status()
            
            return jsonify({
                "message": "Issue analyzed and comment posted",
                "analysis": result
            }), 200
            
        finally:
            loop.close()
    
    return jsonify({"message": f"Issue action {action} processed"}), 200

def handle_comment(data):
    """Handle issue and PR comments"""
    action = data.get('action')
    comment = data.get('comment', {})
    
    if action == 'created':
        # Analyze comment using RAG
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            query = f"Analyze comment: {comment.get('body')}"
            result = loop.run_until_complete(process_query(query))
            return jsonify({
                "message": "Comment analyzed",
                "analysis": result
            }), 200
        finally:
            loop.close()
    
    return jsonify({"message": f"Comment action {action} processed"}), 200

def handle_review(data):
    """Handle pull request reviews"""
    action = data.get('action')
    review = data.get('review', {})
    
    if action == 'submitted':
        # Analyze review using RAG
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            query = f"Analyze review: {review.get('body')}"
            result = loop.run_until_complete(process_query(query))
            return jsonify({
                "message": "Review analyzed",
                "analysis": result
            }), 200
        finally:
            loop.close()
    
    return jsonify({"message": f"Review action {action} processed"}), 200

@app.errorhandler(Exception)
def handle_error(error):
    """Global error handler."""
    logging.exception("Unhandled error")
    return jsonify({
        'error': str(error),
        'type': error.__class__.__name__
    }), 500


if __name__ == '__main__':
    # The backend runs on port 8081
    app.run(host=HOST, port=PORT)
