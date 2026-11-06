# Flask 权限用户管理系统 · UI + API 自动化测试

一个自带被测系统的测试项目：用 Flask + SQLite 从零实现带 RBAC 权限、账号状态与登录锁定的后台系统，
并为它设计了 **UI（Playwright）** 与 **API（requests）** 双层自动化测试。

- 被测系统：`app.py`（单文件，约 300 行）
- 测试用例：**18 条**（UI 10 条 × 双浏览器 + API 8 条）
- 执行耗时：单浏览器 15s，双浏览器 66s

---

## 被测系统能力

| 能力 | 说明 |
|---|---|
| 登录认证 | 用户名 + 密码，Session 保存登录态与角色 |
| 账号状态 | `active` / `disabled`，禁用后不能登录 |
| 登录锁定 | 连续 3 次密码错误锁定 5 分钟，锁定期内正确密码也拒绝 |
| RBAC 权限 | `admin` 可编辑/删除用户；`user` 只能查看 |
| 用户管理 | 列表、新增、编辑、删除（删除带确认弹窗） |
| 接口层 | `/api/users` 的 GET / POST / DELETE，返回 401/403/400/409/201 |

---

## 测试覆盖

### UI 层（Playwright + Page Object）

| 场景 | 断言方式 |
|---|---|
| 登录成功 / 失败 | 页面跳转 + 提示文案 |
| 新增用户 | 列表出现该用户 + **数据库落库校验** |
| 重复用户名 | 提示「用户名已存在」 |
| 删除用户 | 确认弹窗自动接受 + 列表消失 + **数据库确认已删** |
| 未登录访问 | 重定向到 `/login` |
| 普通用户越权删除 | 提示「没有权限删除用户」+ **数据库确认目标仍在** |
| 禁用账号登录 | 提示「账号已被禁用」 |
| 连续 3 次失败锁定 | 第 3 次提示锁定；锁定期内正确密码仍被拒 + 数据库校验 `lock_until` |

### API 层（requests）

| 场景 | 期望 |
|---|---|
| 未登录 GET / POST / DELETE | 401 |
| 管理员查询 | 200 + 字段契约校验 |
| 管理员创建 / 删除 | 201 / 200，创建后能查到、删除后查不到 |
| 重复用户名 | 409 `username_exists` |
| 缺必填字段 | 400 |
| 普通用户读 / 写 | 200 / 403 |

---

## 快速开始

```bash
pip install -r requirements.txt
playwright install chromium firefox

# 终端 1：起被测系统
python app.py

# 终端 2：跑用例
pytest -q                                # 单浏览器，18 条
BROWSERS=chromium,firefox pytest -q      # 双浏览器，28 条
HEADED=1 pytest -q                       # 有头模式，看执行过程
```

> 首次运行会自动创建 `users.db`（`init_db()` 在模块级调用）。

---

## 目录结构

```
flask_user_mgmt/
├── app.py                     被测系统（Flask + SQLite）
├── pytest.ini
├── requirements.txt
├── tests/
│   ├── conftest.py            浏览器生命周期、多浏览器、失败截图、trace、DB 连接
│   ├── pages/                 Page Object：登录页 / 列表页 / 新增页
│   ├── test_user_management.py   基础 CRUD（5 条）
│   ├── test_ui_advanced.py       权限、状态、锁定（5 条）
│   └── test_api.py               接口层（8 条）
├── artifacts/                 失败截图与 trace（gitignore）
└── .github/workflows/ci.yml   CI：双浏览器 + 启动后端 + 上传产物
```

---

## 设计说明

**UI 断言与数据库断言并用**
仅断言「列表里出现该用户」无法发现「接口返回成功但事务回滚」。UI 断言验证表现，数据库断言验证落地，两者同时通过才视为通过。

**状态类前置数据直接写库**
禁用、锁定等前置状态若通过 UI 构造，步骤多且受其他缺陷干扰。通过 `db_conn` 直接插入，用例之间互不影响。

**失败时保留截图与 trace**
UI 用例的主要成本在排障。失败时自动保存整页截图与 Playwright trace（`playwright show-trace xxx.zip` 可逐步回放），无需重跑即可定位。

**浏览器参数化由 `BROWSERS` 控制**
使用自定义 `ui_browser` fixture，避免与 `pytest-playwright` 插件的参数化冲突；默认单浏览器，保证本地执行速度。

**Page Object 边界**
定位器只出现在 `tests/pages/`，用例里不写选择器。改页面只改一处。

---

## CI

`.github/workflows/ci.yml`：安装依赖 → 安装双浏览器 → 启动后端并等待就绪 → 双浏览器执行 → 失败时上传 `artifacts/`。
