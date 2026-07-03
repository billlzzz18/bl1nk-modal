# Modal AGY Sandbox

Image for running agy CLI on Modal cloud.

## What's in the image

- git 2.39.5
- gh 2.95.0 (GitHub CLI)
- agy 1.0.9 (Google Antigravity)
- cargo 1.96.0 + rustc 1.96.0
- python3 3.11
- Agent context: ~/.gemini/{AGENTS,SOUL,TOOLS,BOOT}.md

## Resources

- CPU: 1 core
- Memory: 5120 MB (matches Hermes sandbox)
- Timeout: 600s

## Usage

### Basic Commands

```bash
# Show available tools and usage
./run.sh

# Interactive shell
./run.sh shell

# Run any command
./run.sh "cargo build"
./run.sh "git status"
./run.sh "python3 --version"
```

### Working with Plugins

```bash
# Install plugin from GitHub
./run.sh agy plugin install https://github.com/upstash/context7

# List installed plugins
./run.sh agy plugin list

# Validate plugin structure
./run.sh agy plugin validate /path/to/plugin
```

### Working with Projects

```bash
# Clone a project
./run.sh git clone https://github.com/you/project

# Clone and work on it
./run.sh "git clone https://github.com/you/project /tmp/project && cd /tmp/project && cargo build"
```

### Setup MCP Servers

```bash
# Setup all MCP servers
./setup.sh mcp

# Install all plugins
./setup.sh plugins
```

### Complete Workflow

```bash
# 1. Start interactive shell
./run.sh shell

# 2. Inside shell, install plugin
agy plugin install https://github.com/upstash/context7

# 3. Clone your project
git clone https://github.com/you/project /tmp/project

# 4. Work on your project
cd /tmp/project
cargo build

# 5. Push changes when done
git push
```

## How it works

1. Image has tools + agent context (built once)
2. `agy plugin install <url>` installs plugin at runtime to ~/.gemini/config/plugins/
3. `git clone` pulls the project you work on
4. Plugin context stays in agy global, project context stays in project

## Agent context files

Located in `context/` directory, copied to `~/.gemini/` in image:

- AGENTS.md - agent instructions
- SOUL.md - agent personality
- TOOLS.md - tools reference
- BOOT.md - startup checklist

## MCP Servers

MCP servers are installed via plugins:

| Server | URL |
|--------|-----|
| context7 | https://github.com/upstash/context7 |
| linear | https://github.com/cline/linear-mcp |
| file system | https://github.com/mark3labs/mcp-filesystem-server |
| miro | https://github.com/k-jarzyna/mcp-miro |
| caveman | https://github.com/standardbeagle/caveman-mcp |
| exa | https://github.com/exa-labs/exa-mcp-server |

## Plugin format

See [bl1nk-plugin/PLUGIN_FORMAT.md](../00dev/bl1nk-plugin/PLUGIN_FORMAT.md)
