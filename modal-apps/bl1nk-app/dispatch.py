"""Strategy pattern: agent dispatch handlers.

Each agent type gets its own handler class with can_handle() + handle().
run() in modal_app.py iterates handlers instead of nested conditionals.
"""

from abc import ABC, abstractmethod
from typing import Any


class AgentHandler(ABC):
    """Interface for agent dispatch strategy."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    def can_delegate(self, sub_agent: str) -> bool:
        return False

    def handle(self, cmd: str, sub_agent: str) -> dict[str, Any]:
        return {"primary": self.name, "cmd": cmd or f"{self.name} --help"}

    def delegate(self, cmd: str, sub_agent: str) -> dict[str, Any]:
        return {
            "primary": self.name,
            "delegated_to": sub_agent,
            "status": "dispatched",
        }


class HermesHandler(AgentHandler):
    name = "hermes"

    def can_delegate(self, sub_agent: str) -> bool:
        return sub_agent in {"agy", "opencode", "sandbox"}


class AgyHandler(AgentHandler):
    name = "agy"

    def can_delegate(self, sub_agent: str) -> bool:
        return sub_agent in {"opencode", "sandbox"}


class OpencodeHandler(AgentHandler):
    name = "opencode"

    def handle(self, cmd: str, sub_agent: str) -> dict[str, Any]:
        return {"primary": "opencode", "mode": "headless", "cmd": cmd}


class SandboxHandler(AgentHandler):
    name = "sandbox"

    def handle(self, cmd: str, sub_agent: str) -> dict[str, Any]:
        return {"primary": "sandbox", "cmd": cmd or "sleep infinity"}


# Registry: add new handlers here instead of modifying run()
_HANDLERS: list[AgentHandler] = [
    HermesHandler(),
    AgyHandler(),
    OpencodeHandler(),
    SandboxHandler(),
]
_HANDLER_MAP = {h.name: h for h in _HANDLERS}


def dispatch(primary: str, sub_agent: str, cmd: str) -> dict[str, Any]:
    """Resolve handler and execute dispatch logic.

    Args:
        primary: Primary agent name.
        sub_agent: Sub-agent requested by caller.
        cmd: Command string.

    Returns:
        Dispatch result dict.

    Raises:
        ValueError: If primary agent is unknown.
    """
    handler = _HANDLER_MAP.get(primary)
    if handler is None:
        raise ValueError(f"Unknown agent: {primary}")

    if sub_agent != primary and handler.can_delegate(sub_agent):
        return handler.delegate(cmd, sub_agent)
    return handler.handle(cmd, sub_agent)
