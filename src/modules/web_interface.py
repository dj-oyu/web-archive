from fastapi import FastAPI, HTTPException, Response, Request, status, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from sse_starlette.sse import EventSourceResponse # Import SSE
from pydantic import BaseModel
import os
import sys
import sqlite3
import html
import asyncio
import uuid
import json # Import json for SSE data

# モジュールのインポートパスを追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))
from content_fetch import fetch_content
from db_manager import save_content, get_content, delete_content, init_database, DB_PATH
from content_publish import render_content
from preview_generator import generate_preview, PREVIEW_DIR

app = FastAPI()

# --- Preview Generation & SSE Notification ---
preview_queue = asyncio.Queue()
sse_notification_queue = asyncio.Queue()
MAX_CONCURRENT_PREVIEWS = 1
preview_worker_tasks = []

async def preview_worker():
    """Worker task to process preview generation queue sequentially."""
    print("Preview worker started.")
    while True:
        try:
            view_url, preview_filename, random_url = await preview_queue.get()
            print(f"Worker processing preview for {random_url}...")
            success = False
            try:
                await generate_preview(view_url, preview_filename)
                print(f"Preview generated successfully for {random_url}: {preview_filename}")
                # Update the database record
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("UPDATE archives SET preview_filename = ? WHERE random_url = ?", (preview_filename, random_url))
                conn.commit()
                conn.close()
                print(f"Database updated with preview filename for {random_url}")
                success = True
            except Exception as e:
                print(f"Failed to generate preview for {random_url}: {e}")
                try:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute("UPDATE archives SET preview_filename = NULL WHERE random_url = ?", (random_url,))
                    conn.commit()
                    conn.close()
                    print(f"Set preview_filename to NULL for {random_url} due to generation error.")
                except Exception as db_e:
                     print(f"Error updating DB after preview failure for {random_url}: {db_e}")
            finally:
                preview_queue.task_done()
                print(f"Worker finished processing preview for {random_url}.")
                # Notify SSE clients ONLY if successful
                if success:
                    # Send data in the format expected by EventSourceResponse
                    await sse_notification_queue.put({
                        "event": "preview_ready",
                        "data": json.dumps({"random_url": random_url, "preview_filename": preview_filename})
                    })

        except asyncio.CancelledError:
             print("Preview worker cancelled.")
             break
        except Exception as e:
            print(f"Error in preview worker loop: {e}")
            await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    """Start the preview worker task on application startup."""
    init_database()
    global preview_worker_tasks
    preview_worker_tasks = []
    for i in range(MAX_CONCURRENT_PREVIEWS):
        task = asyncio.create_task(preview_worker())
        preview_worker_tasks.append(task)
        print(f"Started preview worker {i+1}/{MAX_CONCURRENT_PREVIEWS}")

@app.on_event("shutdown")
async def shutdown_event():
    """Cancel preview worker tasks and all asyncio tasks on shutdown (for graceful exit with Ctrl+C)"""
    global preview_worker_tasks
    for task in preview_worker_tasks:
        task.cancel()
    await asyncio.gather(*preview_worker_tasks, return_exceptions=True)
    print("All preview worker tasks cancelled.")

    # 追加: asyncioの全タスクをキャンセル
    current_task = asyncio.current_task()
    all_tasks = [t for t in asyncio.all_tasks() if t is not current_task]
    for t in all_tasks:
        t.cancel()
    await asyncio.gather(*all_tasks, return_exceptions=True)
    print("All asyncio tasks cancelled.")

class ArchiveRequest(BaseModel):
    url: str

@app.get("/", response_class=HTMLResponse)
async def root():
    """ルートエンドポイント。URL入力フォームとアーカイブ一覧（プレビュー付き、表示切替可能）を提供"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT random_url, original_url, created_at, preview_filename FROM archives ORDER BY created_at DESC")
    archives = cursor.fetchall()
    conn.close()

    archive_list_items_html = ""
    if archives:
        for random_url, original_url, created_at, preview_filename in archives:
            safe_original_url = html.escape(original_url)
            safe_created_at = html.escape(str(created_at))
            preview_html = ""
            indicator_html = ""
            li_attrs = f'data-random-url="{random_url}"'

            if preview_filename:
                preview_path = os.path.join(PREVIEW_DIR, preview_filename)
                if os.path.exists(preview_path):
                    preview_html = f'<img src="/preview/{preview_filename}" alt="Preview of {safe_original_url}" loading="lazy">'
                else:
                    indicator_html = '<span class="preview-indicator preview-error">Preview failed</span>'
            else:
                 indicator_html = '<span class="preview-indicator">Generating preview...</span>'

            archive_list_items_html += f'''
                <li {li_attrs}>
                    <div class="archive-info">
                        <a href="/view/{random_url}" target="_blank">{safe_original_url}</a>
                        <span class="archive-date">(Archived: {safe_created_at})</span>
                        <button class="delete-button" onclick="deleteArchive('{random_url}')">Delete</button>
                    </div>
                    <div class="archive-preview">
                        {preview_html}
                        {indicator_html}
                    </div>
                </li>
            '''
    else:
        archive_list_items_html = "<li>No pages archived yet.</li>"

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Web Archive</title>
        <meta charset="UTF-8">
        <style>
             body {{ font-family: sans-serif; }}
            #archive-list ul {{ list-style: none; padding: 0; }}
            #archive-list li {{
                border: 1px solid #eee; margin-bottom: 10px; padding: 10px;
                display: flex; flex-direction: column; background-color: #f9f9f9; border-radius: 4px;
            }}
            .archive-info {{ display: flex; align-items: center; flex-wrap: wrap; margin-bottom: 5px; }}
            .archive-info a {{ margin-right: 10px; word-break: break-all; flex-grow: 1; }}
            .archive-date {{ font-size: 0.9em; color: #666; margin-right: 10px; white-space: nowrap; }}
            .delete-button {{ margin-left: auto; cursor: pointer; padding: 3px 8px; font-size: 0.9em; background-color: #ffdddd; border: 1px solid #ffaaaa; border-radius: 3px; }}
            .delete-button:hover {{ background-color: #ffcccc; }}
            .archive-preview img {{ display: none; max-width: 100%; height: auto; border: 1px solid #ccc; margin-top: 10px; }}
            .preview-indicator {{ display: none; font-style: italic; color: #888; font-size: 0.9em; margin-top: 10px; }}
            .preview-error {{ color: red; font-style: normal; font-weight: bold; }}
            #archive-list.grid-view ul {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 15px; }}
            #archive-list.grid-view li {{ flex-direction: column; align-items: center; text-align: center; }}
            #archive-list.grid-view .archive-info {{ flex-direction: column; align-items: center; margin-bottom: 10px; }}
            #archive-list.grid-view .archive-info a {{ margin-right: 0; margin-bottom: 5px; }}
            #archive-list.grid-view .archive-date {{ margin-right: 0; margin-bottom: 5px; }}
            #archive-list.grid-view .delete-button {{ margin-left: 0; }}
            #archive-list.grid-view .archive-preview img,
            #archive-list.grid-view .archive-preview .preview-indicator {{ display: block; max-width: 200px; max-height: 150px; }}
            #archive-list.list-view .archive-preview img {{ display: none; }}
            #archive-list.list-view .archive-preview .preview-indicator {{ display: block; }}
            .view-toggle button {{ margin: 0 5px; padding: 5px 10px; cursor: pointer; }}
            .view-toggle button.active {{ background-color: #ddd; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h1>Web Archive</h1>
        <form id="archive-form">
            <label for="url">URL to Archive:</label>
            <input type="text" id="url" name="url" size="50" placeholder="https://example.com">
            <button type="submit">Archive</button>
        </form>
        <hr>
        <div class="view-toggle">
            View:
            <button id="list-view-btn" onclick="setView('list-view')">List</button>
            <button id="grid-view-btn" onclick="setView('grid-view')">Grid</button>
        </div>
        <div id="archive-list">
            <h2>Archived Pages</h2>
            <ul>{archive_list_items_html}</ul>
        </div>

        <script>
            document.getElementById('archive-form').onsubmit = async (e) => {{
                e.preventDefault();
                const urlInput = document.getElementById('url');
                const url = urlInput.value;
                const submitButton = e.target.querySelector('button[type="submit"]');
                submitButton.disabled = true;
                submitButton.textContent = 'Archiving...';

                try {{
                    const response = await fetch('/archive', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ url }}),
                    }});
                    const result = await response.json();
                    if (response.ok && result.status === 'success') {{
                        alert(`Archived successfully! Access it at: /view/${{result.random_url}}. Preview generation queued.`);
                        urlInput.value = '';
                        setTimeout(() => window.location.reload(), 500);
                    }} else {{
                        const errorMessage = result.detail?.message || result.message || 'Unknown error';
                        alert(`Failed to archive: ${{errorMessage}}`);
                    }}
                }} catch (error) {{
                    console.error('Error submitting archive request:', error);
                    alert('An error occurred while submitting the archive request.');
                }} finally {{
                     submitButton.disabled = false;
                     submitButton.textContent = 'Archive';
                }}
            }};

            async function deleteArchive(randomUrl) {{
                if (!confirm('Are you sure you want to delete this archive and its preview?')) return;
                try {{
                    const response = await fetch(`/delete/${{randomUrl}}`, {{ method: 'DELETE' }});
                    const result = await response.json();
                    if (response.ok && result.status === 'success') {{
                        alert('Archive deleted successfully.');
                        window.location.reload();
                    }} else {{
                         const errorMessage = result.detail?.message || result.message || 'Unknown error';
                        alert(`Failed to delete archive: ${{errorMessage}}`);
                    }}
                }} catch (error) {{
                    console.error('Error deleting archive:', error);
                    alert('An error occurred while deleting the archive.');
                }}
            }}

            const archiveListDiv = document.getElementById('archive-list');
            const listViewBtn = document.getElementById('list-view-btn');
            const gridViewBtn = document.getElementById('grid-view-btn');

            function setView(viewType) {{
                localStorage.setItem('archiveView', viewType);
                archiveListDiv.className = viewType;
                listViewBtn.classList.toggle('active', viewType === 'list-view');
                gridViewBtn.classList.toggle('active', viewType === 'grid-view');
            }}

            const savedView = localStorage.getItem('archiveView') || 'list-view';
            setView(savedView);

            // --- SSE Logic ---
            console.log('Connecting to SSE endpoint...');
            const eventSource = new EventSource('/sse/preview-status');

            // Listen specifically for the 'preview_ready' event
            eventSource.addEventListener('preview_ready', function(event) {{
                console.log("SSE preview_ready event received:", event.data);
                try {{
                    const eventData = JSON.parse(event.data); // Data is already JSON stringified by server
                    const randomUrl = eventData.random_url;
                    const previewFilename = eventData.preview_filename;

                    console.log(`Preview ready for: ${{randomUrl}}`);
                    const archiveItem = document.querySelector(`li[data-random-url="${{randomUrl}}"]`);
                    if (archiveItem) {{
                        const previewDiv = archiveItem.querySelector('.archive-preview');
                        const indicator = previewDiv.querySelector('.preview-indicator');
                        if (indicator) {{
                            indicator.remove();
                        }}
                        const existingImg = previewDiv.querySelector('img');
                        if(existingImg) {{ existingImg.remove(); }}

                        const img = document.createElement('img');
                        img.src = `/preview/${{previewFilename}}`;
                        img.alt = `Preview`;
                        img.loading = 'lazy';
                        previewDiv.appendChild(img);
                        console.log(`UI updated for: ${{randomUrl}}`);
                    }} else {{
                         console.log(`List item not found for: ${{randomUrl}}`);
                    }}
                }} catch (e) {{
                    console.error("Error processing SSE message:", e);
                }}
            }});

            eventSource.onerror = function(err) {{
                console.error("EventSource failed:", err);
                eventSource.close();
            }};

        </script>
    </body>
    </html>
    """

@app.post("/archive")
async def archive(archive_request: ArchiveRequest):
    """URLを受け取り、アーカイブ処理を開始し、プレビュー生成タスクをキューに追加"""
    url = archive_request.url
    if not url.startswith(('http://', 'https://')):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"status": "error", "message": "Invalid URL format"})

    try:
        print(f"Fetching content for {url}...")
        content = fetch_content(url)
        content["original_url"] = url
        preview_filename = f"{uuid.uuid4()}.jpg"
        content["preview_filename"] = None # Set to None initially

        print(f"Saving content for {url} (preview will be generated)...")
        random_url = save_content(content)

        view_url = f"http://localhost:8000/view/{random_url}"
        await preview_queue.put((view_url, preview_filename, random_url))
        print(f"Preview task for {random_url} (file: {preview_filename}) added to queue.")

        print(f"Archive successful for {url}, random_url: {random_url}.")
        return JSONResponse(content={"status": "success", "random_url": random_url}, status_code=status.HTTP_200_OK)
    except Exception as e:
        print(f"Error during archiving {url}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"status": "error", "message": str(e)})


@app.delete("/delete/{random_url}")
async def delete_archive(random_url: str):
    """指定されたrandom_urlに対応するアーカイブとプレビューファイルを削除する"""
    try:
        delete_content(random_url)
        return JSONResponse(content={"status": "success", "message": "Archive deleted successfully"}, status_code=status.HTTP_200_OK)
    except Exception as e:
        print(f"Error deleting archive {random_url}: {e}")
        if "No content found to delete" in str(e):
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"status": "error", "message": str(e)})
        else:
             raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail={"status": "error", "message": str(e)})


@app.get("/view/{random_url}", response_class=HTMLResponse)
async def view(random_url: str):
    """保存したコンテンツをランダムURLで表示"""
    try:
        content = get_content(random_url)
        rendered_html = render_content(content, random_url)
        return rendered_html
    except Exception as e:
        print(f"Error viewing content {random_url}: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"status": "error", "message": str(e)})

@app.get("/resource/{random_url}/{resource_type}/{index}")
async def serve_resource(random_url: str, resource_type: str, index: int):
    """リソース（CSS, JS, 画像）を返す"""
    try:
        content = get_content(random_url)
        resources = content.get("resources", {})
        if resource_type == "css":
            resource_list = resources.get("css", [])
            if 0 <= index < len(resource_list):
                return Response(content=resource_list[index].get("content", ""), media_type="text/css")
        elif resource_type == "js":
            resource_list = resources.get("js", [])
            if 0 <= index < len(resource_list):
                return Response(content=resource_list[index].get("content", ""), media_type="application/javascript")
        elif resource_type == "image":
            resource_list = resources.get("images", [])
            if 0 <= index < len(resource_list):
                webp_data = resource_list[index].get("webp_data")
                if isinstance(webp_data, bytes):
                    return Response(content=webp_data, media_type="image/webp")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found or invalid")
    except Exception as e:
        print(f"Error serving resource {resource_type}/{index} for {random_url}: {e}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@app.get("/preview/{preview_filename}")
async def serve_preview(preview_filename: str):
    """プレビュー画像を返す"""
    preview_path = os.path.join(PREVIEW_DIR, preview_filename)
    if os.path.exists(preview_path):
        return FileResponse(preview_path, media_type="image/jpeg")
    else:
        print(f"Preview image not found at path: {preview_path}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preview image not found")

# --- SSE Endpoint ---
@app.get("/sse/preview-status")
async def preview_status_sse(request: Request):
    """SSEエンドポイント。プレビュー完了イベントをクライアントに送信"""
    async def event_generator():
        while True:
            try:
                if await request.is_disconnected():
                    print("SSE client disconnected.")
                    break
                notification = await sse_notification_queue.get()
                # Send data in the format EventSourceResponse expects
                yield {
                    "event": notification.get("event", "message"),
                    "data": notification.get("data", "")
                 }
                sse_notification_queue.task_done()
            except asyncio.CancelledError:
                print("SSE event_generator cancelled.")
                break
            except Exception as e:
                print(f"Error in SSE event_generator: {e}")
                await asyncio.sleep(1)
    return EventSourceResponse(event_generator())

# Ensure there's a newline at the end
