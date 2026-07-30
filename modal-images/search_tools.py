"""Search tool registry — Hermes-inspired tool system for search service.

Patterns from Hermes Agent:
- ToolRegistry singleton with register() / dispatch() / get_definitions()
- Self-registration at module import time
- AST-based discovery (scan for registry.register before importing)
- Availability gating (check_fn with TTL cache)
- Progressive disclosure via tool_search / tool_describe / tool_call
"""

from __future__ import annotations

import ast
import importlib
import inspect
import os
import time
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np


# ── Tool Entry ───────────────────────────────────────────────

class ToolEntry:
    """A registered tool — name, schema, handler, availability gate."""

    __slots__ = (
        "name", "toolset", "schema", "handler", "check_fn",
        "is_async", "description", "emoji", "category",
    )

    def __init__(
        self, name: str, toolset: str, schema: dict, handler: Callable,
        check_fn: Optional[Callable] = None, is_async: bool = False,
        description: str = "", emoji: str = "🔧", category: str = "search",
    ):
        self.name = name
        self.toolset = toolset
        self.schema = schema
        self.handler = handler
        self.check_fn = check_fn
        self.is_async = is_async
        self.description = description or schema.get("description", "")
        self.emoji = emoji
        self.category = category


# ── Tool Result Helpers ──────────────────────────────────────

def tool_result(success: bool = True, data: Any = None, error: str = "") -> dict:
    return {"success": success, "data": data, "error": error}


def tool_error(message: str) -> dict:
    return {"success": False, "data": None, "error": message}


# ── Registry ─────────────────────────────────────────────────

class ToolRegistry:
    """Singleton tool registry — register, dispatch, discover, gate."""

    def __init__(self):
        self._entries: dict[str, ToolEntry] = {}
        self._check_cache: dict[str, tuple[float, bool]] = {}
        self._generation = 0  # bumps on register/override

    # ── Registration ──────────────────────────────────────────

    def register(
        self, name: str, toolset: str, schema: dict, handler: Callable,
        check_fn: Optional[Callable] = None, is_async: bool = False,
        description: str = "", emoji: str = "🔧", category: str = "search",
        override: bool = False,
    ) -> None:
        if name in self._entries and not override:
            raise ValueError(
                f"Tool '{name}' already registered. Use override=True to replace."
            )
        self._entries[name] = ToolEntry(
            name=name, toolset=toolset, schema=schema, handler=handler,
            check_fn=check_fn, is_async=is_async, description=description,
            emoji=emoji, category=category,
        )
        self._generation += 1

    # ── Dispatch ──────────────────────────────────────────────

    def dispatch(self, name: str, args: dict, **kwargs) -> dict:
        entry = self._entries.get(name)
        if not entry:
            return tool_error(f"Unknown tool: {name}")
        try:
            if entry.is_async:
                import asyncio
                loop = asyncio.new_event_loop()
                result = loop.run_until_complete(entry.handler(args, **kwargs))
                loop.close()
            else:
                result = entry.handler(args, **kwargs)
            return result if isinstance(result, dict) else tool_result(data=result)
        except Exception as e:
            return tool_error(f"{name} failed: {e}")

    # ── Definitions (for LLM function calling) ────────────────

    def get_definitions(self, tool_names: Optional[list[str]] = None,
                        quiet: bool = False) -> list[dict]:
        names = tool_names or list(self._entries.keys())
        defs = []
        for name in names:
            entry = self._entries.get(name)
            if not entry:
                continue
            if entry.check_fn and not self._check(entry.name, entry.check_fn):
                if not quiet:
                    pass  # silently skip unavailable tools
                continue
            defs.append({
                "type": "function",
                "function": {
                    "name": entry.name,
                    "description": f"{entry.emoji} {entry.description}",
                    "parameters": entry.schema.get("parameters", {}),
                },
            })
        return defs

    # ── Availability gate ─────────────────────────────────────

    def _check(self, name: str, check_fn: Callable) -> bool:
        now = time.time()
        cached = self._check_cache.get(name)
        if cached and (now - cached[0]) < 30:  # 30s TTL
            return cached[1]
        try:
            result = bool(check_fn())
        except Exception:
            result = False
        self._check_cache[name] = (now, result)
        return result

    # ── Discovery (AST scan → import) ─────────────────────────

    def discover(self, tools_dir: Optional[str] = None) -> list[str]:
        """Scan directory for tools that call registry.register(), import them."""
        if tools_dir is None:
            tools_dir = os.path.dirname(os.path.abspath(__file__))
        found = []
        for fpath in sorted(Path(tools_dir).glob("*.py")):
            fname = fpath.name
            if fname.startswith("_") or fname in ("registry.py", "test_"):
                continue
            if not self._file_has_register(fpath):
                continue
            mod_name = fname[:-3]
            try:
                importlib.import_module(f".{mod_name}", package="search_tools")
                found.append(mod_name)
            except ImportError as e:
                print(f"[tools] skip {mod_name}: {e}")
        return found

    @staticmethod
    def _file_has_register(fpath: Path) -> bool:
        """AST check: does file contain 'registry.register(' call? Faster than import."""
        try:
            tree = ast.parse(fpath.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    if isinstance(func, ast.Attribute) and func.attr == "register":
                        return True
                    if isinstance(func, ast.Name) and func.id == "register":
                        return True
        except SyntaxError:
            pass
        return False

    # ── Query ─────────────────────────────────────────────────

    def list_tools(self, category: Optional[str] = None,
                   toolset: Optional[str] = None) -> list[dict]:
        results = []
        for entry in self._entries.values():
            if category and entry.category != category:
                continue
            if toolset and entry.toolset != toolset:
                continue
            results.append({
                "name": entry.name, "toolset": entry.toolset,
                "description": entry.description, "emoji": entry.emoji,
                "category": entry.category, "available": self._check(
                    entry.name, entry.check_fn) if entry.check_fn else True,
            })
        return results


# ── Singleton ────────────────────────────────────────────────

registry = ToolRegistry()


# ── Search Tool Implementations ──────────────────────────────

# These self-register at import time (Hermes pattern)

def _init():
    """Register all search tools."""
    from search_service import (
        query, fts_search, kb_search, graph_related,
        embed, _active_embed_key, EMBED_MODELS,
        _metadata, _index, _ids, _deleted_ids,
    )

    # ── search.query ─────────────────────────────────────────
    registry.register(
        name="search_query",
        toolset="search",
        schema={
            "description": "Vector similarity search. Best for semantic understanding.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "search query"},
                    "source_type": {"type": "string", "enum": ["code", "doc", "session", "memory", ""],
                                    "description": "filter by source type"},
                    "top_k": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
        },
        handler=lambda args, **kw: query(args),
        emoji="🔍",
        description="Semantic vector search across indexed documents",
    )

    # ── search.fts ───────────────────────────────────────────
    registry.register(
        name="search_fts",
        toolset="search",
        schema={
            "description": "Full-text (BM25) keyword search. Best for exact term matching.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "keyword query"},
                    "source_type": {"type": "string", "enum": ["code", "doc", "session", "memory", ""]},
                    "top_k": {"type": "integer", "default": 10},
                },
                "required": ["query"],
            },
        },
        handler=lambda args, **kw: fts_search(args),
        emoji="📝",
        description="Keyword full-text search via BM25",
    )

    # ── search.kb ────────────────────────────────────────────
    registry.register(
        name="search_kb",
        toolset="search",
        schema={
            "description": "Search within a specific knowledge base (kb_id).",
            "parameters": {
                "type": "object",
                "properties": {
                    "kb_id": {"type": "string", "description": "knowledge base ID"},
                    "query": {"type": "string", "description": "search query (empty = recent docs)"},
                    "top_k": {"type": "integer", "default": 10},
                },
                "required": ["kb_id"],
            },
        },
        handler=lambda args, **kw: kb_search(args),
        emoji="📚",
        description="Search within a knowledge base",
    )

    # ── search.graph ─────────────────────────────────────────
    registry.register(
        name="search_graph",
        toolset="search",
        schema={
            "description": "Find related documents via shared metadata (tags, repo, path).",
            "parameters": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "document ID to find relations for"},
                    "max_nodes": {"type": "integer", "default": 10},
                },
                "required": ["id"],
            },
        },
        handler=lambda args, **kw: graph_related(args),
        emoji="🕸️",
        description="Related documents via metadata graph",
    )

    # ── search.status ────────────────────────────────────────
    registry.register(
        name="search_status",
        toolset="search",
        schema={
            "description": "Search index health and statistics.",
            "parameters": {"type": "object", "properties": {}},
        },
        handler=lambda args, **kw: tool_result(data={
            "total_docs": len(_ids),
            "deleted": len(_deleted_ids),
            "active": len(_ids) - len(_deleted_ids),
            "active_model": _active_embed_key,
            "embed_type": EMBED_MODELS[_active_embed_key].get("type", "local"),
        }),
        emoji="📊",
        description="Search index status and statistics",
    )


# Run registration at module import time (Hermes self-registration pattern)
_init()
