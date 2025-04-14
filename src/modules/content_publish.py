from bs4 import BeautifulSoup

def render_content(content, random_url): # random_url を引数に追加
    """コンテンツデータをHTMLとしてレンダリングし、関連リソースをリンクした文字列を返す"""
    html_content = content.get("html_content", "")
    resources = content.get("resources", {"css": [], "js": [], "images": []})

    try:
        soup = BeautifulSoup(html_content, 'html.parser')
    except Exception as e:
        raise Exception(f"Failed to parse HTML content: {str(e)}")

    # CSSリンクを内部URLに書き換える
    for i, css in enumerate(resources.get("css", [])):
        # 元のURLが空でないことを確認
        original_url = css.get("url")
        if original_url:
            for link in soup.find_all('link', rel='stylesheet', href=original_url):
                link['href'] = f"/resource/{random_url}/css/{i}" # random_url を含める

    # JavaScriptリンクを内部URLに書き換える
    for i, js in enumerate(resources.get("js", [])):
        # 元のURLが空でないことを確認
        original_url = js.get("url")
        if original_url:
            for script in soup.find_all('script', src=original_url):
                script['src'] = f"/resource/{random_url}/js/{i}" # random_url を含める

    # 画像リンクを内部URLに書き換える
    for i, img in enumerate(resources.get("images", [])):
        # 元のURLが空でないことを確認
        original_url = img.get("url")
        if original_url:
            for image in soup.find_all('img', src=original_url):
                image['src'] = f"/resource/{random_url}/image/{i}" # random_url を含める

    return str(soup)
