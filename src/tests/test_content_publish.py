import pytest
from unittest.mock import patch
import sys
import os

# モジュールのインポートパスを追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'modules')))
from content_publish import render_content

@pytest.fixture
def sample_content():
    """テスト用のサンプルコンテンツ"""
    return {
        "html_content": """
        <html>
        <head>
            <link rel="stylesheet" href="style.css">
            <script src="script.js"></script>
        </head>
        <body>
            <img src="image.jpg">
        </body>
        </html>
        """,
        "resources": {
            "css": [{"url": "style.css", "content": "body { color: black; }"}],
            "js": [{"url": "script.js", "content": "console.log('test');"}],
            "images": [{"url": "image.jpg", "webp_data": b"webp data"}]
        }
    }

def test_render_content_success(sample_content):
    """コンテンツレンダリングが成功する場合のテスト"""
    # Pass a dummy random_url for testing
    rendered_html = render_content(sample_content, "dummy-random-url")
    assert isinstance(rendered_html, str)
    assert "<html>" in rendered_html
    # Update assertions to include the dummy random_url in the expected href/src
    assert 'href="/resource/dummy-random-url/css/0"' in rendered_html
    assert 'src="/resource/dummy-random-url/js/0"' in rendered_html
    assert 'src="/resource/dummy-random-url/image/0"' in rendered_html

def test_render_content_empty_resources():
    # Use partial matching due to potential reformatting by BeautifulSoup
    """リソースが空の場合のコンテンツレンダリングのテスト"""
    content = {
        "html_content": "<html><body>No resources</body></html>",
        "resources": {
            "css": [],
            "js": [],
            "images": []
        }
    }
    # Pass a dummy random_url
    rendered_html = render_content(content, "dummy-empty-url")
    assert isinstance(rendered_html, str)
    assert "<html>" in rendered_html
    assert "No resources" in rendered_html
    assert "/resource/" not in rendered_html

def test_render_content_invalid_html():
    """無効なHTMLの場合のコンテンツレンダリングのテスト"""
    content = {
        "html_content": "Invalid HTML",
        "resources": {
            "css": [],
            "js": [],
            "images": []
        }
    }
    # BeautifulSoup might not raise an exception for simple invalid strings
    # Instead, check if the output is just the input string
    # Pass a dummy random_url
    rendered_html = render_content(content, "dummy-invalid-url")
    # The function should still return the original invalid HTML string
    # because parsing happens before URL rewriting.
    # If parsing failed, it would raise an exception (which we removed the check for).
    # If parsing succeeds (even with invalid HTML), it proceeds, finds no tags to rewrite,
    # and returns the stringified soup, which for a simple string is the string itself.
    assert rendered_html == "Invalid HTML"
