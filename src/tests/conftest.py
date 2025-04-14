import os
import pytest

@pytest.fixture(autouse=True, scope="session")
def set_test_db_env(tmp_path_factory):
    """全テストでWEB_ARCHIVE_DB_PATHとWEB_ARCHIVE_PREVIEW_DIRをテスト用に切り替える"""
    test_db_path = str(tmp_path_factory.mktemp("data") / "test_web_archive.db")
    test_preview_dir = str(tmp_path_factory.mktemp("previews"))
    old_db_env = os.environ.get("WEB_ARCHIVE_DB_PATH")
    old_preview_env = os.environ.get("WEB_ARCHIVE_PREVIEW_DIR")
    os.environ["WEB_ARCHIVE_DB_PATH"] = test_db_path
    os.environ["WEB_ARCHIVE_PREVIEW_DIR"] = test_preview_dir
    yield
    if old_db_env is not None:
        os.environ["WEB_ARCHIVE_DB_PATH"] = old_db_env
    else:
        del os.environ["WEB_ARCHIVE_DB_PATH"]
    if old_preview_env is not None:
        os.environ["WEB_ARCHIVE_PREVIEW_DIR"] = old_preview_env
    else:
        del os.environ["WEB_ARCHIVE_PREVIEW_DIR"]
