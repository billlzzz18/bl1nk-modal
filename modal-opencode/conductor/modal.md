# Modal Development Guidelines

## 1. Resource Management
- **Explicit Decorators:** Always use `@app.function` to explicitly define resource limits (CPU, memory, timeout, GPU) for each Modal function.
- **Image Definition:** Keep the `modal.Image` definition minimal. Only install packages that are strictly necessary for the runtime environment to reduce cold start times.

## 2. Security & Secrets
- **Environment Variables:** Never hardcode API keys or sensitive passwords in the code. Always retrieve them using `os.environ.get()` combined with `modal.Secret.from_name()`.

## 3. Concurrency & Networking
- **Timeouts:** Configure generous but firm timeouts (`timeout=...`) for functions that make external API calls or run heavy bash commands.
- **Async Execution:** Use asynchronous patterns where appropriate, especially when handling network I/O to maximize throughput.

## 4. Stateful vs Stateless
- **Stateless Functions:** Design Modal functions to be as stateless as possible. Any state that needs to persist across executions should be stored externally (e.g., in a database or Modal Volume).