## Integration Testing

After deploying the backend and RAG module using Docker-Compose (or running them individually), install and activate the Cursor AI extension in your IDE (or use a VS Code emulator). The extension launches a webview that communicates with the backend using the following endpoints:

- **Execute Command** (endpoint: `/api/execute`): Triggers a simulated command execution.
- **RAG Query** (endpoint: `/api/rag`): Processes a retrieval-augmented generation query and returns an intelligent answer.
- **Agent Orchestration** (endpoint: `/api/orchestrate`): Breaks down a task description into actionable steps using an Auto‑GPT/AgentGPT‑style orchestrator.

Use the webview interface to interact with these endpoints. Check the logs in the backend container and review responses in the webview UI to verify that each component communicates correctly. 