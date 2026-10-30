import sys
import os
import uuid
sys.path.insert(0, os.path.dirname(__file__))

import time
import pytest
from pages.login_page import LoginPage
from pages.user_list_page import UserListPage
from pages.add_user_page import AddUserPage

BASE_URL = "http://127.0.0.1:5000"

def login(page, username="admin", password="123456"):
    login_page = LoginPage(page)
    login_page.navigate()
    login_page.login(username, password)
    return login_page

# 测试登录成功
def test_login_success(page):
    login(page)
    assert page.url == f"{BASE_URL}/users"

# 测试登录失败
def test_login_fail(page):
    login(page, username="admin", password="wrong")
    assert page.locator('text=用户名或密码错误').is_visible()

# 测试新增用户 + 数据库断言
def test_add_user(page, db_conn):
    login(page)
    list_page = UserListPage(page)
    list_page.click_add()
    add_page = AddUserPage(page)

    # 使用时间戳生成唯一用户名，避免重复
    username = f"testuser_{int(time.time())}"
    email = f"{username}@example.com"
    add_page.add_user(username, email, 25, "123456")

    # 等待列表页出现该用户名（使用更精确的表格行定位）
    page.wait_for_selector(f"tr:has-text('{username}')", timeout=5000)

    # UI 断言
    assert username in list_page.get_usernames()

    # 数据库断言
    cur = db_conn.cursor()
    cur.execute("SELECT * FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    assert row is not None
    assert row[2] == email
    assert row[3] == 25

# 测试重复用户名（数据库唯一约束）
def test_add_duplicate_user(page):
    login(page)
    list_page = UserListPage(page)
    list_page.click_add()
    add_page = AddUserPage(page)

    # 先添加一个新用户
    username = f"dup_{int(time.time())}"
    add_page.add_user(username, f"{username}@example.com", 30, "123456")
    page.wait_for_selector(f"tr:has-text('{username}')", timeout=5000)

    # 再次点击新增，尝试添加相同用户名
    list_page.click_add()   # 注意：此时已在列表页，需要重新进入添加页
    add_page = AddUserPage(page)
    add_page.add_user(username, "whatever@example.com", 30, "123456")

    # 等待错误提示出现（使用更精确的 li 定位）
    page.wait_for_selector("li:has-text('用户名已存在')", timeout=5000)

# 测试删除用户
def test_delete_user(page, db_conn):
    # 1. 直接在数据库插入测试用户
    username = f"del_{uuid.uuid4().hex[:8]}"
    cur = db_conn.cursor()
    cur.execute(
        "INSERT INTO users (username, email, age, password) VALUES (?, ?, ?, ?)",
        (username, f"{username}@example.com", 40, "123456")
    )

    # 2. 登录并跳转列表页
    login(page)
    page.goto("http://127.0.0.1:5000/users")
    page.wait_for_selector(f"tr:has-text('{username}')", timeout=5000)

    # 3. 删除该用户
    list_page = UserListPage(page)
    links = list_page.find_edit_delete(username)

    # 关键：自动接受确认弹窗
    page.on("dialog", lambda dialog: dialog.accept())
    links['delete'].click()

    # 4. 等待删除完成（元素从页面消失）
    page.wait_for_selector(f"tr:has-text('{username}')", state='detached', timeout=5000)

    # 5. UI 断言
    assert username not in list_page.get_usernames()

    # 6. 数据库断言
    cur.execute("SELECT * FROM users WHERE username=?", (username,))
    assert cur.fetchone() is None