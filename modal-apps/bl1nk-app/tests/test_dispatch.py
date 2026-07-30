"""Strategy pattern: each handler tested independently via its public interface."""

import pytest

from dispatch import (
    AgyHandler,
    HermesHandler,
    OpencodeHandler,
    SandboxHandler,
    dispatch,
)


class TestHermesHandler:
    def test_handle_returns_default_cmd(self):
        h = HermesHandler()
        result = h.handle("", "hermes")
        assert result == {"primary": "hermes", "cmd": "hermes --help"}

    def test_handle_with_custom_cmd(self):
        h = HermesHandler()
        result = h.handle("echo hi", "hermes")
        assert result == {"primary": "hermes", "cmd": "echo hi"}

    def test_can_delegate_to_agy(self):
        assert HermesHandler().can_delegate("agy") is True

    def test_can_delegate_to_opencode(self):
        assert HermesHandler().can_delegate("opencode") is True

    def test_can_delegate_to_sandbox(self):
        assert HermesHandler().can_delegate("sandbox") is True

    def test_cannot_delegate_to_hermes(self):
        assert HermesHandler().can_delegate("hermes") is False

    def test_delegate_returns_dispatched(self):
        h = HermesHandler()
        result = h.delegate("cmd", "agy")
        assert result == {
            "primary": "hermes",
            "delegated_to": "agy",
            "status": "dispatched",
        }


class TestAgyHandler:
    def test_handle_returns_default_cmd(self):
        h = AgyHandler()
        result = h.handle("", "agy")
        assert result == {"primary": "agy", "cmd": "agy --help"}

    def test_can_delegate_to_opencode(self):
        assert AgyHandler().can_delegate("opencode") is True

    def test_can_delegate_to_sandbox(self):
        assert AgyHandler().can_delegate("sandbox") is True

    def test_cannot_delegate_to_hermes(self):
        assert AgyHandler().can_delegate("hermes") is False

    def test_cannot_delegate_to_agy(self):
        assert AgyHandler().can_delegate("agy") is False


class TestOpcencodeHandler:
    def test_handle_returns_headless(self):
        h = OpencodeHandler()
        result = h.handle("build", "opencode")
        assert result == {"primary": "opencode", "mode": "headless", "cmd": "build"}

    def test_handle_default_cmd(self):
        h = OpencodeHandler()
        result = h.handle("", "opencode")
        assert result == {"primary": "opencode", "mode": "headless", "cmd": ""}

    def test_never_delegates(self):
        assert OpencodeHandler().can_delegate("anything") is False


class TestSandboxHandler:
    def test_handle_with_cmd(self):
        h = SandboxHandler()
        result = h.handle("bash script.sh", "sandbox")
        assert result == {"primary": "sandbox", "cmd": "bash script.sh"}

    def test_handle_defaults_to_sleep(self):
        h = SandboxHandler()
        result = h.handle("", "sandbox")
        assert result == {"primary": "sandbox", "cmd": "sleep infinity"}

    def test_never_delegates(self):
        assert SandboxHandler().can_delegate("anything") is False


class TestDispatch:
    def test_dispatch_hermes_direct(self):
        result = dispatch("hermes", "hermes", "cmd")
        assert result["primary"] == "hermes"
        assert "delegated_to" not in result

    def test_dispatch_hermes_delegates_to_agy(self):
        result = dispatch("hermes", "agy", "cmd")
        assert result["primary"] == "hermes"
        assert result["delegated_to"] == "agy"

    def test_dispatch_agy_direct(self):
        result = dispatch("agy", "agy", "cmd")
        assert result["primary"] == "agy"

    def test_dispatch_agy_delegates_to_sandbox(self):
        result = dispatch("agy", "sandbox", "cmd")
        assert result["primary"] == "agy"
        assert result["delegated_to"] == "sandbox"

    def test_dispatch_opencode_headless(self):
        result = dispatch("opencode", "opencode", "build")
        assert result == {"primary": "opencode", "mode": "headless", "cmd": "build"}

    def test_dispatch_sandbox_default(self):
        result = dispatch("sandbox", "sandbox", "")
        assert result == {"primary": "sandbox", "cmd": "sleep infinity"}

    def test_raises_on_unknown_agent(self):
        with pytest.raises(ValueError, match="Unknown agent"):
            dispatch("unknown", "hermes", "")

    def test_unknown_sub_agent_does_not_delegate(self):
        result = dispatch("hermes", "unknown", "cmd")
        assert result["primary"] == "hermes"
        assert result["cmd"] == "cmd"
