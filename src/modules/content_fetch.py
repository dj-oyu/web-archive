import requests
from bs4 import BeautifulSoup
from io import BytesIO
from PIL import Image
import urllib.parse

def fetch_content(url):
    """指定されたURLからコンテンツを取得し、構造化したデータを返す"""
    if not url.startswith(('http://', 'https://')):
        raise ValueError("Invalid URL format. URL must start with http:// or https://")
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to fetch content from {url}: {str(e)}")

    html_content = response.text
    resources = parse_html_resources(html_content, base_url=url)
    
    # CSS, JSを取得
    for css in resources["css"]:
        try:
            css_url = urllib.parse.urljoin(url, css["url"])
            css_response = requests.get(css_url, timeout=5)
            css_response.raise_for_status()
            css["content"] = css_response.text
        except requests.exceptions.RequestException:
            css["content"] = ""

    for js in resources["js"]:
        try:
            js_url = urllib.parse.urljoin(url, js["url"])
            js_response = requests.get(js_url, timeout=5)
            js_response.raise_for_status()
            js["content"] = js_response.text
        except requests.exceptions.RequestException:
            js["content"] = ""

    # 画像を取得し、WebPに変換
    for img in resources["images"]:
        try:
            img_url = urllib.parse.urljoin(url, img["url"])
            img_response = requests.get(img_url, timeout=5)
            img_response.raise_for_status()
            img["webp_data"] = convert_to_webp(img_response.content)
        except (requests.exceptions.RequestException, Exception):
            img["webp_data"] = b""

    return {
        "html_content": html_content,
        "resources": {
            "css": resources["css"],
            "js": resources["js"],
            "images": resources["images"]
        }
    }

def parse_html_resources(html_content, base_url=""):
    """HTMLからCSS, JS, 画像のURLを抽出する"""
    soup = BeautifulSoup(html_content, 'html.parser')
    resources = {
        "css": [],
        "js": [],
        "images": []
    }

    # CSSリンクを抽出
    for link in soup.find_all('link', rel='stylesheet'):
        href = link.get('href', '')
        if href:
            resources["css"].append({"url": href, "content": ""})

    # JavaScriptスクリプトを抽出
    for script in soup.find_all('script', src=True):
        src = script.get('src', '')
        if src:
            resources["js"].append({"url": src, "content": ""})

    # 画像を抽出
    for img in soup.find_all('img', src=True):
        src = img.get('src', '')
        if src:
            resources["images"].append({"url": src, "webp_data": b""})

    return resources

def convert_to_webp(image_data):
    """画像データをWebP形式に変換する"""
    try:
        img = Image.open(BytesIO(image_data))
        output = BytesIO()
        img.save(output, format="WEBP", quality=80)
        return output.getvalue()
    except Exception as e:
        raise Exception(f"Failed to convert image to WebP: {str(e)}")
