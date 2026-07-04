import base64
import hashlib
import hmac

from main import verify_signature


def test_github_valid_signature(monkeypatch):
    monkeypatch.setenv("GITHUB_SECRET", "s3cret")
    body = b'{"foo": "bar"}'
    sig = "sha256=" + hmac.new(b"s3cret", body, hashlib.sha256).hexdigest()
    assert verify_signature("github", body, {"x-hub-signature-256": sig})


def test_github_invalid_signature(monkeypatch):
    monkeypatch.setenv("GITHUB_SECRET", "s3cret")
    body = b'{"foo": "bar"}'
    assert not verify_signature("github", body, {"x-hub-signature-256": "sha256=deadbeef"})


def test_gitlab_valid_token(monkeypatch):
    monkeypatch.setenv("GITLAB_SECRET", "tok123")
    assert verify_signature("gitlab", b"{}", {"x-gitlab-token": "tok123"})


def test_gitlab_invalid_token(monkeypatch):
    monkeypatch.setenv("GITLAB_SECRET", "tok123")
    assert not verify_signature("gitlab", b"{}", {"x-gitlab-token": "wrong"})


def test_azure_valid_basic_auth(monkeypatch):
    monkeypatch.setenv("AZURE_DEVOPS_USERNAME", "user")
    monkeypatch.setenv("AZURE_DEVOPS_PASSWORD", "pass")
    creds = base64.b64encode(b"user:pass").decode()
    headers = {"authorization": f"Basic {creds}"}
    assert verify_signature("azure", b"{}", headers)


def test_azure_invalid_basic_auth(monkeypatch):
    monkeypatch.setenv("AZURE_DEVOPS_USERNAME", "user")
    monkeypatch.setenv("AZURE_DEVOPS_PASSWORD", "pass")
    creds = base64.b64encode(b"user:wrong").decode()
    headers = {"authorization": f"Basic {creds}"}
    assert not verify_signature("azure", b"{}", headers)


def test_azure_missing_auth_header():
    assert not verify_signature("azure", b"{}", {})


def test_unknown_platform():
    assert not verify_signature("bitbucket", b"{}", {})
