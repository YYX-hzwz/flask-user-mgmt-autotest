class AddUserPage:
    def __init__(self, page):
        self.page = page
        self.username_input = page.locator('input[name="username"]')
        self.email_input = page.locator('input[name="email"]')
        self.age_input = page.locator('input[name="age"]')
        self.password_input = page.locator('input[name="password"]')
        self.submit_btn = page.locator('input[type="submit"]')

    def add_user(self, username, email, age, password):
        self.username_input.fill(username)
        self.email_input.fill(email)
        self.age_input.fill(str(age))
        self.password_input.fill(password)
        self.submit_btn.click()
        # 等待跳转到用户列表页
        #self.page.wait_for_url("**/users")