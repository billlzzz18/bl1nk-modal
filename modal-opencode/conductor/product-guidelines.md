# Product Guidelines

## 1. Security First
- **Strict Authentication:** Every incoming request to the webhook MUST include a valid `password` or authorization token.
- **Controlled Environments:** Restrict system tool usage (especially `bash`) by providing minimal privileges and carefully parsing parameters.
- **Fail Securely:** Ensure any exception or timeout does not expose sensitive API keys or environment variables.

## 2. Robustness & Resilience
- **Timeouts & Limits:** Enforce strict execution timeouts for bash scripts and external API calls (e.g., `webfetch`) to prevent runaway processes.
- **Graceful Degradation:** If an external LLM provider or tool fails, return a standardized JSON error response rather than crashing the Gateway.

## 3. Code Readability & Maintainability
- **Type Annotations:** Strictly use Python type hints for all functions to maintain clarity in tool execution inputs and outputs.
- **Clear Documentation:** Maintain comprehensive docstrings. According to the project's global conventions, explain critical logic using the Thai language where possible.
- **Modular Tools:** Encapsulate each tool (e.g., `tool_read`, `tool_bash`) into distinct, easily testable functions.

## 4. API Design & Communication
- **Standardized JSON:** Follow consistent JSON structures for responses, including standardized fields like `success`, `error`, `response`, and `turns`.
- **Traceability:** Generate and include a unique `requestId` for every session to simplify debugging and log tracing.