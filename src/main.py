import uvicorn
import os
import sys

# モジュールのインポートパスを追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'modules')))
from web_interface import app

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
