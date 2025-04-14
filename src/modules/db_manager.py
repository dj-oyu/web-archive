import sqlite3
import json
import uuid
from datetime import datetime
import os
import base64 # Base64をインポート
import time # Import time for sleep

DB_PATH = os.environ.get("WEB_ARCHIVE_DB_PATH", "web_archive.db")
MAX_RETRIES = 10 # Define max retries for URL generation
RETRY_DELAY = 3.0 # Increase delay between retries to 3 seconds

def init_database(db_path=None):
    """データベースとテーブルを初期化する"""
    if db_path is None:
        db_path = os.environ.get("WEB_ARCHIVE_DB_PATH", "web_archive.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS archives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            random_url TEXT UNIQUE NOT NULL,
            original_url TEXT NOT NULL,
            html_content TEXT NOT NULL,
            resources TEXT NOT NULL,
            preview_filename TEXT, -- Add column for preview image filename
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Basic check for existing column to avoid errors if run multiple times
    # A more robust migration strategy would be needed for production
    try:
        cursor.execute("SELECT preview_filename FROM archives LIMIT 1")
    except sqlite3.OperationalError:
        print("Adding preview_filename column to archives table.")
        cursor.execute("ALTER TABLE archives ADD COLUMN preview_filename TEXT")

    conn.commit()
    conn.close()

def generate_random_url():
    """一意のランダムURLを生成する"""
    return str(uuid.uuid4())

def save_content(content, db_path=None):
    """コンテンツをデータベースに保存し、対応するランダムURLを返す"""
    if db_path is None:
        db_path = os.environ.get("WEB_ARCHIVE_DB_PATH", "web_archive.db")
    original_url = content.get("original_url", "")
    html_content = content.get("html_content", "")
    
    # リソース内の画像データをBase64エンコード
    resources_to_save = content.get("resources", {})
    if "images" in resources_to_save:
        for img in resources_to_save["images"]:
            if isinstance(img.get("webp_data"), bytes):
                img["webp_data_b64"] = base64.b64encode(img["webp_data"]).decode('utf-8')
                del img["webp_data"] # 元のバイトデータは削除

    resources_json = json.dumps(resources_to_save)
    created_at = datetime.now().isoformat()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    inserted = False
    retries = 0
    random_url = "" # Initialize random_url

    while not inserted and retries < MAX_RETRIES:
        random_url = generate_random_url() # Generate URL inside the loop
        try:
            cursor.execute('''
                INSERT INTO archives (random_url, original_url, html_content, resources, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (random_url, original_url, html_content, resources_json, created_at))
            conn.commit()
            inserted = True # Exit loop if insertion is successful
        except sqlite3.IntegrityError:
            # URL collision, loop will generate a new one and retry
            retries += 1
            print(f"URL collision for {random_url}, retrying ({retries}/{MAX_RETRIES})...")
            time.sleep(RETRY_DELAY) # Wait 1 second before retrying
            pass # Continue loop
        except Exception as e:
             conn.rollback()
             conn.close()
             raise e # Re-raise other exceptions

    if not inserted:
        conn.close()
        raise Exception(f"Failed to generate a unique random_url after {MAX_RETRIES} retries.")

    # Save preview filename (assuming it's passed in the content dict)
    preview_filename = content.get("preview_filename")

    # Update the record with the preview filename
    # This assumes the initial insert without preview_filename succeeded
    if preview_filename:
        try:
            cursor.execute('''
                UPDATE archives SET preview_filename = ? WHERE random_url = ?
            ''', (preview_filename, random_url))
            conn.commit()
        except Exception as e:
            print(f"Error updating preview filename for {random_url}: {e}")
            conn.rollback()
            # Decide how to handle this error, maybe log it
            # For now, we still return the random_url as the content is saved
    
    conn.close() # Close connection after all operations

    return random_url

def get_content(random_url, db_path=DB_PATH):
    """ランダムURLを基に保存したコンテンツを取得する"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Select preview_filename as well
    cursor.execute('SELECT original_url, html_content, resources, preview_filename FROM archives WHERE random_url = ?', (random_url,))
    result = cursor.fetchone()
    conn.close()

    if result is None:
        raise Exception(f"Content not found for random_url: {random_url}")

    original_url, html_content, resources_json, preview_filename = result
    resources = json.loads(resources_json)
    
    # リソース内のBase64エンコードされた画像データをデコード
    if "images" in resources:
        for img in resources["images"]:
            if "webp_data_b64" in img:
                img["webp_data"] = base64.b64decode(img["webp_data_b64"])
                del img["webp_data_b64"] # デコード後のBase64データは削除

    return {
        "original_url": original_url,
        "html_content": html_content,
        "resources": resources,
        "preview_filename": preview_filename # Return preview filename
    }

def delete_content(random_url, db_path=DB_PATH):
    """指定されたrandom_urlに対応するアーカイブとプレビューファイルを削除する"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    preview_filename = None
    try:
        # First, get the preview filename
        cursor.execute('SELECT preview_filename FROM archives WHERE random_url = ?', (random_url,))
        result = cursor.fetchone()
        if result and result[0]:
            preview_filename = result[0]

        # Delete the database record
        cursor.execute('DELETE FROM archives WHERE random_url = ?', (random_url,))
        conn.commit()

        # Check if any row was deleted
        deleted_rows = cursor.rowcount
        if deleted_rows == 0:
            # If no rows were deleted, maybe the entry didn't exist
             pass # Or raise specific error? For now, just pass.

        # If a preview file exists, delete it
        if preview_filename:
            preview_dir = os.environ.get("WEB_ARCHIVE_PREVIEW_DIR", "previews")
            preview_path = os.path.join(preview_dir, preview_filename)
            if os.path.exists(preview_path):
                try:
                    os.remove(preview_path)
                    print(f"Deleted preview file: {preview_path}")
                except OSError as e_remove:
                    print(f"Error deleting preview file {preview_path}: {e_remove}")
                    # Decide if this should be a critical error

    except Exception as e:
        conn.rollback() # Roll back in case of error
        raise e # Re-raise the exception
    finally:
        conn.close()

# 初期化を保証
if not os.path.exists(DB_PATH):
    init_database()
