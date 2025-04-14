import pytest
import requests
from unittest.mock import patch, Mock
import sys
import os

# モジュールのインポートパスを追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'modules')))
from content_fetch import fetch_content, parse_html_resources, convert_to_webp

@pytest.fixture
def mock_requests_get():
    """requests.getのモック"""
    with patch('requests.get') as mock:
        mock_response = Mock()
        mock_response.text = """
        <html>
        <head>
            <link rel="stylesheet" href="style.css">
            <script src="script.js"></script>
        </head>
        <body>
            <img src="image.jpg">
        </body>
        </html>
        """
        mock_response.content = b"image data"
        mock.return_value = mock_response
        yield mock

@pytest.fixture
def mock_pillow_image():
    """PillowのImageモック"""
    with patch('PIL.Image.open') as mock_open:
        mock_image = Mock()
        mock_open.return_value = mock_image
        mock_image.save = Mock()
        yield mock_image

def test_fetch_content_success(mock_requests_get):
    """コンテンツ取得が成功する場合のテスト"""
    result = fetch_content("https://example.com")
    assert "html_content" in result
    assert "resources" in result
    assert "css" in result["resources"]
    assert "js" in result["resources"]
    assert "images" in result["resources"]
    mock_requests_get.assert_called()
    assert result["html_content"].strip().startswith("<html>")

def test_fetch_content_request_failure(mock_requests_get):
    """リクエストが失敗する場合のテスト"""
    mock_requests_get.side_effect = requests.exceptions.RequestException("Request failed")
    with pytest.raises(Exception) as exc_info:
        fetch_content("https://example.com")
    # Check if the actual exception message contains the expected parts
    assert "Failed to fetch content from https://example.com" in str(exc_info.value)
    assert "Request failed" in str(exc_info.value)

def test_parse_html_resources():
    """HTMLリソース解析のテスト"""
    html_content = """
    <html>
    <head>
        <link rel="stylesheet" href="style.css">
        <script src="script.js"></script>
    </head>
    <body>
        <img src="image.jpg">
    </body>
    </html>
    """
    resources = parse_html_resources(html_content)
    assert len(resources["css"]) == 1
    assert resources["css"][0]["url"] == "style.css" # Check the 'url' key
    assert len(resources["js"]) == 1
    assert resources["js"][0]["url"] == "script.js" # Check the 'url' key
    assert len(resources["images"]) == 1
    assert resources["images"][0]["url"] == "image.jpg" # Check the 'url' key

def test_convert_to_webp(mock_pillow_image):
    """WebP変換のテスト"""
    image_data = b"dummy image data"
    result = convert_to_webp(image_data)
    assert isinstance(result, bytes)
    mock_pillow_image.save.assert_called_once()
