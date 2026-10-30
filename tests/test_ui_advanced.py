"""UI 层高级场景：未登录跳转、越权拦截、禁用账号、连续失败锁定。

这些场景的共同点：**状态在数据库里，表现要回到页面上验证**。
所以每个用例都是「准备数据 → 操作界面 → 断言页面 + 断言数据库」。
"""

from __future__ import annotations

import uuid

import pytest
from playwright.sync_api import expect

from pages.login_page import LoginPage

pytestmark = pytest.mark.ui


def add_user(db_conn, *, role: str = "user", status: str = "active", password: str = "123456") -> tuple[int, str]:
    """直接写库造数据，返回 (id, username)。

    走 UI 造数太慢、且会被"新增页"本身的缺陷干扰；状态类数据用 SQL 更直接。
    """
    username = f"ui_{uuid.uuid4().hex[:8]}"
    db_conn.execute(
        "INSERT INTO users (username, email, age, password, role, status) VALUES (?, ?, ?, ?, ?, ?)",
        (username, f"{username}@example.com", 20, password, role, status),
    )
    row = db_conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    return int(row[0]), username


def user_id_of(db_conn, username: str) -> int | None:
    row = db_conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    return int(row[0]) if row else None


def login(page, base_url: str, username: str, password: str, *, expect_success: bool = True) -> LoginPage:
    login_page = LoginPage(page)
    login_page.navigate()
    login_page.login(username, password, expect_success=expect_success)
    return login_page


def test_anonymous_redirected_to_login(page, base_url: str) -> None:
    page.goto(f"{base_url}/users")
    expect(page).to_have_url(f"{base_url}/login")


def test_normal_user_cannot_delete(page, db_conn, base_url: str) -> None:
    """普通用户点删除：应被拦下，且目标用户仍然存在。"""
    actor_id, actor_name = add_user(db_conn, role="user")
    target_id, target_name = add_user(db_conn, role="user")

    login(page, base_url, actor_name, "123456")
    page.goto(f"{base_url}/user/delete/{target_id}")

    expect(page.locator("body")).to_contain_text("没有权限删除用户")
    assert user_id_of(db_conn, target_name) is not None, "越权删除成功了，这是严重缺陷"


def test_admin_can_delete(page, db_conn, base_url: str) -> None:
    target_id, target_name = add_user(db_conn, role="user")

    login(page, base_url, "admin", "123456")
    page.goto(f"{base_url}/user/delete/{target_id}")

    expect(page.locator("body")).to_contain_text("用户已删除")
    assert user_id_of(db_conn, target_name) is None


def test_disabled_user_cannot_login(page, db_conn, base_url: str) -> None:
    _, username = add_user(db_conn, status="disabled")

    login_page = login(page, base_url, username, "123456", expect_success=False)

    assert "账号已被禁用" in login_page.flash_text()


def test_account_locked_after_three_failures(page, db_conn, base_url: str) -> None:
    """连续 3 次密码错误 → 锁定；锁定期内即使密码正确也不能登录。"""
    _, username = add_user(db_conn)

    login_page = LoginPage(page)
    login_page.navigate()

    for attempt in range(1, 4):
        login_page.login(username, "wrong-password", expect_success=False)

    assert "锁定" in login_page.flash_text(), "第 3 次失败后应提示锁定"

    # 锁定期内用正确密码
    login_page.login(username, "123456", expect_success=False)
    assert "账号已锁定" in login_page.flash_text()

    # 数据库也应记录锁定状态
    row = db_conn.execute("SELECT login_attempts, lock_until FROM users WHERE username = ?", (username,)).fetchone()
    assert row[0] >= 3
    assert row[1] is not None
