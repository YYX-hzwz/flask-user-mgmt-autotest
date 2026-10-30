class UserListPage:
    def __init__(self, page):
        self.page = page
        self.add_btn = page.locator('a[href="/user/add"]')
        self.table_rows = page.locator('table tr')
        self.flash_msg = page.locator('li')

    def click_add(self):
        self.add_btn.click()

    def get_usernames(self):
        rows = self.table_rows.all()[1:]
        return [row.locator('td').nth(1).inner_text() for row in rows]
    def find_edit_delete(self, username):
        # 根据用户名找到行内的编辑/删除链接
        row = self.page.locator('tr', has_text=username)
        return {
            'edit': row.locator('a[href*="/user/edit/"]'),
            'delete': row.locator('a[href*="/user/delete/"]')
        }