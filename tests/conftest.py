"""pytest 全局配置：浏览器生命周期、多浏览器、失败截图、trace、数据库连接。

用法：
    pytest                                   # 默认 chromium
    BROWSERS=chromium,firefox pytest         # 双浏览器
    HEADED=1 pytest                          # 有头模式
    BASE_URL=http://127.0.0.1:5001 pytest    # 换端口

失败产物：
    artifacts/<用例>-<浏览器>-<时间>.png    失败截图
    artifacts/<用例>-<浏览器>-<时间>.zip    trace，用 `playwright show-trace` 打开
"""

from __future__ import annotations

import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
# 让用例可以直接 `from pages.xxx import ...`
sys.path.insert(0, str(Path(__file__).parent))

DB_PATH = ROOT / "users.db"
ARTIFACTS = ROOT / "artifacts"

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:5000").rstrip("/")
BROWSERS = [item.strip() for item in os.getenv("BROWSERS", "chromium").split(",") if item.strip()]
HEADLESS = os.getenv("HEADED", "0") != "1"
UI_TIMEOUT = int(os.getenv("UI_TIMEOUT_MS", "8000"))


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """把 ui_browser 参数化：BROWSERS=chromium,firefox 时同一批用例跑两遍。"""
    if "ui_browser" in metafunc.fixturenames:
        metafunc.parametrize("ui_browser", BROWSERS, scope="session")


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture(scope="session")
def db_conn():
    """测试库连接。isolation_level=None 即自动提交，避免 SQLite 写锁。"""
    conn = sqlite3.connect(DB_PATH, timeout=10, isolation_level=None)
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def cleanup_created_users(db_conn):
    """每条用例结束后，删除本次新建的用户。

    做法：用例前记录当前最大 id，用例后删除 id 更大的行。
    这样不管用例是走 UI 还是直接写库造的数据，都能被收干净，
    数据库不会随着执行次数无限膨胀。
    """
    baseline = int(db_conn.execute("SELECT COALESCE(MAX(id), 0) FROM users").fetchone()[0])
    yield
    db_conn.execute("DELETE FROM users WHERE id > ? AND username != 'admin'", (baseline,))


@pytest.fixture
def page(ui_browser: str, request: pytest.FixtureRequest):
    """每个用例一个干净的浏览器上下文；失败时自动截图并保留 trace。"""
    ARTIFACTS.mkdir(exist_ok=True)
    case = request.node.name.replace("/", "_").replace("::", "-")

    with sync_playwright() as p:
        browser = getattr(p, ui_browser).launch(headless=HEADLESS)
        context = browser.new_context()
        context.tracing.start(screenshots=True, snapshots=True, sources=False)
        page = context.new_page()
        page.set_default_timeout(UI_TIMEOUT)

        failed = False
        try:
            yield page
        except Exception:
            failed = True
            stamp = datetime.now().strftime("%H%M%S")
            try:
                page.screenshot(path=str(ARTIFACTS / f"{case}-{ui_browser}-{stamp}.png"), full_page=True)
            except Exception:
                pass
            try:
                context.tracing.stop(path=str(ARTIFACTS / f"{case}-{ui_browser}-{stamp}.zip"))
            except Exception:
                pass
            raise
        finally:
            if not failed:
                try:
                    context.tracing.stop()
                except Exception:
                    pass
            context.close()
            browser.close()
