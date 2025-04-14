from playwright.async_api import async_playwright
import os
import asyncio

PREVIEW_DIR = os.environ.get("WEB_ARCHIVE_PREVIEW_DIR", "previews")
PREVIEW_WIDTH = 1024
PREVIEW_HEIGHT = 768

async def generate_preview(url: str, output_filename: str):
    """指定されたURLのスクリーンショットを生成し、指定されたファイル名で保存する"""
    if not os.path.exists(PREVIEW_DIR):
        os.makedirs(PREVIEW_DIR)

    output_path = os.path.join(PREVIEW_DIR, output_filename)

    async with async_playwright() as p:
        # Try chromium first, fallback to firefox if needed
        browser = None
        try:
            browser = await p.chromium.launch()
        except Exception:
            print("Chromium launch failed, trying Firefox.")
            try:
                browser = await p.firefox.launch()
            except Exception as e_ff:
                print(f"Firefox launch also failed: {e_ff}")
                raise Exception("Could not launch any browser (Chromium, Firefox)")

        if browser is None:
             raise Exception("Browser could not be launched.")

        page = await browser.new_page()
        try:
            await page.set_viewport_size({"width": PREVIEW_WIDTH, "height": PREVIEW_HEIGHT})
            # Increase timeout for potentially slow-loading archived pages
            await page.goto(url, timeout=60000)
            # Wait for network idle to ensure resources are loaded
            await page.wait_for_load_state('networkidle', timeout=30000)
            await page.screenshot(path=output_path, type="jpeg", quality=80)
        except Exception as e:
            print(f"Error taking screenshot for {url}: {e}")
            # Optionally, create a placeholder image or log the error
            # For now, just raise the exception
            raise
        finally:
            await browser.close()

    return output_filename

# Example usage (for testing purposes)
async def main():
    filename = await generate_preview("http://localhost:8000/view/some-random-url", "preview_test.jpg")
    print(f"Preview saved as: {filename}")

if __name__ == "__main__":
    # This part is for manual testing, requires the server to be running
    # and a valid random_url to exist.
    # Replace 'some-random-url' with an actual random_url from your DB.
    # asyncio.run(main())
    pass
