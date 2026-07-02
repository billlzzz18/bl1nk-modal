import os
import pytest
from opencode import webhook
from starlette.responses import JSONResponse
from unittest.mock import patch, MagicMock
from opencode import tool_edit, tool_list_directory, tool_websearch

def test_tool_websearch_success():
    # Mock search result or call real one if environment allows
    # For now, let's test the implementation logic
    result = tool_websearch(query="python programming")
    assert result["success"] is True
    assert "content" in result
    assert len(result["content"]) > 0

def test_tool_websearch_empty_query():
    result = tool_websearch(query="")
    assert result["success"] is False
    assert "query" in result["error"].lower()

def test_tool_list_directory_simple(tmp_path):
    # Create subdirs and files
    (tmp_path / "subdir").mkdir()
    (tmp_path / "file1.txt").write_text("content")
    (tmp_path / "subdir" / "file2.txt").write_text("content")
    
    # Test flat list
    result = tool_list_directory(path=str(tmp_path), tree=False)
    assert result["success"] is True
    assert "file1.txt" in result["content"]
    assert "subdir" in result["content"]

def test_tool_list_directory_tree(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "b").mkdir()
    (tmp_path / "a" / "file.py").write_text("code")
    
    result = tool_list_directory(path=str(tmp_path), tree=True)
    assert result["success"] is True
    assert "a/" in result["content"]
    assert "  b/" in result["content"]
    assert "  file.py" in result["content"]

def test_tool_edit_success(tmp_path):
    # Create a dummy file
    test_file = tmp_path / "hello.py"
    test_file.write_text("print('hello')\nprint('world')")
    
    # Call tool_edit
    result = tool_edit(
        path=str(test_file),
        old_string="print('world')",
        new_string="print('agent')"
    )
    
    assert result["success"] is True
    assert "print('agent')" in test_file.read_text()
    assert "print('world')" not in test_file.read_text()

def test_tool_edit_file_not_found():
    result = tool_edit(path="non_existent.txt", old_string="a", new_string="b")
    assert result["success"] is False
    assert "error" in result

def test_tool_edit_string_not_found(tmp_path):
    test_file = tmp_path / "data.txt"
    test_file.write_text("apple pie")
    
    result = tool_edit(path=str(test_file), old_string="banana", new_string="cherry")
    assert result["success"] is False
    assert "not found" in result["error"].lower()

@patch("opencode.run_conversation")
def test_webhook_unauthorized_missing_password(mock_run):
    # Set server password
    os.environ["KILO_SERVER_PASSWORD"] = "secret123"
    
    # Call webhook without password in body
    request_data = {"prompt": "test"}
    response = webhook.local(request_data)
    
    assert isinstance(response, JSONResponse)
    assert response.status_code == 401

@patch("opencode.run_conversation")
def test_webhook_unauthorized_wrong_password(mock_run):
    os.environ["KILO_SERVER_PASSWORD"] = "secret123"
    
    request_data = {"prompt": "test", "password": "wrong"}
    response = webhook.local(request_data)
    
    assert isinstance(response, JSONResponse)
    assert response.status_code == 401

@patch("opencode.run_conversation")
def test_webhook_unauthorized_if_server_password_not_set(mock_run):
    # This is the test that should FAIL before implementation
    # if we want to enforce mandatory password even if not in ENV
    if "KILO_SERVER_PASSWORD" in os.environ:
        del os.environ["KILO_SERVER_PASSWORD"]
    if "OPENCODE_SERVER_PASSWORD" in os.environ:
        del os.environ["OPENCODE_SERVER_PASSWORD"]
        
    request_data = {"prompt": "test"}
    response = webhook.local(request_data)
    
    # Goal: it should return 401 if password is missing in request
    assert isinstance(response, JSONResponse)
    assert response.status_code == 401
