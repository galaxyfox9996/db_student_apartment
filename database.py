import os
import re
import sqlite3
import sys
from datetime import date, datetime

import pymysql

from config import DB_CONFIG, DB_MODE, SQLITE_CONFIG


CALL_AUTO_ASSIGN_PATTERN = re.compile(r"^\s*CALL\s+proc_auto_assign_room\(", re.IGNORECASE)


def runtime_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def sqlite_db_path():
    db_path = SQLITE_CONFIG["path"]
    if os.path.isabs(db_path):
        return db_path
    return os.path.join(runtime_base_dir(), db_path)


def normalize_sql(sql):
    normalized = sql.replace("%s", "?")
    normalized = normalized.replace("NOW()", "CURRENT_TIMESTAMP")
    normalized = normalized.replace("CURDATE()", "DATE('now', 'localtime')")
    return normalized


def convert_sqlite_value(column_name, value):
    if not isinstance(value, str):
        return value

    try:
        if column_name.endswith("_time"):
            return datetime.fromisoformat(value)
        if column_name.endswith("_date"):
            return date.fromisoformat(value)
    except ValueError:
        return value

    return value


def convert_sqlite_row(row):
    return {key: convert_sqlite_value(key, row[key]) for key in row.keys()}


class SQLiteCursorWrapper:
    def __init__(self, connection_wrapper):
        self.connection_wrapper = connection_wrapper
        self.cursor = connection_wrapper.connection.cursor()
        self._result_rows = None
        self.lastrowid = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.cursor.close()

    def execute(self, sql, params=None):
        params = tuple(params or ())
        if CALL_AUTO_ASSIGN_PATTERN.match(sql):
            self._result_rows = [self.connection_wrapper.proc_auto_assign_room(*params)]
            self.lastrowid = None
            return self

        normalized_sql = normalize_sql(sql)
        self.cursor.execute(normalized_sql, params)
        self.lastrowid = self.cursor.lastrowid
        self._result_rows = None
        return self

    def fetchone(self):
        if self._result_rows is not None:
            return self._result_rows.pop(0) if self._result_rows else None

        row = self.cursor.fetchone()
        if row is None:
            return None
        return convert_sqlite_row(row)

    def fetchall(self):
        if self._result_rows is not None:
            rows = list(self._result_rows)
            self._result_rows = []
            return rows
        return [convert_sqlite_row(row) for row in self.cursor.fetchall()]


class SQLiteConnectionWrapper:
    def __init__(self, db_path):
        os.makedirs(os.path.dirname(db_path), exist_ok=True) if os.path.dirname(db_path) else None
        needs_init = not os.path.exists(db_path)
        self.connection = sqlite3.connect(db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")
        self._open = True
        self._autocommit = True
        if needs_init or not self._has_tables():
            init_sqlite_database(self.connection)

    @property
    def open(self):
        return self._open

    @property
    def autocommit(self):
        return self._autocommit

    @autocommit.setter
    def autocommit(self, value):
        self._autocommit = bool(value)

    def _has_tables(self):
        row = self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'user_account'"
        ).fetchone()
        return row is not None

    def cursor(self):
        return SQLiteCursorWrapper(self)

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        if self._open:
            self.connection.close()
            self._open = False

    def proc_auto_assign_room(self, student_id, apartment_id, room_type):
        cur = self.connection.cursor()

        student_row = cur.execute(
            """
            SELECT student_id, student_no, name, check_status
            FROM student
            WHERE student_id = ?
            """,
            (student_id,),
        ).fetchone()
        if student_row is None:
            return {"message": "分配宿舍失败：学生不存在"}
        if student_row["check_status"] == "checked_in":
            return {"message": "分配宿舍失败：该学生已经入住"}

        living_count = cur.execute(
            "SELECT COUNT(*) AS cnt FROM accommodation WHERE student_id = ? AND status = 'living'",
            (student_id,),
        ).fetchone()["cnt"]
        if living_count > 0:
            return {"message": "分配宿舍失败：该学生已经入住"}

        room = cur.execute(
            """
            SELECT room_id, room_no, capacity, current_count
            FROM room
            WHERE apartment_id = ?
              AND room_type = ?
              AND status = 'normal'
              AND current_count < capacity
            ORDER BY floor ASC, room_no ASC, room_id ASC
            LIMIT 1
            """,
            (apartment_id, room_type),
        ).fetchone()
        if room is None:
            return {"message": "分配宿舍失败：未找到符合条件的可用房间"}

        occupied_rows = cur.execute(
            "SELECT bed_no FROM accommodation WHERE room_id = ? AND status = 'living' ORDER BY bed_no ASC",
            (room["room_id"],),
        ).fetchall()
        occupied = {row["bed_no"] for row in occupied_rows}

        bed_no = None
        for candidate in range(1, room["capacity"] + 1):
            if candidate not in occupied:
                bed_no = candidate
                break

        if bed_no is None:
            return {"message": "分配宿舍失败：房间床位状态异常，请刷新后重试"}

        cur.execute(
            """
            INSERT INTO accommodation (student_id, room_id, bed_no, check_in_date, status)
            VALUES (?, ?, ?, DATE('now', 'localtime'), 'living')
            """,
            (student_id, room["room_id"], bed_no),
        )

        return {
            "message": f"自动分配成功，房间号：{room['room_no']}，床位号：{bed_no}",
            "student_id": student_id,
            "room_id": room["room_id"],
            "bed_no": bed_no,
        }


def get_db_connection():
    if DB_MODE == "sqlite":
        return SQLiteConnectionWrapper(sqlite_db_path())

    return pymysql.connect(
        host=DB_CONFIG["host"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        charset=DB_CONFIG["charset"],
        cursorclass=pymysql.cursors.DictCursor,
    )


def init_sqlite_database(connection):
    schema_statements = [
        """
        CREATE TABLE IF NOT EXISTS user_account (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('student', 'manager', 'admin')),
            related_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
            created_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS student (
            student_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_no TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            gender TEXT NOT NULL CHECK (gender IN ('male', 'female')),
            college TEXT,
            major TEXT,
            class TEXT,
            phone TEXT,
            email TEXT,
            check_status TEXT NOT NULL DEFAULT 'not_checked_in'
                CHECK (check_status IN ('not_checked_in', 'checked_in', 'checked_out'))
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS apartment_manager (
            manager_id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_no TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            gender TEXT NOT NULL CHECK (gender IN ('male', 'female')),
            phone TEXT,
            email TEXT,
            status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive'))
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS apartment (
            apartment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            apartment_name TEXT NOT NULL UNIQUE,
            address TEXT,
            floor_count INTEGER NOT NULL CHECK (floor_count > 0),
            manager_id INTEGER,
            description TEXT,
            FOREIGN KEY (manager_id) REFERENCES apartment_manager(manager_id)
                ON UPDATE CASCADE ON DELETE SET NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS room (
            room_id INTEGER PRIMARY KEY AUTOINCREMENT,
            apartment_id INTEGER NOT NULL,
            room_no TEXT NOT NULL,
            floor INTEGER NOT NULL CHECK (floor > 0),
            room_type TEXT NOT NULL CHECK (room_type IN ('single', 'double', 'quad', 'six')),
            capacity INTEGER NOT NULL CHECK (capacity > 0),
            current_count INTEGER NOT NULL DEFAULT 0 CHECK (current_count >= 0),
            status TEXT NOT NULL DEFAULT 'normal' CHECK (status IN ('normal', 'repairing', 'disabled')),
            UNIQUE (apartment_id, room_no),
            FOREIGN KEY (apartment_id) REFERENCES apartment(apartment_id)
                ON UPDATE CASCADE ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS accommodation (
            accommodation_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            room_id INTEGER NOT NULL,
            bed_no INTEGER NOT NULL,
            check_in_date TEXT NOT NULL,
            check_out_date TEXT,
            status TEXT NOT NULL DEFAULT 'living'
                CHECK (status IN ('living', 'checkout', 'changed')),
            FOREIGN KEY (student_id) REFERENCES student(student_id)
                ON UPDATE CASCADE ON DELETE RESTRICT,
            FOREIGN KEY (room_id) REFERENCES room(room_id)
                ON UPDATE CASCADE ON DELETE RESTRICT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS repair_request (
            repair_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            room_id INTEGER NOT NULL,
            repair_type TEXT NOT NULL,
            description TEXT,
            image_path TEXT,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (status IN ('pending', 'processing', 'completed')),
            submit_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            handle_time TEXT,
            handler_id INTEGER,
            result TEXT,
            result_image_path TEXT,
            FOREIGN KEY (student_id) REFERENCES student(student_id)
                ON UPDATE CASCADE ON DELETE RESTRICT,
            FOREIGN KEY (room_id) REFERENCES room(room_id)
                ON UPDATE CASCADE ON DELETE RESTRICT,
            FOREIGN KEY (handler_id) REFERENCES apartment_manager(manager_id)
                ON UPDATE CASCADE ON DELETE SET NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS visitor_log (
            visitor_id INTEGER PRIMARY KEY AUTOINCREMENT,
            visitor_name TEXT NOT NULL,
            visitor_phone TEXT,
            id_card TEXT,
            student_id INTEGER NOT NULL,
            room_id INTEGER NOT NULL,
            visit_reason TEXT,
            visit_time TEXT NOT NULL,
            leave_time TEXT,
            register_manager_id INTEGER,
            remark TEXT,
            FOREIGN KEY (student_id) REFERENCES student(student_id)
                ON UPDATE CASCADE ON DELETE RESTRICT,
            FOREIGN KEY (room_id) REFERENCES room(room_id)
                ON UPDATE CASCADE ON DELETE RESTRICT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS notice (
            notice_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            image_path TEXT,
            file_path TEXT,
            video_path TEXT,
            publish_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            publisher_id INTEGER,
            FOREIGN KEY (publisher_id) REFERENCES apartment_manager(manager_id)
                ON UPDATE CASCADE ON DELETE SET NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS system_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            operation TEXT NOT NULL,
            operation_time TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            description TEXT,
            FOREIGN KEY (user_id) REFERENCES user_account(user_id)
                ON UPDATE CASCADE ON DELETE CASCADE
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_accommodation_student ON accommodation(student_id)",
        "CREATE INDEX IF NOT EXISTS idx_accommodation_room ON accommodation(room_id)",
        "CREATE INDEX IF NOT EXISTS idx_accommodation_status ON accommodation(status)",
        "CREATE INDEX IF NOT EXISTS idx_repair_student ON repair_request(student_id)",
        "CREATE INDEX IF NOT EXISTS idx_repair_room ON repair_request(room_id)",
        "CREATE INDEX IF NOT EXISTS idx_repair_status ON repair_request(status)",
        "CREATE INDEX IF NOT EXISTS idx_visitor_student ON visitor_log(student_id)",
        "CREATE INDEX IF NOT EXISTS idx_visitor_room ON visitor_log(room_id)",
        "CREATE INDEX IF NOT EXISTS idx_visitor_visit_time ON visitor_log(visit_time)",
        "CREATE INDEX IF NOT EXISTS idx_notice_publisher ON notice(publisher_id)",
        "CREATE INDEX IF NOT EXISTS idx_notice_publish_time ON notice(publish_time)",
        "CREATE INDEX IF NOT EXISTS idx_log_user ON system_log(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_log_operation_time ON system_log(operation_time)",
        """
        CREATE TRIGGER IF NOT EXISTS trg_accommodation_insert_living
        AFTER INSERT ON accommodation
        WHEN NEW.status = 'living'
        BEGIN
            UPDATE room SET current_count = current_count + 1 WHERE room_id = NEW.room_id;
            UPDATE student SET check_status = 'checked_in' WHERE student_id = NEW.student_id;
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_accommodation_update_old_living
        AFTER UPDATE ON accommodation
        WHEN OLD.status = 'living' AND (NEW.status <> 'living' OR NEW.room_id <> OLD.room_id)
        BEGIN
            UPDATE room SET current_count = current_count - 1 WHERE room_id = OLD.room_id;
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_accommodation_update_new_living
        AFTER UPDATE ON accommodation
        WHEN NEW.status = 'living' AND (OLD.status <> 'living' OR NEW.room_id <> OLD.room_id)
        BEGIN
            UPDATE room SET current_count = current_count + 1 WHERE room_id = NEW.room_id;
            UPDATE student SET check_status = 'checked_in' WHERE student_id = NEW.student_id;
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS trg_accommodation_delete_living
        AFTER DELETE ON accommodation
        WHEN OLD.status = 'living'
        BEGIN
            UPDATE room SET current_count = current_count - 1 WHERE room_id = OLD.room_id;
        END
        """,
    ]

    for statement in schema_statements:
        connection.execute(statement)

    seed_sqlite_data(connection)
    connection.commit()


def seed_sqlite_data(connection):
    user_exists = connection.execute("SELECT 1 FROM user_account LIMIT 1").fetchone()
    if user_exists:
        return

    seed_statements = [
        (
            """
            INSERT INTO apartment_manager
            (manager_id, employee_no, name, gender, phone, email, status)
            VALUES
            (1, 'M2026001', '张老师', 'male', '13800000001', 'zhang@example.com', 'active'),
            (2, 'M2026002', '李老师', 'female', '13800000002', 'li@example.com', 'active')
            """,
            (),
        ),
        (
            """
            INSERT INTO student
            (student_id, student_no, name, gender, college, major, class, phone, email, check_status)
            VALUES
            (1, '20260001', '王小明', 'male', '计算机学院', '软件工程', '软件2601', '13900000001', 'wang@example.com', 'checked_in'),
            (2, '20260002', '赵小红', 'female', '计算机学院', '数据科学', '数据2601', '13900000002', 'zhao@example.com', 'checked_in'),
            (3, '20260003', '刘小强', 'male', '信息学院', '网络工程', '网络2601', '13900000003', 'liu@example.com', 'not_checked_in')
            """,
            (),
        ),
        (
            """
            INSERT INTO user_account
            (user_id, username, password, role, related_id, status)
            VALUES
            (1, 'admin', '123456', 'admin', 0, 'active'),
            (2, 'manager001', '123456', 'manager', 1, 'active'),
            (3, 'manager002', '123456', 'manager', 2, 'active'),
            (4, '20260001', '123456', 'student', 1, 'active'),
            (5, '20260002', '123456', 'student', 2, 'active'),
            (6, '20260003', '123456', 'student', 3, 'active')
            """,
            (),
        ),
        (
            """
            INSERT INTO apartment
            (apartment_id, apartment_name, address, floor_count, manager_id, description)
            VALUES
            (1, '一号公寓', '校园东区', 6, 1, '主要入住男生'),
            (2, '二号公寓', '校园西区', 6, 2, '主要入住女生')
            """,
            (),
        ),
        (
            """
            INSERT INTO room
            (room_id, apartment_id, room_no, floor, room_type, capacity, current_count, status)
            VALUES
            (1, 1, '101', 1, 'quad', 4, 0, 'normal'),
            (2, 1, '102', 1, 'quad', 4, 0, 'normal'),
            (3, 1, '201', 2, 'quad', 4, 0, 'normal'),
            (4, 2, '101', 1, 'quad', 4, 0, 'normal'),
            (5, 2, '102', 1, 'quad', 4, 0, 'normal'),
            (6, 2, '201', 2, 'quad', 4, 0, 'repairing')
            """,
            (),
        ),
        (
            """
            INSERT INTO accommodation
            (accommodation_id, student_id, room_id, bed_no, check_in_date, check_out_date, status)
            VALUES
            (1, 1, 1, 1, '2026-05-01', NULL, 'living'),
            (2, 2, 4, 1, '2026-05-01', NULL, 'living')
            """,
            (),
        ),
        (
            """
            INSERT INTO repair_request
            (repair_id, student_id, room_id, repair_type, description, image_path, status, submit_time, handler_id, result)
            VALUES
            (1, 1, 1, '水电维修', '宿舍灯管损坏，需要更换。', 'uploads/repairs/sample_light.jpg', 'pending', CURRENT_TIMESTAMP, NULL, NULL),
            (2, 2, 4, '门窗维修', '窗户无法正常关闭。', 'uploads/repairs/sample_window.jpg', 'processing', CURRENT_TIMESTAMP, 2, '已联系维修人员处理')
            """,
            (),
        ),
        (
            """
            INSERT INTO visitor_log
            (visitor_id, visitor_name, visitor_phone, id_card, student_id, room_id, visit_reason, visit_time, leave_time, register_manager_id, remark)
            VALUES
            (1, '王先生', '13700000001', '110101199901010011', 1, 1, '探望学生', '2026-05-15 10:00:00', '2026-05-15 11:00:00', 1, '正常离开'),
            (2, '赵女士', '13700000002', '110101199902020022', 2, 4, '送生活用品', '2026-05-15 14:00:00', NULL, 2, '尚未登记离开')
            """,
            (),
        ),
        (
            """
            INSERT INTO notice
            (notice_id, title, content, publisher_id, file_path, image_path, video_path)
            VALUES
            (1, '关于宿舍安全检查的通知', '本周五下午进行宿舍安全检查，请同学们提前整理宿舍。', 1, NULL, NULL, NULL),
            (2, '公寓消防安全宣传', '请同学们认真学习消防安全知识。', 2, NULL, NULL, NULL)
            """,
            (),
        ),
        (
            """
            INSERT INTO system_log
            (log_id, user_id, operation, ip_address, description)
            VALUES
            (1, 1, '初始化数据', '127.0.0.1', '系统管理员初始化 SQLite 演示数据')
            """,
            (),
        ),
    ]

    for statement, params in seed_statements:
        connection.execute(statement, params)
