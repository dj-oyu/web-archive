import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import os
import sys
import asyncio

# モジュールのインポートパスを追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from modules.preview_generator import generate_preview, PREVIEW_DIR

# Fixture to ensure preview directory exists and is cleaned up
@pytest.fixture(scope="module", autouse=True)
def setup_preview_dir():
    if not os.path.exists(PREVIEW_DIR):
        os.makedirs(PREVIEW_DIR)
    yield
    # Clean up created files after tests in this module run
    if os.path.exists(PREVIEW_DIR):
        for f in os.listdir(PREVIEW_DIR):
            if f.startswith("test_"): # Only remove test files
                os.remove(os.path.join(PREVIEW_DIR, f))
        # Optionally remove dir if empty and owned by tests
        # try:
        #     os.rmdir(PREVIEW_DIR)
        # except OSError:
        #     pass # Ignore if not empty

@pytest.mark.asyncio
async def test_generate_preview_success():
    """プレビュー生成成功のテスト"""
    test_url = "http://example.com/test"
    test_filename = "test_success.jpg"
    expected_path = os.path.join(PREVIEW_DIR, test_filename)

    # Mock Playwright objects and methods
    mock_page = AsyncMock()
    mock_browser = AsyncMock()
    mock_browser.new_page.return_value = mock_page
    mock_playwright_context = AsyncMock()
    mock_playwright_context.chromium.launch.return_value = mock_browser
    # Simulate entering the async context manager
    mock_playwright_context.__aenter__.return_value = mock_playwright_context

    with patch('modules.preview_generator.async_playwright', return_value=mock_playwright_context):
        result_filename = await generate_preview(test_url, test_filename)

    assert result_filename == test_filename
    # Check if playwright methods were called correctly
    mock_playwright_context.chromium.launch.assert_called_once()
    mock_browser.new_page.assert_called_once()
    mock_page.set_viewport_size.assert_called_once()
    mock_page.goto.assert_called_once_with(test_url, timeout=60000)
    mock_page.wait_for_load_state.assert_called_once_with('networkidle', timeout=30000)
    mock_page.screenshot.assert_called_once_with(path=expected_path, type="jpeg", quality=80)
    mock_browser.close.assert_called_once()

@pytest.mark.asyncio
async def test_generate_preview_screenshot_failure():
    """スクリーンショット失敗時のテスト"""
    test_url = "http://example.com/fail"
    test_filename = "test_fail.jpg"

    mock_page = AsyncMock()
    mock_page.screenshot.side_effect = Exception("Screenshot failed") # Simulate failure
    mock_browser = AsyncMock()
    mock_browser.new_page.return_value = mock_page
    mock_playwright_context = AsyncMock()
    mock_playwright_context.chromium.launch.return_value = mock_browser
    mock_playwright_context.__aenter__.return_value = mock_playwright_context

    with patch('modules.preview_generator.async_playwright', return_value=mock_playwright_context):
        with pytest.raises(Exception, match="Screenshot failed"):
            await generate_preview(test_url, test_filename)

    # Ensure browser is still closed even on failure
    mock_browser.close.assert_called_once()

@pytest.mark.asyncio
async def test_generate_preview_browser_launch_fallback():
    """Chromium起動失敗時のFirefoxフォールバックテスト"""
    test_url = "http://example.com/fallback"
    test_filename = "test_fallback.jpg"
    expected_path = os.path.join(PREVIEW_DIR, test_filename)

    mock_page = AsyncMock()
    mock_ff_browser = AsyncMock()
    mock_ff_browser.new_page.return_value = mock_page
    mock_playwright_context = AsyncMock()
    mock_playwright_context.chromium.launch.side_effect = Exception("Chromium failed") # Simulate Chromium failure
    mock_playwright_context.firefox.launch.return_value = mock_ff_browser # Firefox succeeds
    mock_playwright_context.__aenter__.return_value = mock_playwright_context

    with patch('modules.preview_generator.async_playwright', return_value=mock_playwright_context):
        result_filename = await generate_preview(test_url, test_filename)

    assert result_filename == test_filename
    mock_playwright_context.chromium.launch.assert_called_once()
    mock_playwright_context.firefox.launch.assert_called_once() # Check Firefox was tried
    mock_ff_browser.new_page.assert_called_once()
    mock_page.screenshot.assert_called_once_with(path=expected_path, type="jpeg", quality=80)
    mock_ff_browser.close.assert_called_once()

@pytest.mark.asyncio
async def test_generate_preview_all_browsers_fail():
    """全ブラウザ起動失敗時のテスト"""
    test_url = "http://example.com/allfail"
    test_filename = "test_allfail.jpg"

    mock_playwright_context = AsyncMock()
    mock_playwright_context.chromium.launch.side_effect = Exception("Chromium failed")
    mock_playwright_context.firefox.launch.side_effect = Exception("Firefox failed") # Firefox also fails
    mock_playwright_context.__aenter__.return_value = mock_playwright_context

    with patch('modules.preview_generator.async_playwright', return_value=mock_playwright_context):
        with pytest.raises(Exception, match="Could not launch any browser"):
            await generate_preview(test_url, test_filename)

    mock_playwright_context.chromium.launch.assert_called_once()
    mock_playwright_context.firefox.launch.assert_called_once()
