#!/bin/bash
# Setup MCP servers and plugins for agy
#
# Usage:
#   ./setup.sh              # show available MCP servers and plugins
#   ./setup.sh mcp          # setup all MCP servers
#   ./setup.sh plugins      # install all plugins

echo "=== Modal AGY Setup ==="
echo ""

if [ "$1" = "mcp" ]; then
    echo "Setting up MCP servers (via plugins)..."
    
    # context7 - Library documentation (MCP included)
    echo "Installing context7..."
    agy plugin install https://github.com/upstash/context7
    
    # linear - Issue tracking (MCP included)
    echo "Installing linear..."
    agy plugin install https://github.com/cline/linear-mcp
    
    # file system - File operations (MCP included)
    echo "Installing file system MCP..."
    agy plugin install https://github.com/mark3labs/mcp-filesystem-server
    
    # miro - Visual collaboration (MCP included)
    echo "Installing miro..."
    agy plugin install https://github.com/k-jarzyna/mcp-miro
    
    # caveman - Unknown tool (MCP included)
    echo "Installing caveman..."
    agy plugin install https://github.com/standardbeagle/caveman-mcp
    
    # exa - Search engine (MCP included)
    echo "Installing exa..."
    agy plugin install https://github.com/exa-labs/exa-mcp-server
    
    echo ""
    echo "MCP servers installed via plugins:"
    agy plugin list
    
elif [ "$1" = "plugins" ]; then
    echo "Installing plugins..."
    
    # context7
    agy plugin install https://github.com/upstash/context7
    
    # linear
    agy plugin install https://github.com/cline/linear-mcp
    
    # file system
    agy plugin install https://github.com/mark3labs/mcp-filesystem-server
    
    # miro
    agy plugin install https://github.com/k-jarzyna/mcp-miro
    
    # caveman
    agy plugin install https://github.com/standardbeagle/caveman-mcp
    
    # exa
    agy plugin install https://github.com/exa-labs/exa-mcp-server
    
    echo ""
    echo "Plugins installed:"
    agy plugin list
    
else
    echo "Available MCP servers (via plugins):"
    echo "  - context7    : https://github.com/upstash/context7"
    echo "  - linear      : https://github.com/cline/linear-mcp"
    echo "  - file system : https://github.com/mark3labs/mcp-filesystem-server"
    echo "  - miro        : https://github.com/k-jarzyna/mcp-miro"
    echo "  - caveman     : https://github.com/standardbeagle/caveman-mcp"
    echo "  - exa         : https://github.com/exa-labs/exa-mcp-server"
    echo ""
    echo "Usage:"
    echo "  $0 mcp      # setup all MCP servers"
    echo "  $0 plugins  # install all plugins"
fi
