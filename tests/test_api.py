"""API 层用例：/api/users 的鉴权、CRUD 与错误码。

为什么单独一层：
- UI 用例慢（每个用例要起浏览器），API 用例快，适合覆盖边界和权限组合；
- UI + API 双层，才能验证「接口返回成功」与「页面表现」是否一致。

覆盖：
- 未登录：401
- 普通用户：创建/删除 403，查询 200
- 管理员：查询 200、创建 201、重复 409、删除 200
- 参数缺失：400
"""

from __future__ import annotations

import uuid

import pytest
import requests

pytestmark = pytest.mark.api

TIMEOUT = 5

USER_SCHEMA = {"id", "username", "email", "age", "role", "status"}


def unique_name(prefix: str = "api") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def session_for(base_url: str, username: str, password: str) -> requests.Session:
    """登录并返回带 cookie 的会话；登录失败直接报错，避免后续用例误判。"""
    session = requests.Session()
    response = session.post(
        f"{base_url}/login",
        data={"username": username, "password": password},
        allow_redirects=False,
        timeout=TIMEOUT,
    )
    assert response.status_code == 302, f"{username} 登录失败：HTTP {response.status_code}"
    return session


def create_user_via_api(session: requests.Session, base_url: str, **overrides) -> dict:
    payload = {
        "username": unique_name(),
        "email": "api@example.com",
        "age": 20,
        "password": "123456",
        "role": "user",
        "status": "active",
    }
    payload.update(overrides)
    response = session.post(f"{base_url}/api/users", json=payload, timeout=TIMEOUT)
    assert response.status_code == 201, response.text
    return payload


def find_user_id(session: requests.Session, base_url: str, username: str) -> int | None:
    rows = session.get(f"{base_url}/api/users", timeout=TIMEOUT).json()
    for row in rows:
        if row["username"] == username:
            return int(row["id"])
    return None


# --------------------------------------------------------------------------
# 未登录
# --------------------------------------------------------------------------
def test_get_users_requires_login(base_url: str) -> None:
    response = requests.get(f"{base_url}/api/users", timeout=TIMEOUT)
    assert response.status_code == 401
    assert response.json() == {"error": "unauthorized"}


def test_create_requires_login(base_url: str) -> None:
    response = requests.post(f"{base_url}/api/users", json={"username": "x", "password": "y"}, timeout=TIMEOUT)
    assert response.status_code == 401


def test_delete_requires_login(base_url: str) -> None:
    response = requests.delete(f"{base_url}/api/users/1", timeout=TIMEOUT)
    assert response.status_code == 401


# --------------------------------------------------------------------------
# 管理员
# --------------------------------------------------------------------------
def test_admin_can_list_users(base_url: str) -> None:
    session = session_for(base_url, "admin", "123456")
    response = session.get(f"{base_url}/api/users", timeout=TIMEOUT)

    assert response.status_code == 200
    rows = response.json()
    assert isinstance(rows, list) and rows, "至少应有 admin 用户"
    assert USER_SCHEMA <= set(rows[0]), f"字段缺失：{USER_SCHEMA - set(rows[0])}"
    assert any(row["username"] == "admin" for row in rows)


def test_admin_create_and_delete_roundtrip(base_url: str) -> None:
    session = session_for(base_url, "admin", "123456")
    payload = create_user_via_api(session, base_url)

    user_id = find_user_id(session, base_url, payload["username"])
    assert user_id is not None, "创建成功但列表里查不到，说明没落库"

    deleted = session.delete(f"{base_url}/api/users/{user_id}", timeout=TIMEOUT)
    assert deleted.status_code == 200
    assert find_user_id(session, base_url, payload["username"]) is None


def test_duplicate_username_returns_409(base_url: str) -> None:
    session = session_for(base_url, "admin", "123456")
    payload = create_user_via_api(session, base_url)
    try:
        again = session.post(f"{base_url}/api/users", json=payload, timeout=TIMEOUT)
        assert again.status_code == 409
        assert again.json() == {"error": "username_exists"}
    finally:
        user_id = find_user_id(session, base_url, payload["username"])
        if user_id:
            session.delete(f"{base_url}/api/users/{user_id}", timeout=TIMEOUT)


def test_missing_required_fields_returns_400(base_url: str) -> None:
    session = session_for(base_url, "admin", "123456")
    response = session.post(f"{base_url}/api/users", json={"email": "a@b.com"}, timeout=TIMEOUT)
    assert response.status_code == 400


# --------------------------------------------------------------------------
# 普通用户
# --------------------------------------------------------------------------
@pytest.fixture
def normal_user(base_url: str):
    """用管理员创建一个普通用户，用完删除。"""
    admin = session_for(base_url, "admin", "123456")
    payload = create_user_via_api(admin, base_url, role="user")
    yield payload
    user_id = find_user_id(admin, base_url, payload["username"])
    if user_id:
        admin.delete(f"{base_url}/api/users/{user_id}", timeout=TIMEOUT)


def test_normal_user_can_read_but_cannot_write(base_url: str, normal_user: dict) -> None:
    normal = session_for(base_url, normal_user["username"], normal_user["password"])

    assert normal.get(f"{base_url}/api/users", timeout=TIMEOUT).status_code == 200

    created = normal.post(
        f"{base_url}/api/users",
        json={"username": unique_name(), "password": "123456"},
        timeout=TIMEOUT,
    )
    assert created.status_code == 403
    assert created.json() == {"error": "forbidden"}

    deleted = normal.delete(f"{base_url}/api/users/1", timeout=TIMEOUT)
    assert deleted.status_code == 403
