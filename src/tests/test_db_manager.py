import pytest
import sqlite3
from unittest.mock import patch, MagicMock
import sys
import os
import json

# モジュールのインポートパスを追加
# Ensure correct relative path for modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from modules.db_manager import save_content, get_content, delete_content, init_database, DB_PATH

# Use a consistent temporary database for all tests in this module
@pytest.fixture(scope="module")
def test_db(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("data") / "test_archive.db"
    init_database(str(db_path))
    # Clean up previews dir if it exists from previous runs
    preview_dir = "previews"
    if os.path.exists(preview_dir):
        for f in os.listdir(preview_dir):
            os.remove(os.path.join(preview_dir, f))
    yield str(db_path)
    # Cleanup previews after tests if needed, though delete_content should handle it
    if os.path.exists(preview_dir):
         for f in os.listdir(preview_dir):
            os.remove(os.path.join(preview_dir, f))
         # os.rmdir(preview_dir) # Optional: remove dir if empty

@pytest.fixture
def sample_content():
    """テスト用のサンプルコンテンツ"""
    return {
        "original_url": "https://example.com",
        "html_content": "<html><body>Test Content</body></html>",
        "resources": {
            "css": [{"url": "style.css", "content": "body { color: black; }"}],
            "js": [{"url": "script.js", "content": "console.log('test');"}],
            # Simulate base64 encoded data as saved by the modified save_content
            "images": [{"url": "image.jpg", "webp_data_b64": "d2VicCBkYXRh"}] # "webp data" base64 encoded
        },
        "preview_filename": "test_preview.jpg" # Add preview filename
    }

import uuid # Import uuid for side_effect

@pytest.fixture
def mock_uuid():
    """UUID生成のモック（呼び出しごとに異なる値を返す）"""
    # Use a side effect to return different values on each call
    mock_values = [f"random-url-{i}" for i in range(20)] # Generate enough unique IDs
    with patch('uuid.uuid4', side_effect=mock_values) as mock:
        yield mock

def test_init_database(test_db):
    """データベース初期化とカラム追加のテスト"""
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='archives';")
    result = cursor.fetchone()
    assert result is not None
    assert result[0] == "archives"
    # Check if preview_filename column exists
    cursor.execute("PRAGMA table_info(archives);")
    columns = [info[1] for info in cursor.fetchall()]
    assert "preview_filename" in columns
    conn.close()

def test_save_content(test_db, sample_content, mock_uuid):
    """コンテンツ保存（プレビューファイル名含む）のテスト"""
    # Modify sample content to simulate what's passed before saving
    content_to_save = sample_content.copy()
    content_to_save["resources"] = {
         "css": [{"url": "style.css", "content": "body { color: black; }"}],
         "js": [{"url": "script.js", "content": "console.log('test');"}],
         "images": [{"url": "image.jpg", "webp_data": b"webp data"}] # Pass raw bytes
    }

    random_url = save_content(content_to_save, db_path=test_db)
    # Assert against the first value returned by the mock side_effect
    assert random_url == "random-url-0"

    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute("SELECT original_url, html_content, resources, preview_filename FROM archives WHERE random_url = ?", (random_url,))
    result = cursor.fetchone()
    conn.close()

    assert result is not None
    assert result[0] == "https://example.com"
    assert result[1] == "<html><body>Test Content</body></html>"
    resources = json.loads(result[2]) # Resources are saved as JSON
    assert len(resources["css"]) == 1
    assert resources["css"][0]["url"] == "style.css"
    assert "webp_data_b64" in resources["images"][0] # Check if data was base64 encoded
    assert result[3] == "test_preview.jpg" # Check preview filename

def test_get_content(test_db, sample_content, mock_uuid):
    """コンテンツ取得（プレビューファイル名とデコード含む）のテスト"""
     # Save first to have data to retrieve
    content_to_save = sample_content.copy()
    content_to_save["resources"] = {
         "css": [{"url": "style.css", "content": "body { color: black; }"}],
         "js": [{"url": "script.js", "content": "console.log('test');"}],
         "images": [{"url": "image.jpg", "webp_data": b"webp data"}]
    }
    random_url = save_content(content_to_save, db_path=test_db)

    retrieved_content = get_content(random_url, db_path=test_db)
    assert retrieved_content["original_url"] == "https://example.com"
    assert retrieved_content["html_content"] == "<html><body>Test Content</body></html>"
    assert len(retrieved_content["resources"]["css"]) == 1
    assert retrieved_content["resources"]["css"][0]["url"] == "style.css"
    assert "webp_data" in retrieved_content["resources"]["images"][0] # Check if data was decoded
    assert retrieved_content["resources"]["images"][0]["webp_data"] == b"webp data"
    assert retrieved_content["preview_filename"] == "test_preview.jpg"

def test_get_content_not_found(test_db):
    """存在しないコンテンツ取得のテスト"""
    with pytest.raises(Exception) as exc_info:
        get_content("non-existent-url", db_path=test_db)
    assert "Content not found for random_url: non-existent-url" in str(exc_info.value)

# Mock os.path.exists and os.remove for delete test
@patch('os.path.exists')
@patch('os.remove')
def test_delete_content(mock_remove, mock_exists, test_db, sample_content, mock_uuid):
    """コンテンツとプレビューファイルの削除テスト"""
    # Setup: Save content and create a dummy preview file
    content_to_save = sample_content.copy()
    content_to_save["resources"] = { "images": [{"url": "image.jpg", "webp_data": b"webp data"}]}
    random_url = save_content(content_to_save, db_path=test_db)
    preview_filename = sample_content["preview_filename"]
    preview_dir = "previews"
    if not os.path.exists(preview_dir): os.makedirs(preview_dir)
    dummy_preview_path = os.path.join(preview_dir, preview_filename)
    with open(dummy_preview_path, 'w') as f: f.write('dummy')

    mock_exists.return_value = True # Assume file exists for the mock

    # Action: Delete the content
    delete_content(random_url, db_path=test_db)

    # Assert: Check DB record is deleted
    with pytest.raises(Exception) as exc_info:
        get_content(random_url, db_path=test_db)
    assert "Content not found" in str(exc_info.value)

    # Assert: Check os.remove was called for the preview file
    # Use assert_called_with to check the specific call inside delete_content
    mock_exists.assert_called_with(dummy_preview_path)
    mock_remove.assert_called_with(dummy_preview_path)
    # Check that remove was called only once (implicitly by assert_called_with if strict)
    # Or explicitly check call count if needed after ensuring the right call happened.
    # assert mock_remove.call_count == 1 # Might be too strict depending on setup

    # Cleanup dummy file if mock didn't actually remove it
    if os.path.exists(dummy_preview_path): os.remove(dummy_preview_path)
