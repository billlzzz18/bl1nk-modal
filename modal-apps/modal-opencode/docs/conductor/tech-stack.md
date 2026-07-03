# Technology Stack

## 1. Programming Language
- **Python (3.12):** The primary language used to build the Gateway, specifically chosen to run in a `debian_slim` environment on Modal.

## 2. Frameworks & Backend
- **FastAPI / Starlette:** Used for creating the `/webhook` endpoint with high-performance asynchronous request handling.
- **Modal:** The core serverless infrastructure and orchestrator. Responsible for providing scalable, on-demand GPU/CPU compute environments.

## 3. Key Libraries & Utilities
- **httpx:** Used for making outbound asynchronous API calls (e.g., fetching web content, DuckDuckGo web search, or interacting with the KiloCode / OpenCode APIs).
- **subprocess:** Built-in Python library used to execute shell (`bash`) commands dynamically on the server.
- **glob / json:** Standard utility libraries for searching files and formatting payloads.
- **re:** Used for regex-based text extraction and HTML cleaning in search/fetch tools.

## 4. Environment & Deployment
- **Debian (Slim):** The container operating system.
- **Packages:** Node.js, npm, git, curl, openssh-client (pre-installed for agentic tooling).
- **Security:** Handled through `modal.Secret` integration for API Key management.