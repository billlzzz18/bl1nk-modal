from unittest.mock import AsyncMock, patch

import main


async def test_send_line_notify_posts_when_token_set(monkeypatch):
    monkeypatch.setenv("LINE_TOKEN", "tok")
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client

    with patch("httpx.AsyncClient", return_value=mock_client):
        await main.send_line_notify("hello")

    mock_client.post.assert_awaited_once()
    args, kwargs = mock_client.post.call_args
    assert args[0] == "https://notify-api.line.me/api/notify"
    assert kwargs["headers"]["Authorization"] == "Bearer tok"
    assert kwargs["data"]["message"] == "hello"


async def test_send_line_notify_noop_without_token(monkeypatch):
    monkeypatch.delenv("LINE_TOKEN", raising=False)
    with patch("httpx.AsyncClient") as mock_client_cls:
        await main.send_line_notify("hello")
    mock_client_cls.assert_not_called()
