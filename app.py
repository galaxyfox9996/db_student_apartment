from flask import Flask, render_template, request, redirect, url_for, session
import webbrowser
import threading
import time
import os
import sys

from database import get_db_connection


def resource_path(*parts):
    """兼容 PyInstaller 打包后的资源路径。"""
    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, *parts)


def static_upload_dir(*parts):
    return os.path.join(app.static_folder, *parts)


app = Flask(
    __name__,
    template_folder=resource_path("templates"),
    static_folder=resource_path("static"),
)
app.secret_key = os.environ.get("APP_SECRET_KEY", "student_apartment_secret_key")

CLIENT_HEARTBEAT_TIMEOUT = 15
CLIENT_HEARTBEAT_INTERVAL = 5
_active_clients = {}
_active_clients_lock = threading.Lock()
_heartbeat_started = False


def is_local_desktop_mode():
    host = os.environ.get("APP_HOST", "127.0.0.1")
    return getattr(sys, "frozen", False) and host in ("127.0.0.1", "localhost")


def register_active_client(client_id):
    global _heartbeat_started
    if not client_id:
        return
    with _active_clients_lock:
        _active_clients[client_id] = time.time()
        _heartbeat_started = True


def remove_active_client(client_id):
    if not client_id:
        return
    with _active_clients_lock:
        _active_clients.pop(client_id, None)


def prune_inactive_clients():
    now = time.time()
    with _active_clients_lock:
        expired_ids = [
            client_id
            for client_id, last_seen in _active_clients.items()
            if now - last_seen > CLIENT_HEARTBEAT_TIMEOUT
        ]
        for client_id in expired_ids:
            _active_clients.pop(client_id, None)
        return bool(_active_clients), _heartbeat_started


def shutdown_process():
    time.sleep(1)
    os._exit(0)


def auto_shutdown_watchdog():
    while True:
        time.sleep(CLIENT_HEARTBEAT_INTERVAL)
        has_clients, heartbeat_started = prune_inactive_clients()
        if heartbeat_started and not has_clients and is_local_desktop_mode():
            shutdown_process()


def inject_client_shutdown_script(html):
    script = f"""
<script>
(function() {{
  var key = "__student_apartment_tab_id__";
  var clientId = sessionStorage.getItem(key);
  if (!clientId) {{
    if (window.crypto && window.crypto.randomUUID) {{
      clientId = window.crypto.randomUUID();
    }} else {{
      clientId = "tab_" + Date.now() + "_" + Math.random().toString(16).slice(2);
    }}
    sessionStorage.setItem(key, clientId);
  }}

  function sendLifecycleEvent(url) {{
    var payload = JSON.stringify({{ client_id: clientId }});
    if (navigator.sendBeacon) {{
      navigator.sendBeacon(url, new Blob([payload], {{ type: "application/json" }}));
      return;
    }}
    fetch(url, {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: payload,
      keepalive: true
    }});
  }}

  sendLifecycleEvent("/__heartbeat");
  window.setInterval(function() {{
    sendLifecycleEvent("/__heartbeat");
  }}, {CLIENT_HEARTBEAT_INTERVAL * 1000});

  window.addEventListener("beforeunload", function() {{
    sendLifecycleEvent("/__disconnect");
  }});
}})();
</script>
"""
    if "</body>" in html:
        return html.replace("</body>", script + "\n</body>")
    return html + script


@app.after_request
def attach_auto_shutdown_script(response):
    if not is_local_desktop_mode():
        return response
    if response.content_type and "text/html" in response.content_type.lower():
        html = response.get_data(as_text=True)
        response.set_data(inject_client_shutdown_script(html))
        response.headers["Content-Length"] = str(len(response.get_data()))
    return response


@app.route("/__heartbeat", methods=["POST"])
def heartbeat():
    data = request.get_json(silent=True) or {}
    register_active_client(data.get("client_id"))
    return ("", 204)


@app.route("/__disconnect", methods=["POST"])
def disconnect():
    data = request.get_json(silent=True) or {}
    remove_active_client(data.get("client_id"))
    return ("", 204)


def write_log(operation, description=None):
    """写入系统日志"""
    user_id = session.get("user_id")
    if not user_id:
        return
    ip_address = request.remote_addr
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
            INSERT INTO system_log (user_id, operation, operation_time, ip_address, description)
            VALUES (%s, %s, NOW(), %s, %s)
            """
            cursor.execute(sql, (user_id, operation, ip_address, description))
            conn.commit()
    except Exception as e:
        print("写系统日志失败：", e)
    finally:
        if conn is not None and conn.open:
            conn.close()


@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = None
        user = None

        try:
            conn = get_db_connection()

            with conn.cursor() as cursor:
                sql = """
                SELECT * FROM user_account
                WHERE username = %s
                  AND password = %s
                  AND status = 'active'
                """
                cursor.execute(sql, (username, password))
                user = cursor.fetchone()

        except Exception as e:
            print("登录查询失败：", e)
            return render_template("login.html", error="数据库连接或查询失败")

        finally:
            if conn is not None and conn.open:
                conn.close()

        if user:
            session["user_id"] = user["user_id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            session["related_id"] = user["related_id"]

            write_log("用户登录", f"用户 {user['username']}({user['role']}) 登录系统")

            if user["role"] == "admin":
                return redirect(url_for("admin_index"))
            elif user["role"] == "manager":
                return redirect(url_for("manager_index"))
            elif user["role"] == "student":
                return redirect(url_for("student_index"))

        return render_template("login.html", error="用户名或密码错误")

    return render_template("login.html")


@app.route("/admin")
def admin_index():
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    return render_template("admin_index.html")

@app.route("/admin/students")
def student_list():
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    keyword = request.args.get("keyword", "")
    conn = None
    students = []
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if keyword:
                sql = """
                SELECT *
                FROM student
                WHERE student_no LIKE %s
                    OR name LIKE %s
                    OR college LIKE %s
                    OR major LIKE %s
                    OR `class` LIKE %s
                ORDER BY student_id DESC
                """
                like_keyword = f"%{keyword}%"
                cursor.execute(sql,(like_keyword, like_keyword, like_keyword, like_keyword, like_keyword))
            else:
                sql = """
                    SELECT *
                    FROM student
                    ORDER BY student_id DESC
                    """
                cursor.execute(sql)
            students = cursor.fetchall()
    except Exception as e:
        print("查询学生列表失败：", e)
        return "查询学生信息失败"
    finally:
        if conn is not None and conn.open:
            conn.close()
    return render_template(
        "student_list.html",
        students=students,
        keyword=keyword
    )



# 添加学生功能，管理员可以通过表单输入学生信息，提交后将数据插入到数据库中，并创建对应的用户账号
@app.route("/admin/students/add", methods=["GET", "POST"])
def add_student():
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    if request.method == "POST":
        student_no = request.form.get("student_no")
        name = request.form.get("name")
        gender = request.form.get("gender")
        college = request.form.get("college")
        major = request.form.get("major")
        phone = request.form.get("phone")
        email = request.form.get("email")
        class_name = request.form.get("class_name")

        conn = None

        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                sql = """
                INSERT INTO student
                (student_no, name, gender, college, major, phone, email, `class`, check_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'not_checked_in')
                """
                cursor.execute(sql,(
                    student_no,
                    name,
                    gender,
                    college,
                    major,
                    phone,
                    email,
                    class_name
                ))

                student_id = cursor.lastrowid

                sql_user = """
                INSERT INTO user_account
                (username, password, role, related_id, status)
                VALUES (%s, %s, 'student', %s, 'active')"""
                cursor.execute(sql_user, (student_no, "123456", student_id))

                conn.commit()
                write_log("添加学生", f"添加学生 {name}({student_no})")
                return redirect(url_for("student_list"))
        except Exception as e:
            if conn:
                conn.rollback()
            print("添加学生失败：", e)
            return "添加学生失败"
        finally:
            if conn is not None and conn.open:
                conn.close()
    return render_template("student_add.html")


# 编辑学生功能，管理员可以修改学生的基本信息和审核状态，提交后更新数据库中的记录，并同步更新对应的用户账号的用户名
@app.route("/admin/students/edit/<int:student_id>", methods=["GET", "POST"])
def edit_student(student_id):
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    conn = None
    if request.method == "POST":
        student_no = request.form.get("student_no")
        name = request.form.get("name")
        gender = request.form.get("gender")
        college = request.form.get("college")
        major = request.form.get("major")
        class_name = request.form.get("class_name")
        phone = request.form.get("phone")
        email = request.form.get("email")
        check_status = request.form.get("check_status")

        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                sql = """
                UPDATE student
                SET student_no = %s,
                    name = %s,
                    gender = %s,
                    college = %s,
                    major = %s,
                    `class` = %s,
                    phone = %s,
                    email = %s,
                    check_status = %s
                WHERE student_id = %s
                """
                cursor.execute(sql, (
                    student_no,
                    name,
                    gender,
                    college,
                    major,
                    class_name,
                    phone,
                    email,
                    check_status,
                    student_id
                ))
                sql_user = """
                UPDATE user_account
                SET username = %s
                WHERE role = 'student' AND related_id = %s
                """
                cursor.execute(sql_user, (student_no, student_id))


                conn.commit()
                write_log("编辑学生", f"编辑学生 {name}({student_no})")
            return redirect(url_for("student_list"))
        except Exception as e:
            if conn:
                conn.rollback()
            print("更新学生信息失败：", e)
            return "更新学生信息失败"
        finally:
            if conn is not None and conn.open:
                conn.close()
        
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """SELECT * FROM student WHERE student_id = %s"""
            cursor.execute(sql, (student_id,))
            student = cursor.fetchone()
        if not student:
            return "学生不存在"
    except Exception as e:
        print("查询学生信息失败：", e)
        return "查询学生信息失败"
    finally:
        if conn is not None and conn.open:
            conn.close()
    return render_template("student_edit.html", student=student)

# 删除学生功能，管理员可以删除学生记录，同时删除对应的用户账号
@app.route("/admin/students/delete/<int:student_id>")
def delete_student(student_id):
    if session.get("role") !="admin":
        return redirect(url_for("login"))
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 删除学生前先检查是否存在住宿记录，如果存在则不允许删除
            sql_check = """
            SELECT COUNT(*) AS count
            FROM accommodation
            WHERE student_id = %s
            """
            cursor.execute(sql_check, (student_id,))
            result = cursor.fetchone()
            if result["count"] > 0:
                return "无法删除学生，存在住宿记录"
            #先删除账号
            sql_user = """
            DELETE FROM user_account
            WHERE role = 'student' AND related_id = %s"""
            cursor.execute(sql_user, (student_id,))
            #再删除学生信息
            sql_student = """
            DELETE FROM student
            WHERE student_id = %s"""
            cursor.execute(sql_student, (student_id,))
            conn.commit()
            write_log("删除学生", f"删除学生 ID={student_id}")
            return redirect(url_for("student_list"))
    except Exception as e:
        if conn:
            conn.rollback()
        print("删除学生失败：", e)
        return "删除学生失败"
    finally:
        if conn is not None and conn.open:
            conn.close()

@app.route("/admin/managers")
def manager_list():
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    # 这里可以添加查询管理员信息的代码，类似于学生信息管理
    keyword = request.args.get("keyword", "")
    conn = None
    managers = []
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if keyword:
                sql = """
                SELECT *
                FROM apartment_manager
                WHERE employee_no LIKE %s
                    OR name LIKE %s
                    OR gender LIKE %s
                    OR phone LIKE %s
                    OR email LIKE %s
                ORDER BY manager_id DESC
                """
                like_keyword = f"%{keyword}%"
                cursor.execute(sql,(like_keyword, like_keyword, like_keyword, like_keyword, like_keyword))
            else:
                sql = """
                    SELECT *
                    FROM apartment_manager
                    ORDER BY manager_id DESC
                    """
                cursor.execute(sql)
            managers = cursor.fetchall()
    except Exception as e:
        print("查询管理员列表失败：", e)
        return "查询管理员信息失败"
    finally:
        if conn is not None and conn.open:
            conn.close()
    return render_template(
        "manager_list.html",
        managers=managers,
        keyword=keyword
    )

# 添加公寓管理员功能，管理员可以通过表单输入管理员信息，提交后将数据插入到数据库中，并创建对应的用户账号
@app.route("/admin/managers/add", methods=["GET", "POST"])
def add_manager():
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    if request.method == "POST":
        employee_no = request.form.get("employee_no")
        name = request.form.get("name")
        gender = request.form.get("gender")
        phone = request.form.get("phone")
        email = request.form.get("email")

        conn = None

        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                sql = """
                INSERT INTO apartment_manager
                (employee_no, name, gender, phone, email)
                VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(sql,(
                    employee_no,
                    name,
                    gender,
                    phone,
                    email
                ))

                manager_id = cursor.lastrowid

                sql_user = """
                INSERT INTO user_account
                (username, password, role, related_id, status)
                VALUES (%s, %s, 'manager', %s, 'active')"""
                cursor.execute(sql_user, (employee_no, "123456", manager_id))

                conn.commit()
                write_log("添加公寓管理员", f"添加管理员 {name}({employee_no})")
                return redirect(url_for("manager_list"))
        except Exception as e:
            if conn:
                conn.rollback()
            print("添加公寓管理员失败：", e)
            return "添加公寓管理员失败"
        finally:
            if conn is not None and conn.open:
                conn.close()
    return render_template("manager_add.html")

# 编辑公寓管理员功能，管理员可以修改管理员的基本信息，提交后更新数据库中的记录，并同步更新对应的用户账号的用户名
@app.route("/admin/managers/edit/<int:manager_id>", methods=["GET", "POST"])
def edit_manager(manager_id):
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    conn = None
    if request.method == "POST":
        employee_no = request.form.get("employee_no")
        name = request.form.get("name")
        gender = request.form.get("gender")
        phone = request.form.get("phone")
        email = request.form.get("email")

        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                sql = """
                UPDATE apartment_manager
                SET employee_no = %s,
                    name = %s,
                    gender = %s,
                    phone = %s,
                    email = %s
                WHERE manager_id = %s
                """
                cursor.execute(sql, (
                    employee_no,
                    name,
                    gender,
                    phone,
                    email,
                    manager_id
                ))
                sql_user = """
                UPDATE user_account
                SET username = %s
                WHERE role = 'manager' AND related_id = %s
                """
                cursor.execute(sql_user, (employee_no, manager_id))


                conn.commit()
                write_log("编辑公寓管理员", f"编辑管理员 {name}({employee_no})")
            return redirect(url_for("manager_list"))
        except Exception as e:
            if conn:
                conn.rollback()
            print("更新公寓管理员信息失败：", e)
            return "更新公寓管理员信息失败"
        finally:
            if conn is not None and conn.open:
                conn.close()

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """SELECT * FROM apartment_manager WHERE manager_id = %s"""
            cursor.execute(sql, (manager_id,))
            manager = cursor.fetchone()
        if not manager:
            return "公寓管理员不存在"
    except Exception as e:
        print("查询公寓管理员信息失败：", e)
        return "查询公寓管理员信息失败"
    finally:
        if conn is not None and conn.open:
            conn.close()
    return render_template("manager_edit.html", manager=manager)

# 删除公寓管理员功能，管理员可以删除管理员记录，同时删除对应的用户账号
@app.route("/admin/managers/delete/<int:manager_id>")
def delete_manager(manager_id):
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            #先删除账号
            sql_user = """
            DELETE FROM user_account
            WHERE role = 'manager' AND related_id = %s"""
            cursor.execute(sql_user, (manager_id,))
            #再删除管理员信息
            sql_manager = """
            DELETE FROM apartment_manager
            WHERE manager_id = %s"""
            cursor.execute(sql_manager, (manager_id,))
            conn.commit()
            write_log("删除公寓管理员", f"删除管理员 ID={manager_id}")
            return redirect(url_for("manager_list"))
    except Exception as e:
        if conn:
            conn.rollback()
        print("删除公寓管理员失败：", e)
        return "删除公寓管理员失败"
    finally:
        if conn is not None and conn.open:
            conn.close()

# 公寓信息管理功能，管理员可以查看公寓房间的基本信息，可以根据房间号、楼层、容量等信息进行搜索和过滤
@app.route("/admin/apartments", methods=["GET", "POST"])
def apartment_list():
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    # 这里可以添加查询房间信息的代码
    keyword = request.args.get("keyword", "")
    conn = None
    apartments = []

    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if keyword:
                sql = """
                SELECT *
                FROM apartment
                WHERE apartment_name LIKE %s
                    OR address LIKE %s
                ORDER BY manager_id DESC
                """
                like_keyword = f"%{keyword}%"
                cursor.execute(sql,(like_keyword, like_keyword))
            else:
                sql = """
                    SELECT *
                    FROM apartment
                    ORDER BY manager_id DESC
                    """
                cursor.execute(sql)
            apartments = cursor.fetchall()
    except Exception as e:
        print("查询公寓列表失败：", e)
        return "查询公寓列表失败"
    finally:
        if conn is not None and conn.open:
            conn.close()
    return render_template(
        "apartment_list.html",
        apartments=apartments,
        keyword=keyword
    )

# 房间信息，查看房间的信息以及居住学生的信息，管理员可以根据房间号、学生姓名等信息进行搜索和过滤
@app.route("/admin/rooms")
def room_list():
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    keyword = request.args.get("keyword", "")
    apartment_id = request.args.get("apartment_id", "")
    apartment_name = ""
    conn = None
    rooms = []
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 如果指定了公寓ID，查询公寓名称
            if apartment_id:
                sql_apt = "SELECT apartment_name FROM apartment WHERE apartment_id = %s"
                cursor.execute(sql_apt, (apartment_id,))
                apt = cursor.fetchone()
                if apt:
                    apartment_name = apt["apartment_name"]

            if apartment_id and keyword:
                sql = """
                SELECT r.*, a.apartment_name, s.name AS student_name,
                       (r.capacity - r.current_count) AS available_beds
                FROM room r
                LEFT JOIN apartment a ON r.apartment_id = a.apartment_id
                LEFT JOIN accommodation ac ON r.room_id = ac.room_id
                LEFT JOIN student s ON ac.student_id = s.student_id
                WHERE r.apartment_id = %s
                    AND (r.room_no LIKE %s
                        OR a.apartment_name LIKE %s
                        OR s.name LIKE %s)"""
                like_keyword = f"%{keyword}%"
                cursor.execute(sql, (apartment_id, like_keyword, like_keyword, like_keyword))
            elif apartment_id:
                sql = """
                SELECT r.*, a.apartment_name, s.name AS student_name,
                       (r.capacity - r.current_count) AS available_beds
                FROM room r
                LEFT JOIN apartment a ON r.apartment_id = a.apartment_id
                LEFT JOIN accommodation ac ON r.room_id = ac.room_id
                LEFT JOIN student s ON ac.student_id = s.student_id
                WHERE r.apartment_id = %s"""
                cursor.execute(sql, (apartment_id,))
            elif keyword:
                sql = """
                SELECT r.*, a.apartment_name, s.name AS student_name,
                       (r.capacity - r.current_count) AS available_beds
                FROM room r
                LEFT JOIN apartment a ON r.apartment_id = a.apartment_id
                LEFT JOIN accommodation ac ON r.room_id = ac.room_id
                LEFT JOIN student s ON ac.student_id = s.student_id
                WHERE r.room_no LIKE %s
                    OR a.apartment_name LIKE %s
                    OR s.name LIKE %s"""
                like_keyword = f"%{keyword}%"
                cursor.execute(sql, (like_keyword, like_keyword, like_keyword))
            else:
                sql = """
                    SELECT r.*, a.apartment_name, s.name AS student_name,
                           (r.capacity - r.current_count) AS available_beds
                    FROM room r
                    LEFT JOIN apartment a ON r.apartment_id = a.apartment_id
                    LEFT JOIN accommodation ac ON r.room_id = ac.room_id
                    LEFT JOIN student s ON ac.student_id = s.student_id
                    """
                cursor.execute(sql)
            rooms = cursor.fetchall()
    except Exception as e:
        print("查询房间列表失败：", e)
        return "查询房间列表失败"
    finally:
        if conn is not None and conn.open:
            conn.close()
    return render_template(
        "room_list.html",
        rooms=rooms,
        keyword=keyword,
        apartment_id=apartment_id,
        apartment_name=apartment_name
    )


# 住宿分配管理 — 学生列表页，管理员可以搜索学生并选择进行宿舍分配
@app.route("/admin/assign")
def assign_list():
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    keyword = request.args.get("keyword", "")
    conn = None
    students = []
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if keyword:
                sql = """
                SELECT s.*,
                    CASE WHEN ac.room_id IS NOT NULL THEN 'checked_in' ELSE 'not_checked_in' END AS check_status
                FROM student s
                LEFT JOIN accommodation ac ON s.student_id = ac.student_id
                WHERE s.student_no LIKE %s
                    OR s.name LIKE %s
                    OR s.college LIKE %s
                    OR s.major LIKE %s
                    OR s.`class` LIKE %s
                ORDER BY s.student_id DESC
                """
                like_keyword = f"%{keyword}%"
                cursor.execute(sql, (like_keyword, like_keyword, like_keyword, like_keyword, like_keyword))
            else:
                sql = """
                SELECT s.*,
                    CASE WHEN ac.room_id IS NOT NULL THEN 'checked_in' ELSE 'not_checked_in' END AS check_status
                FROM student s
                LEFT JOIN accommodation ac ON s.student_id = ac.student_id
                ORDER BY s.student_id DESC
                """
                cursor.execute(sql)
            students = cursor.fetchall()
    except Exception as e:
        print("查询学生列表失败：", e)
        return "查询学生列表失败"
    finally:
        if conn is not None and conn.open:
            conn.close()
    return render_template(
        "assign_list.html",
        students=students,
        keyword=keyword
    )

# 为指定学生分配宿舍
@app.route("/admin/assign/<int:student_id>", methods=["GET", "POST"])
def assign_room(student_id):
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    
    conn = None
    available_rooms = []
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 查询学生信息
            cursor.execute("SELECT * FROM student WHERE student_id = %s", (student_id,))
            student = cursor.fetchone()
            if not student:
                return "学生不存在"
            
            # 查询所有公寓列表
            cursor.execute("SELECT * FROM apartment ORDER BY apartment_id")
            apartments = cursor.fetchall()

            # 查询所有有空位的房间
            sql_rooms = """
            SELECT r.room_id, r.room_no, r.room_type, r.floor, r.capacity, r.current_count,
                   (r.capacity - r.current_count) AS available_beds,
                   a.apartment_id, a.apartment_name
            FROM room r
            JOIN apartment a ON r.apartment_id = a.apartment_id
            WHERE r.status = 'normal'
              AND (r.capacity - r.current_count) > 0
            ORDER BY a.apartment_name, r.room_no
            """
            cursor.execute(sql_rooms)
            available_rooms = cursor.fetchall()
    except Exception as e:
        print("查询学生/公寓信息失败：", e)
        return "查询信息失败"
    finally:
        if conn is not None and conn.open:
            conn.close()
    
    if request.method == "POST":
        assign_mode = request.form.get("assign_mode", "auto")
        apartment_id = request.form.get("apartment_id")
        
        if not apartment_id:
            return render_template("assign_result.html", error="请选择公寓")
        
        conn2 = None
        try:
            conn2 = get_db_connection()
            # 注意：不自动提交，需要手动控制事务
            conn2.autocommit = False
            with conn2.cursor() as cursor:
                if assign_mode == "manual":
                    # 手动选床分配
                    room_id = request.form.get("room_id")
                    bed_no = request.form.get("bed_no")
                    
                    if not room_id or not bed_no:
                        conn2.rollback()
                        return render_template("assign_result.html", error="请选择房间和床位")
                    
                    room_id = int(room_id)
                    bed_no = int(bed_no)
                    
                    # 检查学生是否已入住
                    cursor.execute(
                        "SELECT COUNT(*) AS cnt FROM accommodation WHERE student_id = %s AND status = 'living'",
                        (student_id,)
                    )
                    if cursor.fetchone()["cnt"] > 0:
                        conn2.rollback()
                        return render_template("assign_result.html", error="该学生已经入住")
                    
                    # 检查床位是否已被占用
                    cursor.execute(
                        "SELECT COUNT(*) AS cnt FROM accommodation WHERE room_id = %s AND bed_no = %s AND status = 'living'",
                        (room_id, bed_no)
                    )
                    if cursor.fetchone()["cnt"] > 0:
                        conn2.rollback()
                        return render_template("assign_result.html", error=f"床位号 {bed_no} 已被占用")
                    
                    # 检查房间是否还有空位
                    cursor.execute(
                        "SELECT capacity, current_count, room_no FROM room WHERE room_id = %s AND status = 'normal'",
                        (room_id,)
                    )
                    room = cursor.fetchone()
                    if not room:
                        conn2.rollback()
                        return render_template("assign_result.html", error="房间不存在或不可用")
                    if room["current_count"] >= room["capacity"]:
                        conn2.rollback()
                        return render_template("assign_result.html", error="该房间已满")
                    
                    # 插入住宿记录（触发器会自动更新 current_count）
                    cursor.execute(
                        "INSERT INTO accommodation (student_id, room_id, bed_no, check_in_date, status) VALUES (%s, %s, %s, CURDATE(), 'living')",
                        (student_id, room_id, bed_no)
                    )
                    
                    # 更新学生入住状态
                    cursor.execute(
                        "UPDATE student SET check_status = 'checked_in' WHERE student_id = %s",
                        (student_id,)
                    )
                    
                    conn2.commit()
                    
                    write_log("住宿分配", f"为学生 {student['name']}({student['student_no']}) 手动分配宿舍 {room['room_no']} 床位 {bed_no}")
                    
                    result = {
                        "message": f"分配成功，房间号：{room['room_no']}，床位号：{bed_no}",
                        "student_id": student_id,
                        "room_id": room_id,
                        "bed_no": bed_no
                    }
                    return render_template("assign_result.html", result=result)
                else:
                    # 自动分配：调用存储过程
                    room_type = request.form.get("room_type")
                    if not room_type:
                        return render_template("assign_result.html", error="请选择房间类型")
                    
                    cursor.execute(
                        "CALL proc_auto_assign_room(%s, %s, %s)",
                        (student_id, int(apartment_id), room_type)
                    )
                    result = cursor.fetchone()
                    conn2.commit()

                    # 检查存储过程是否返回了错误消息
                    msg = result.get("message", "") if result else ""
                    if msg and msg.startswith("分配宿舍失败"):
                        return render_template("assign_result.html", error=msg)

                    write_log("住宿分配", f"为学生 {student['name']}({student['student_no']}) 自动分配宿舍")
                    return render_template("assign_result.html", result=result)
        except Exception as e:
            error_msg = str(e)
            print("分配宿舍失败：", error_msg)
            try:
                conn2.rollback()
            except:
                pass
            return render_template("assign_result.html", error=error_msg)
        finally:
            try:
                conn2.autocommit = True
            except:
                pass
            if conn2 is not None and conn2.open:
                conn2.close()
    
    # GET 请求：渲染分配表单
    return render_template(
        "assign_room.html",
        student=student,
        apartments=apartments,
        available_rooms=available_rooms
    )

# API: 获取某公寓下有空位的房间列表
@app.route("/admin/api/available_rooms")
def api_available_rooms():
    if session.get("role") != "admin":
        return {"error": "未授权"}, 403
    apartment_id = request.args.get("apartment_id", "")
    if not apartment_id:
        return {"error": "请提供公寓ID"}, 400
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
            SELECT r.room_id, r.room_no, r.room_type, r.floor, r.capacity, r.current_count,
                   (r.capacity - r.current_count) AS available_beds
            FROM room r
            WHERE r.apartment_id = %s
              AND r.status = 'normal'
              AND (r.capacity - r.current_count) > 0
            ORDER BY r.floor ASC, r.room_no ASC
            """
            cursor.execute(sql, (apartment_id,))
            rooms = cursor.fetchall()
            return {"rooms": rooms}
    except Exception as e:
        print("查询空闲房间失败：", e)
        return {"error": "查询失败"}, 500
    finally:
        if conn is not None and conn.open:
            conn.close()


# API: 获取某房间的空闲床位号列表
@app.route("/admin/api/room_beds/<int:room_id>")
def api_room_beds(room_id):
    if session.get("role") != "admin":
        return {"error": "未授权"}, 403
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 获取房间容量和当前入住人数
            cursor.execute(
                "SELECT capacity, current_count FROM room WHERE room_id = %s AND status = 'normal'",
                (room_id,)
            )
            room = cursor.fetchone()
            if not room:
                return {"error": "房间不存在或不可用"}, 404
            
            # 获取已占用的床位号
            cursor.execute(
                "SELECT bed_no FROM accommodation WHERE room_id = %s AND status = 'living'",
                (room_id,)
            )
            occupied = set(row["bed_no"] for row in cursor.fetchall())
            
            # 生成可用床位号列表
            available_beds = [i for i in range(1, room["capacity"] + 1) if i not in occupied]
            
            return {
                "room_id": room_id,
                "capacity": room["capacity"],
                "current_count": room["current_count"],
                "available_beds": available_beds
            }
    except Exception as e:
        print("查询空闲床位失败：", e)
        return {"error": "查询失败"}, 500
    finally:
        if conn is not None and conn.open:
            conn.close()


# admin查看系统运行日志
@app.route("/admin/logs")
def system_logs():
    if session.get("role") != "admin":
        return redirect(url_for("login"))
    username = request.args.get("username", "")
    operation = request.args.get("operation", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    page = request.args.get("page", 1, type=int)
    per_page = 20

    conn = None
    logs = []
    total = 0
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 构建查询条件
            where_clauses = []
            params = []

            if username:
                where_clauses.append("u.username LIKE %s")
                params.append(f"%{username}%")
            if operation:
                where_clauses.append("l.operation = %s")
                params.append(operation)
            if date_from:
                where_clauses.append("DATE(l.operation_time) >= %s")
                params.append(date_from)
            if date_to:
                where_clauses.append("DATE(l.operation_time) <= %s")
                params.append(date_to)

            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

            # 查询总数
            count_sql = f"""
            SELECT COUNT(*) AS cnt
            FROM system_log l
            JOIN user_account u ON l.user_id = u.user_id
            WHERE {where_sql}
            """
            cursor.execute(count_sql, params)
            total = cursor.fetchone()["cnt"]

            # 分页查询
            offset = (page - 1) * per_page
            sql = f"""
            SELECT l.*, u.username, u.role
            FROM system_log l
            JOIN user_account u ON l.user_id = u.user_id
            WHERE {where_sql}
            ORDER BY l.operation_time DESC
            LIMIT %s OFFSET %s
            """
            cursor.execute(sql, params + [per_page, offset])
            logs = cursor.fetchall()
    except Exception as e:
        print("查询系统日志失败：", e)
        return "查询系统日志失败"
    finally:
        if conn is not None and conn.open:
            conn.close()

    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template(
        "admin_log.html",
        logs=logs,
        username=username,
        operation=operation,
        date_from=date_from,
        date_to=date_to,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages
    )


@app.route("/manager")
def manager_index():
    if session.get("role") != "manager":
        return redirect(url_for("login"))
    return render_template("manager_index.html")

# 公寓管理员维修申报处理
@app.route("/manager/repair/list")
def manager_repair_list():
    if session.get("role") != "manager":
        return redirect(url_for("login"))
    manager_id = session.get("related_id")
    status_filter = request.args.get("status", "")
    conn = None
    repairs = []
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if status_filter:
                sql = """
                SELECT rr.*,
                       s.name AS student_name,
                       s.student_no,
                       r.room_no,
                       r.room_type,
                       ap.apartment_name
                FROM repair_request rr
                JOIN room r ON rr.room_id = r.room_id
                JOIN apartment ap ON r.apartment_id = ap.apartment_id
                JOIN student s ON rr.student_id = s.student_id
                WHERE ap.manager_id = %s AND rr.status = %s
                ORDER BY rr.submit_time DESC
                """
                cursor.execute(sql, (manager_id, status_filter))
            else:
                sql = """
                SELECT rr.*,
                       s.name AS student_name,
                       s.student_no,
                       r.room_no,
                       r.room_type,
                       ap.apartment_name
                FROM repair_request rr
                JOIN room r ON rr.room_id = r.room_id
                JOIN apartment ap ON r.apartment_id = ap.apartment_id
                JOIN student s ON rr.student_id = s.student_id
                WHERE ap.manager_id = %s
                ORDER BY rr.submit_time DESC
                """
                cursor.execute(sql, (manager_id,))
            repairs = cursor.fetchall()
    except Exception as e:
        print("查询维修申报列表失败：", e)
        return "查询维修申报列表失败"
    finally:
        if conn is not None and conn.open:
            conn.close()
    return render_template(
        "manager_repair_list.html",
        repairs=repairs,
        status_filter=status_filter
    )


@app.route("/manager/repair/handle/<int:repair_id>", methods=["GET", "POST"])
def manager_repair_handle(repair_id):
    if session.get("role") != "manager":
        return redirect(url_for("login"))
    manager_id = session.get("related_id")

    conn = None
    repair = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
            SELECT rr.*,
                   s.name AS student_name,
                   s.student_no,
                   s.phone AS student_phone,
                   r.room_no,
                   r.room_type,
                   ap.apartment_name,
                   ap.manager_id
            FROM repair_request rr
            JOIN room r ON rr.room_id = r.room_id
            JOIN apartment ap ON r.apartment_id = ap.apartment_id
            JOIN student s ON rr.student_id = s.student_id
            WHERE rr.repair_id = %s
            """
            cursor.execute(sql, (repair_id,))
            repair = cursor.fetchone()
    except Exception as e:
        print("查询维修申报详情失败：", e)
        return "查询维修申报详情失败"
    finally:
        if conn is not None and conn.open:
            conn.close()

    if not repair:
        return "维修申报不存在"
    if repair["manager_id"] != manager_id:
        return "无权处理该维修申报"

    if request.method == "POST":
        new_status = request.form.get("status")
        result_text = request.form.get("result", "").strip()

        if new_status not in ("processing", "completed"):
            return "无效的状态值"

        conn2 = None
        try:
            conn2 = get_db_connection()
            with conn2.cursor() as cursor:
                sql_update = """
                UPDATE repair_request
                SET status = %s,
                    result = %s,
                    handler_id = %s,
                    handle_time = NOW()
                WHERE repair_id = %s
                """
                cursor.execute(sql_update, (new_status, result_text if result_text else None, manager_id, repair_id))
                conn2.commit()
                write_log("处理维修申报", f"处理维修申报 ID={repair_id}, 状态={new_status}")
        except Exception as e:
            print("处理维修申报失败：", e)
            return "处理维修申报失败"
        finally:
            if conn2 is not None and conn2.open:
                conn2.close()
        return redirect(url_for("manager_repair_list"))

    return render_template("manager_repair_handle.html", repair=repair)


# manager处理访客申请
@app.route("/manager/visitor/list")
def manager_visitor_list():
    if session.get("role") != "manager":
        return redirect(url_for("login"))
    manager_id = session.get("related_id")
    status_filter = request.args.get("status", "")
    conn = None
    visitors = []
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            if status_filter == "registered":
                sql = """
                SELECT v.*,
                       s.name AS student_name,
                       s.student_no,
                       r.room_no,
                       r.room_type,
                       ap.apartment_name
                FROM visitor_log v
                JOIN room r ON v.room_id = r.room_id
                JOIN apartment ap ON r.apartment_id = ap.apartment_id
                JOIN student s ON v.student_id = s.student_id
                WHERE ap.manager_id = %s AND v.register_manager_id IS NOT NULL
                ORDER BY v.visit_time DESC
                """
                cursor.execute(sql, (manager_id,))
            elif status_filter == "unregistered":
                sql = """
                SELECT v.*,
                       s.name AS student_name,
                       s.student_no,
                       r.room_no,
                       r.room_type,
                       ap.apartment_name
                FROM visitor_log v
                JOIN room r ON v.room_id = r.room_id
                JOIN apartment ap ON r.apartment_id = ap.apartment_id
                JOIN student s ON v.student_id = s.student_id
                WHERE ap.manager_id = %s AND v.register_manager_id IS NULL
                ORDER BY v.visit_time DESC
                """
                cursor.execute(sql, (manager_id,))
            else:
                sql = """
                SELECT v.*,
                       s.name AS student_name,
                       s.student_no,
                       r.room_no,
                       r.room_type,
                       ap.apartment_name
                FROM visitor_log v
                JOIN room r ON v.room_id = r.room_id
                JOIN apartment ap ON r.apartment_id = ap.apartment_id
                JOIN student s ON v.student_id = s.student_id
                WHERE ap.manager_id = %s
                ORDER BY v.visit_time DESC
                """
                cursor.execute(sql, (manager_id,))
            visitors = cursor.fetchall()
    except Exception as e:
        print("查询访客列表失败：", e)
        return "查询访客列表失败"
    finally:
        if conn is not None and conn.open:
            conn.close()
    return render_template(
        "manager_visitor_list.html",
        visitors=visitors,
        status_filter=status_filter
    )


@app.route("/manager/visitor/handle/<int:visitor_id>", methods=["GET", "POST"])
def manager_visitor_handle(visitor_id):
    if session.get("role") != "manager":
        return redirect(url_for("login"))
    manager_id = session.get("related_id")

    conn = None
    visitor = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
            SELECT v.*,
                   s.name AS student_name,
                   s.student_no,
                   s.phone AS student_phone,
                   r.room_no,
                   r.room_type,
                   ap.apartment_name,
                   ap.manager_id
            FROM visitor_log v
            JOIN room r ON v.room_id = r.room_id
            JOIN apartment ap ON r.apartment_id = ap.apartment_id
            JOIN student s ON v.student_id = s.student_id
            WHERE v.visitor_id = %s
            """
            cursor.execute(sql, (visitor_id,))
            visitor = cursor.fetchone()
    except Exception as e:
        print("查询访客详情失败：", e)
        return "查询访客详情失败"
    finally:
        if conn is not None and conn.open:
            conn.close()

    if not visitor:
        return "访客记录不存在"
    if visitor["manager_id"] != manager_id:
        return "无权处理该访客记录"

    if request.method == "POST":
        action = request.form.get("action")

        conn2 = None
        try:
            conn2 = get_db_connection()
            with conn2.cursor() as cursor:
                if action == "register":
                    sql_update = """
                    UPDATE visitor_log
                    SET register_manager_id = %s
                    WHERE visitor_id = %s AND register_manager_id IS NULL
                    """
                    cursor.execute(sql_update, (manager_id, visitor_id))
                    conn2.commit()
                    write_log("登记访客", f"登记访客 ID={visitor_id}, 访客 {visitor['visitor_name']}")
                elif action == "leave":
                    sql_update = """
                    UPDATE visitor_log
                    SET leave_time = NOW()
                    WHERE visitor_id = %s AND leave_time IS NULL
                    """
                    cursor.execute(sql_update, (visitor_id,))
                    conn2.commit()
                    write_log("访客离校", f"访客离校 ID={visitor_id}, 访客 {visitor['visitor_name']}")
                else:
                    return "无效的操作"
        except Exception as e:
            print("处理访客记录失败：", e)
            return "处理访客记录失败"
        finally:
            if conn2 is not None and conn2.open:
                conn2.close()
        return redirect(url_for("manager_visitor_list"))

    return render_template("manager_visitor_handle.html", visitor=visitor)

# manager发布公告功能，管理员可以发布公告以及删除公告，输入公告标题和内容，并且可以添加图片、文件或视频，提交后将公告保存到数据库中，并在学生首页显示最新的公告信息

@app.route("/manager/notice/list")
def manager_notice_list():
    if session.get("role") != "manager":
        return redirect(url_for("login"))
    manager_id = session.get("related_id")
    conn = None
    notices = []
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
            SELECT *
            FROM notice
            WHERE publisher_id = %s
            ORDER BY publish_time DESC
            """
            cursor.execute(sql, (manager_id,))
            notices = cursor.fetchall()
    except Exception as e:
        print("查询公告列表失败：", e)
        return "查询公告列表失败"
    finally:
        if conn is not None and conn.open:
            conn.close()
    return render_template("manager_notice_list.html", notices=notices)


@app.route("/manager/notice/add", methods=["GET", "POST"])
def manager_notice_add():
    if session.get("role") != "manager":
        return redirect(url_for("login"))
    manager_id = session.get("related_id")

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()

        if not title or not content:
            return "标题和内容不能为空"

        import uuid
        import os

        upload_dir = static_upload_dir("uploads", "notices")
        os.makedirs(upload_dir, exist_ok=True)

        image_path = None
        file_path = None
        video_path = None

        # 图片上传
        img_file = request.files.get("image")
        if img_file and img_file.filename:
            filename = img_file.filename
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            if ext not in ("jpg", "jpeg", "png", "gif", "webp"):
                return "只允许上传 jpg、jpeg、png、gif、webp 格式的图片"
            img_file.seek(0, 2)
            size = img_file.tell()
            img_file.seek(0)
            if size > 5 * 1024 * 1024:
                return "图片大小不能超过 5MB"
            save_name = f"{uuid.uuid4().hex}_{filename}"
            save_path = os.path.join(upload_dir, save_name)
            img_file.save(save_path)
            image_path = f"uploads/notices/{save_name}"

        # 文件上传
        doc_file = request.files.get("file")
        if doc_file and doc_file.filename:
            filename = doc_file.filename
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            if ext not in ("pdf", "doc", "docx", "xls", "xlsx"):
                return "只允许上传 pdf、doc、docx、xls、xlsx 格式的文件"
            doc_file.seek(0, 2)
            size = doc_file.tell()
            doc_file.seek(0)
            if size > 5 * 1024 * 1024:
                return "文件大小不能超过 5MB"
            save_name = f"{uuid.uuid4().hex}_{filename}"
            save_path = os.path.join(upload_dir, save_name)
            doc_file.save(save_path)
            file_path = f"uploads/notices/{save_name}"

        # 视频上传
        vid_file = request.files.get("video")
        if vid_file and vid_file.filename:
            filename = vid_file.filename
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            if ext not in ("mp4", "avi", "mov"):
                return "只允许上传 mp4、avi、mov 格式的视频"
            vid_file.seek(0, 2)
            size = vid_file.tell()
            vid_file.seek(0)
            if size > 5 * 1024 * 1024:
                return "视频大小不能超过 5MB"
            save_name = f"{uuid.uuid4().hex}_{filename}"
            save_path = os.path.join(upload_dir, save_name)
            vid_file.save(save_path)
            video_path = f"uploads/notices/{save_name}"

        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                sql = """
                INSERT INTO notice (title, content, image_path, file_path, video_path, publisher_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (title, content, image_path, file_path, video_path, manager_id))
                conn.commit()
                write_log("发布公告", f"发布公告：{title}")
        except Exception as e:
            print("发布公告失败：", e)
            return "发布公告失败"
        finally:
            if conn is not None and conn.open:
                conn.close()
        return redirect(url_for("manager_notice_list"))

    return render_template("manager_notice_add.html")


@app.route("/manager/notice/delete/<int:notice_id>")
def manager_notice_delete(notice_id):
    if session.get("role") != "manager":
        return redirect(url_for("login"))
    manager_id = session.get("related_id")
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # 只能删除自己发布的公告
            sql = """
            DELETE FROM notice
            WHERE notice_id = %s AND publisher_id = %s
            """
            cursor.execute(sql, (notice_id, manager_id))
            conn.commit()
            write_log("删除公告", f"删除公告 ID={notice_id}")
    except Exception as e:
        print("删除公告失败：", e)
        return "删除公告失败"
    finally:
        if conn is not None and conn.open:
            conn.close()
    return redirect(url_for("manager_notice_list"))


@app.route("/student")
def student_index():
    if session.get("role") != "student":
        return redirect(url_for("login"))
    # 查询最新公告用于首页展示
    conn = None
    latest_notices = []
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
            SELECT n.notice_id, n.title, n.publish_time, am.name AS publisher_name
            FROM notice n
            LEFT JOIN apartment_manager am ON n.publisher_id = am.manager_id
            ORDER BY n.publish_time DESC
            LIMIT 5
            """
            cursor.execute(sql)
            latest_notices = cursor.fetchall()
    except Exception as e:
        print("查询最新公告失败：", e)
    finally:
        if conn is not None and conn.open:
            conn.close()
    return render_template("student_index.html", latest_notices=latest_notices)

# 学生查看自己的所有信息
@app.route("/student/info")
def student_info():
    if session.get("role") != "student":
        return redirect(url_for("login"))
    student_id = session.get("related_id")
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
            SELECT s.*,
            a.accommodation_id,
            a.bed_no,
            a.check_in_date,
            a.status AS accommodation_status,
            r.room_no,
            r.floor,
            r.room_type,
            ap.apartment_name
            FROM student s
            LEFT JOIN accommodation a ON s.student_id = a.student_id AND a.status = 'living'
            LEFT JOIN room r ON a.room_id = r.room_id
            LEFT JOIN apartment ap ON r.apartment_id = ap.apartment_id
            WHERE s.student_id = %s
            """
            cursor.execute(sql, (student_id,))
            student = cursor.fetchone()
    except Exception as e:
        print("查询学生信息失败：", e)
        return "查询学生信息失败"
    finally:
        if conn is not None and conn.open:
            conn.close()
    return render_template("student_info.html", student=student)

# 学生提交维修申报
@app.route("/student/repair", methods=["GET", "POST"])
def submit_repair():
    if session.get("role") != "student":
        return redirect(url_for("login"))
    student_id = session.get("related_id")
    conn = None
    # 查询学生住宿信息（GET渲染用）
    accommodation = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
            SELECT a.accommodation_id, a.room_id, a.bed_no,
                   r.room_no, r.floor, r.room_type,
                   ap.apartment_name
            FROM accommodation a
            JOIN room r ON a.room_id = r.room_id
            JOIN apartment ap ON r.apartment_id = ap.apartment_id
            WHERE a.student_id = %s AND a.status = 'living'
            """
            cursor.execute(sql, (student_id,))
            accommodation = cursor.fetchone()
    except Exception as e:
        print("查询住宿信息失败：", e)
    finally:
        if conn is not None and conn.open:
            conn.close()

    if request.method == "POST":
        # 校验是否已入住
        if not accommodation:
            return "未入住，无法提交维修申报。请先办理入住。"
        # 接收表单数据
        repair_type = request.form.get("repair_type", "").strip()
        description = request.form.get("description", "").strip()
        if not repair_type:
            return "请选择维修类型"
        # 处理图片上传
        image_path = None
        file = request.files.get("image")
        if file and file.filename:
            filename = file.filename
            # 只允许图片格式
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            if ext not in ("jpg", "jpeg", "png", "gif", "webp"):
                return "只允许上传 jpg、jpeg、png、gif、webp 格式的图片"
            # 检查文件大小（5MB）
            file.seek(0, 2)
            size = file.tell()
            file.seek(0)
            if size > 5 * 1024 * 1024:
                return "图片大小不能超过 5MB"
            # 生成唯一文件名
            import uuid
            import os
            upload_dir = static_upload_dir("uploads", "repairs")
            os.makedirs(upload_dir, exist_ok=True)
            save_name = f"{uuid.uuid4().hex}_{filename}"
            save_path = os.path.join(upload_dir, save_name)
            file.save(save_path)
            image_path = f"uploads/repairs/{save_name}"
        # 插入维修申报
        conn2 = None
        try:
            conn2 = get_db_connection()
            with conn2.cursor() as cursor:
                sql = """
                INSERT INTO repair_request
                (student_id, room_id, repair_type, description, image_path, status, submit_time)
                VALUES (%s, %s, %s, %s, %s, 'pending', NOW())
                """
                cursor.execute(sql, (
                    student_id,
                    accommodation["room_id"],
                    repair_type,
                    description if description else None,
                    image_path
                ))
                conn2.commit()
                write_log("提交维修申报", f"学生提交维修申报，类型={repair_type}")
        except Exception as e:
            print("提交维修申报失败：", e)
            return "提交维修申报失败，请稍后重试"
        finally:
            if conn2 is not None and conn2.open:
                conn2.close()
        # 提交成功，重定向避免重复提交
        return redirect(url_for("submit_repair"))

    return render_template("student_repair.html", accommodation=accommodation)

# 学生查看维修进度
@app.route("/student/repair/list")
def student_repair_list():
    if session.get("role") != "student":
        return redirect(url_for("login"))
    student_id = session.get("related_id")
    conn = None
    repairs = []
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
            SELECT rr.*,
                   r.room_no,
                   r.room_type,
                   ap.apartment_name
            FROM repair_request rr
            JOIN room r ON rr.room_id = r.room_id
            JOIN apartment ap ON r.apartment_id = ap.apartment_id
            WHERE rr.student_id = %s
            ORDER BY rr.submit_time DESC
            """
            cursor.execute(sql, (student_id,))
            repairs = cursor.fetchall()
    except Exception as e:
        print("查询维修记录失败：", e)
        return "查询维修记录失败"
    finally:
        if conn is not None and conn.open:
            conn.close()
    return render_template("student_repair_list.html", repairs=repairs)

# 学生查看公告
@app.route("/student/notice")
def student_notice_list():
    if session.get("role") != "student":
        return redirect(url_for("login"))
    conn = None
    notices = []
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
            SELECT n.*, am.name AS publisher_name
            FROM notice n
            LEFT JOIN apartment_manager am ON n.publisher_id = am.manager_id
            ORDER BY n.publish_time DESC
            """
            cursor.execute(sql)
            notices = cursor.fetchall()
    except Exception as e:
        print("查询公告列表失败：", e)
        return "查询公告列表失败"
    finally:
        if conn is not None and conn.open:
            conn.close()
    return render_template("student_notice_list.html", notices=notices)

# 申请访客入校
@app.route("/student/visitor/apply", methods=["GET", "POST"])
def visitor_apply():
    if session.get("role") != "student":
        return redirect(url_for("login"))
    student_id = session.get("related_id")
    conn = None
    accommodation = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
            SELECT a.accommodation_id, a.room_id, a.bed_no,
                   r.room_no, r.floor, r.room_type,
                   ap.apartment_name
            FROM accommodation a
            JOIN room r ON a.room_id = r.room_id
            JOIN apartment ap ON r.apartment_id = ap.apartment_id
            WHERE a.student_id = %s AND a.status = 'living'
            """
            cursor.execute(sql, (student_id,))
            accommodation = cursor.fetchone()
    except Exception as e:
        print("查询住宿信息失败：", e)
    finally:
        if conn is not None and conn.open:
            conn.close()

    if request.method == "POST":
        if not accommodation:
            return "未入住，无法申请访客"
        visitor_name = request.form.get("visitor_name", "").strip()
        visitor_phone = request.form.get("visitor_phone", "").strip()
        id_card = request.form.get("id_card", "").strip()
        visit_reason = request.form.get("visit_reason", "").strip()
        visit_time = request.form.get("visit_time", "").strip()
        remark = request.form.get("remark", "").strip()

        if not visitor_name or not visit_time:
            return "访客姓名和来访时间不能为空"

        conn2 = None
        try:
            conn2 = get_db_connection()
            with conn2.cursor() as cursor:
                sql = """
                INSERT INTO visitor_log
                (visitor_name, visitor_phone, id_card, student_id, room_id,
                 visit_reason, visit_time, remark)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (
                    visitor_name,
                    visitor_phone if visitor_phone else None,
                    id_card if id_card else None,
                    student_id,
                    accommodation["room_id"],
                    visit_reason if visit_reason else None,
                    visit_time,
                    remark if remark else None
                ))
                conn2.commit()
                write_log("申请访客", f"学生申请访客 {visitor_name}")
        except Exception as e:
            print("申请访客失败：", e)
            return "申请访客失败，请稍后重试"
        finally:
            if conn2 is not None and conn2.open:
                conn2.close()
        return redirect(url_for("visitor_apply"))

    return render_template("student_visitor_apply.html", accommodation=accommodation)


# 学生查看访客历史记录
@app.route("/student/visitor/history")
def visitor_history():
    if session.get("role") != "student":
        return redirect(url_for("login"))
    student_id = session.get("related_id")
    conn = None
    visitors = []
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            sql = """
            SELECT v.*, r.room_no, r.room_type, ap.apartment_name
            FROM visitor_log v
            JOIN room r ON v.room_id = r.room_id
            JOIN apartment ap ON r.apartment_id = ap.apartment_id
            WHERE v.student_id = %s
            ORDER BY v.visit_time DESC
            """
            cursor.execute(sql, (student_id,))
            visitors = cursor.fetchall()
    except Exception as e:
        print("查询访客记录失败：", e)
        return "查询访客记录失败"
    finally:
        if conn is not None and conn.open:
            conn.close()
    return render_template("student_visitor_history.html", visitors=visitors)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

def open_browser():
    time.sleep(1)  # 等待服务器启动
    host = os.environ.get("APP_HOST", "127.0.0.1")
    port = int(os.environ.get("APP_PORT", "5000"))
    webbrowser.open(f"http://{host}:{port}/")


def start_app():
    host = os.environ.get("APP_HOST", "127.0.0.1")
    port = int(os.environ.get("APP_PORT", "5000"))
    debug = os.environ.get("APP_DEBUG", "0") == "1"
    if is_local_desktop_mode():
        threading.Thread(target=auto_shutdown_watchdog, daemon=True).start()
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        threading.Thread(target=open_browser).start()
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    start_app()
