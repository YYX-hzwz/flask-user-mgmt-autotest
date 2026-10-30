import os

from playwright.sync_api import Page

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:5000").rstrip("/")


class LoginPage:
    """登录页。定位器集中在这里，用例不直接引用选择器。"""

    def __init__(self, page: Page):
        self.page = page
        self.username_input = page.locator('input[name="username"]')
        self.password_input = page.locator('input[name="password"]')
        self.submit_btn = page.locator('input[type="submit"]')
        self.flash = page.locator("li")

    def navigate(self):
        self.page.goto(f"{BASE_URL}/login")
        return self

    def login(self, username, password, expect_success: bool = False):
        """默认不等待跳转：失败登录也走这里，等 /users 会超时。"""
        self.username_input.fill(username)
        self.password_input.fill(password)
        self.submit_btn.click()
        if expect_success:
            self.page.wait_for_url("**/users")
        return self

    def flash_text(self) -> str:
        """返回页面上的提示文案，没有则返回空串。"""
        if self.flash.count() == 0:
            return ""
        return self.flash.first.inner_text()
