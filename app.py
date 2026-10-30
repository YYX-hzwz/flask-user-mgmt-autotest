import sqlite3
from flask import Flask, render_template_string, request, redirect, url_for, session, flash
app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# 初始化数据库
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
             (id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT UNIQUE NOT NULL,
              email TEXT NOT NULL,
              age INTEGER,
              password TEXT NOT NULL,
              role TEXT NOT NULL DEFAULT 'user',
              status TEXT NOT NULL DEFAULT 'active',
              login_attempts INTEGER NOT NULL DEFAULT 0,
              lock_until TEXT)''')
    c.execute("INSERT OR IGNORE INTO users (username, email, age, password, role, status) VALUES ('admin', 'admin@example.com', 30, '123456', 'admin', 'active')")
    conn.commit()
    conn.close()

def query_db(query, args=(), one=False):
    conn = sqlite3.connect('users.db')
    try:
        cur = conn.execute(query, args)
        rv = cur.fetchall()
        conn.commit()
        return (rv[0] if rv else None) if one else rv
    except:
        conn.rollback()
        raise
    finally:
        conn.close()
# HTML 模板字符串
login_html = '''
<!DOCTYPE html>
<html>
<body>
    <h2>登录</h2>
    {% with messages = get_flashed_messages() %}
      {% if messages %}
        <ul>
        {% for message in messages %}
          <li>{{ message }}</li>
        {% endfor %}
        </ul>
      {% endif %}
    {% endwith %}
    <form method="post">
        用户名: <input type="text" name="username"><br>
        密码: <input type="password" name="password"><br>
        <input type="submit" value="登录">
    </form>
</body>
</html>
'''

list_html = '''
<!DOCTYPE html>
<html>
<body>
    <h2>用户列表</h2>
    <a href="/user/add">新增用户</a>
    <a href="/logout">登出</a>
    {% with messages = get_flashed_messages() %}
      {% if messages %}
        <ul>
        {% for message in messages %}
          <li>{{ message }}</li>
        {% endfor %}
        </ul>
      {% endif %}
    {% endwith %}
    <table border="1">
    <tr><th>ID</th><th>用户名</th><th>邮箱</th><th>年龄</th><th>角色</th><th>状态</th><th>操作</th></tr>
    {% for user in users %}
    <tr>
        <td>{{ user[0] }}</td>
        <td>{{ user[1] }}</td>
        <td>{{ user[2] }}</td>
        <td>{{ user[3] }}</td>
        <td>{{ user[5] }}</td>
        <td>{{ user[6] }}</td>
        <td>
            <a href="/user/edit/{{ user[0] }}">编辑</a>
            {% if session.get('role') == 'admin' %}
            <a href="/user/delete/{{ user[0] }}" onclick="return confirm('确定删除?')">删除</a>
            {% endif %}
        </td>
    </tr>
    {% endfor %}
</table>
</body>
</html>
'''

add_html = '''
<!DOCTYPE html>
<html>
<body>
    <h2>新增用户</h2>
    {% with messages = get_flashed_messages() %}
      {% if messages %}
        <ul>
        {% for message in messages %}
          <li>{{ message }}</li>
        {% endfor %}
        </ul>
      {% endif %}
    {% endwith %}
    <form method="post">
        用户名: <input type="text" name="username"><br>
        邮箱: <input type="text" name="email"><br>
        年龄: <input type="number" name="age"><br>
        密码: <input type="password" name="password"><br>
        <input type="submit" value="添加">
        <a href="/users">返回</a>
    </form>
</body>
</html>
'''

edit_html = '''
<!DOCTYPE html>
<html>
<body>
    <h2>编辑用户</h2>
    {% with messages = get_flashed_messages() %}
      {% if messages %}
        <ul>
        {% for message in messages %}
          <li>{{ message }}</li>
        {% endfor %}
        </ul>
      {% endif %}
    {% endwith %}
    <form method="post">
        用户名: <input type="text" name="username" value="{{ user[1] }}"><br>
        邮箱: <input type="text" name="email" value="{{ user[2] }}"><br>
        年龄: <input type="number" name="age" value="{{ user[3] }}"><br>
        密码: <input type="password" name="password" value="{{ user[4] }}"><br>
        <input type="submit" value="更新">
        <a href="/users">返回</a>
    </form>
</body>
</html>
'''

from datetime import datetime, timedelta

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = query_db('SELECT * FROM users WHERE username = ?', (username,), one=True)
        if user:
            # 检查用户状态
            if user[6] == 'disabled':   # 假设字段顺序：id, username, email, age, password, role, status, login_attempts, lock_until
                flash('账号已被禁用')
                return render_template_string(login_html)
            # 检查是否锁定
            if user[8]:  # lock_until 字段
                lock_time = datetime.fromisoformat(user[8])
                if lock_time > datetime.now():
                    flash('账号已锁定，请稍后再试')
                    return render_template_string(login_html)
            # 验证密码
            if user[4] == password:
                # 登录成功，重置失败次数
                query_db('UPDATE users SET login_attempts = 0, lock_until = NULL WHERE id = ?', (user[0],))
                session['user'] = username
                session['role'] = user[5]   # 保存角色到 session
                return redirect(url_for('list_users'))
            else:
                # 密码错误，增加失败次数
                attempts = user[7] + 1
                if attempts >= 3:
                    lock_until = (datetime.now() + timedelta(minutes=5)).isoformat()
                    query_db('UPDATE users SET login_attempts = ?, lock_until = ? WHERE id = ?', (attempts, lock_until, user[0]))
                    flash('密码错误次数过多，账号已锁定5分钟')
                else:
                    query_db('UPDATE users SET login_attempts = ? WHERE id = ?', (attempts, user[0]))
                    flash('用户名或密码错误')
        else:
            flash('用户名或密码错误')
    return render_template_string(login_html)

@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('role', None)
    return redirect(url_for('login'))

@app.route('/users')
def list_users():
    if 'user' not in session:
        return redirect(url_for('login'))
    users = query_db('SELECT * FROM users')
    return render_template_string(list_html, users=users)

@app.route('/user/add', methods=['GET', 'POST'])
def add_user():
    if 'user' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        age = request.form['age']
        password = request.form['password']
        try:
            query_db('INSERT INTO users (username, email, age, password) VALUES (?, ?, ?, ?)',
                     (username, email, age, password))
            flash('用户添加成功')
            return redirect(url_for('list_users'))
        except sqlite3.IntegrityError:
            flash('用户名已存在')
    return render_template_string(add_html)

@app.route('/user/edit/<int:id>', methods=['GET', 'POST'])
def edit_user(id):
    if 'user' not in session:
        return redirect(url_for('login'))
    if session.get('role') != 'admin':
        flash('没有权限编辑用户')
        return redirect(url_for('list_users'))
    user = query_db('SELECT * FROM users WHERE id = ?', (id,), one=True)
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        age = request.form['age']
        password = request.form['password']
        role = request.form.get('role', user[5])   # 保留原角色
        status = request.form.get('status', user[6]) # 保留原状态
        try:
            query_db('UPDATE users SET username=?, email=?, age=?, password=?, role=?, status=? WHERE id=?',
                     (username, email, age, password, role, status, id))
            flash('用户更新成功')
            return redirect(url_for('list_users'))
        except sqlite3.IntegrityError:
            flash('用户名已存在')
    return render_template_string(edit_html, user=user)

@app.route('/user/delete/<int:id>')
def delete_user(id):
    if 'user' not in session:
        return redirect(url_for('login'))
    if session.get('role') != 'admin':
        flash('没有权限删除用户')
        return redirect(url_for('list_users'))
    query_db('DELETE FROM users WHERE id = ?', (id,))
    flash('用户已删除')
    return redirect(url_for('list_users'))


from flask import jsonify

@app.route('/api/users', methods=['GET'])
def api_get_users():
    if 'user' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    users = query_db('SELECT id, username, email, age, role, status FROM users')
    user_list = [{'id': u[0], 'username': u[1], 'email': u[2], 'age': u[3], 'role': u[4], 'status': u[5]} for u in users]
    return jsonify(user_list)

@app.route('/api/users', methods=['POST'])
def api_create_user():
    if 'user' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    if session.get('role') != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    age = data.get('age')
    password = data.get('password')
    role = data.get('role', 'user')
    status = data.get('status', 'active')
    if not username or not password:
        return jsonify({'error': 'username and password are required'}), 400
    try:
        query_db('INSERT INTO users (username, email, age, password, role, status) VALUES (?, ?, ?, ?, ?, ?)',
                 (username, email, age, password, role, status))
        return jsonify({'message': 'created'}), 201
    except sqlite3.IntegrityError:
        return jsonify({'error': 'username_exists'}), 409

@app.route('/api/users/<int:id>', methods=['DELETE'])
def api_delete_user(id):
    if 'user' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    if session.get('role') != 'admin':
        return jsonify({'error': 'forbidden'}), 403
    query_db('DELETE FROM users WHERE id = ?', (id,))
    return jsonify({'message': 'deleted'}), 200

init_db()

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=False)
