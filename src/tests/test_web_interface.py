import pytest
from fastapi.testclient import TestClient
from fastapi import Response # Import Response for mocking
from unittest.mock import AsyncMock, patch, MagicMock
import sys
import os
import asyncio
import sqlite3 # Import sqlite3 for mocking

# モジュールのインポートパスを追加
# Ensure correct relative path for modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from modules.web_interface import app, preview_queue # Import app and queue
from modules.db_manager import DB_PATH, init_database # Import DB_PATH for cleanup

# Fixture to initialize and clean up the database for web interface tests
@pytest.fixture(scope="module", autouse=True)
def setup_test_environment():
    # Ensure a clean state before tests run
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_database(DB_PATH)
    # Ensure preview directory exists
    if not os.path.exists("previews"):
        os.makedirs("previews")
    yield
    # Clean up database file after tests
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    # Clean up preview files
    preview_dir = "previews"
    if os.path.exists(preview_dir):
        for f in os.listdir(preview_dir):
            if f.startswith("mock_") or f.startswith("test_"): # Be specific about cleanup
                os.remove(os.path.join(preview_dir, f))
        # try:
        #     os.rmdir(preview_dir) # Only remove if empty
        # except OSError:
        #     pass

@pytest.fixture
def client():
    """テスト用のFastAPIクライアントを返す"""
    # Removed patch('asyncio.create_task') as it might interfere with TestClient setup
    yield TestClient(app)

# --- Mocks for dependent modules ---
@pytest.fixture
def mock_fetch_content():
    with patch('modules.web_interface.fetch_content') as mock:
        mock.return_value = {
            "html_content": "<html><body>Mock Content</body></html>",
            "resources": {"css": [], "js": [], "images": []}
        }
        yield mock

@pytest.fixture
def mock_save_content():
    with patch('modules.web_interface.save_content') as mock:
        mock.return_value = "test-random-url-save"
        yield mock

@pytest.fixture
def mock_get_content():
    # This mock is used for /view, /resource, etc., NOT for the root / listing
    with patch('modules.web_interface.get_content') as mock:
        mock.return_value = {
            "original_url": "http://mockview.com",
            "html_content": "<html><body>Mock Get Content for View</body></html>",
            "resources": {"css": [], "js": [], "images": []},
            "preview_filename": "mock_preview_view.jpg"
        }
        yield mock

# Note: mock_get_content_no_preview is not needed if we mock the DB access in root tests

@pytest.fixture
def mock_delete_content():
    with patch('modules.web_interface.delete_content') as mock:
        yield mock

@pytest.fixture
def mock_render_content():
    with patch('modules.web_interface.render_content') as mock:
        mock.return_value = "<html><body>Rendered Mock Content</body></html>"
        yield mock

@pytest.fixture
def mock_preview_queue_put():
    with patch('modules.web_interface.preview_queue.put', new_callable=AsyncMock) as mock:
         yield mock

# --- Test Cases ---

@patch('modules.web_interface.sqlite3.connect')
def test_root_endpoint_empty(mock_connect, client):
    """ルートエンドポイント（アーカイブなし）のテスト"""
    # Setup mock cursor and connection to return no archives
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [] # No archives
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    response = client.get("/")
    assert response.status_code == 200
    assert "<h1>Web Archive</h1>" in response.text
    assert "No pages archived yet." in response.text
    assert 'id="list-view-btn"' in response.text
    assert 'id="grid-view-btn"' in response.text
    mock_connect.assert_called_once_with(DB_PATH) # Verify DB was queried

@patch('modules.web_interface.sqlite3.connect')
def test_root_endpoint_with_archive(mock_connect, client):
    """ルートエンドポイント（アーカイブあり）のテスト"""
    # Setup mock cursor and connection
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        ("test-random-url-list", "http://mock.com/list", "2024-01-01T10:00:00", "list_preview.jpg")
    ]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    # Mock os.path.exists for the preview image check within the root handler
    with patch('os.path.exists', return_value=True) as mock_os_exists:
        response = client.get("/")

    assert response.status_code == 200
    assert "http://mock.com/list" in response.text
    assert "(Archived: 2024-01-01T10:00:00)" in response.text
    assert '<img src="/preview/list_preview.jpg"' in response.text
    assert 'onclick="deleteArchive(\'test-random-url-list\')"' in response.text
    mock_connect.assert_called_once_with(DB_PATH)
    mock_os_exists.assert_called_once_with(os.path.join("previews", "list_preview.jpg"))

@patch('modules.web_interface.sqlite3.connect')
def test_root_endpoint_with_generating_preview(mock_connect, client):
    """ルートエンドポイント（プレビュー生成中）のテスト"""
    # Setup mock cursor and connection
    mock_cursor = MagicMock()
    # Simulate preview_filename is None (still generating or failed)
    mock_cursor.fetchall.return_value = [
        ("test-random-url-gen", "http://mock.com/generating", "2024-01-02T11:00:00", None)
    ]
    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    response = client.get("/")
    assert response.status_code == 200
    assert "http://mock.com/generating" in response.text
    assert '<span class="preview-indicator">Generating preview...</span>' in response.text
    assert 'onclick="deleteArchive(\'test-random-url-gen\')"' in response.text
    mock_connect.assert_called_once_with(DB_PATH)

@pytest.mark.asyncio
async def test_archive_endpoint_success(client, mock_fetch_content, mock_save_content, mock_preview_queue_put):
    """アーカイブ成功とキューへの追加テスト"""
    test_url = "https://example-success.com"
    response = client.post("/archive", json={"url": test_url})

    assert response.status_code == 200
    json_response = response.json()
    assert json_response["status"] == "success"
    assert "random_url" in json_response
    saved_random_url = json_response["random_url"]

    mock_fetch_content.assert_called_once_with(test_url)
    mock_save_content.assert_called_once()
    saved_content_arg = mock_save_content.call_args[0][0]
    assert saved_content_arg["original_url"] == test_url
    assert "preview_filename" in saved_content_arg

    await asyncio.sleep(0) # Allow event loop to process queue.put
    mock_preview_queue_put.assert_called_once()
    queued_task_args = mock_preview_queue_put.call_args[0][0]
    expected_view_url = f"http://localhost:8000/view/{saved_random_url}"
    assert queued_task_args[0] == expected_view_url
    assert queued_task_args[1] == saved_content_arg["preview_filename"]
    assert queued_task_args[2] == saved_random_url

def test_archive_endpoint_invalid_url(client):
    """無効なURLでのアーカイブエンドポイントのテスト"""
    response = client.post("/archive", json={"url": "invalid-url"})
    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "Invalid URL format"

def test_archive_endpoint_fetch_failure(client, mock_fetch_content):
    """コンテンツ取得失敗時のアーカイブテスト"""
    mock_fetch_content.side_effect = Exception("Fetch failed")
    response = client.post("/archive", json={"url": "https://example-fail.com"})
    assert response.status_code == 500
    assert response.json()["detail"]["message"] == "Fetch failed"

# mock_get_content is used here for the /view endpoint
def test_view_endpoint_success(client, mock_get_content, mock_render_content):
    """ビューエンドポイント成功テスト"""
    response = client.get("/view/test-random-url-view")
    assert response.status_code == 200
    assert "Rendered Mock Content" in response.text
    mock_get_content.assert_called_once_with("test-random-url-view")
    mock_render_content.assert_called_once()
    call_args = mock_render_content.call_args[0]
    assert call_args[0] == mock_get_content.return_value
    assert call_args[1] == "test-random-url-view"

def test_view_endpoint_not_found(client, mock_get_content):
    """ビューエンドポイント（コンテンツなし）テスト"""
    mock_get_content.side_effect = Exception("Content not found")
    response = client.get("/view/not-found-url")
    assert response.status_code == 404
    assert "Content not found" in response.json()["detail"]["message"]

def test_delete_endpoint_success(client, mock_delete_content):
    """削除エンドポイント成功テスト"""
    response = client.delete("/delete/test-random-url-delete")
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_delete_content.assert_called_once_with("test-random-url-delete")

def test_delete_endpoint_not_found(client, mock_delete_content):
    """削除エンドポイント（コンテンツなし）テスト"""
    mock_delete_content.side_effect = Exception("No content found to delete")
    response = client.delete("/delete/not-found-url-delete")
    assert response.status_code == 404
    assert "No content found to delete" in response.json()["detail"]["message"]

@patch('os.path.exists')
@patch('modules.web_interface.FileResponse')
def test_serve_preview_success(mock_file_response, mock_exists, client):
    """プレビュー画像提供成功テスト"""
    mock_exists.return_value = True
    # Simulate FileResponse behavior more accurately if needed, or just check call
    mock_file_response.return_value = Response(content=b"dummyjpeg", media_type="image/jpeg")

    response = client.get("/preview/test_preview.jpg")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    mock_exists.assert_called_once_with(os.path.join("previews", "test_preview.jpg"))
    mock_file_response.assert_called_once_with(os.path.join("previews", "test_preview.jpg"), media_type="image/jpeg")

@patch('os.path.exists')
def test_serve_preview_not_found(mock_exists, client):
    """プレビュー画像提供（ファイルなし）テスト"""
    mock_exists.return_value = False
    response = client.get("/preview/not_found.jpg")
    assert response.status_code == 404
    assert "Preview image not found" in response.json()["detail"]
    mock_exists.assert_called_once_with(os.path.join("previews", "not_found.jpg"))

# Ensure there's a newline at the end
