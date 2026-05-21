DROP DATABASE IF EXISTS student_apartment_system;
CREATE DATABASE student_apartment_system
DEFAULT CHARACTER SET utf8mb4
DEFAULT COLLATE utf8mb4_general_ci;
USE student_apartment_system;

-- 1.用户表
CREATE TABLE user_account(
    user_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '用户编号',
    username VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
    password VARCHAR(255) NOT NULL COMMENT '密码',
    role ENUM('student','manager','admin') NOT NULL COMMENT '用户角色',
    related_id INT NOT NULL COMMENT '关联ID',
    status ENUM('active','inactive') NOT NULL DEFAULT 'active' COMMENT '账户状态',
    created_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- 2.学生表
CREATE TABLE student(
    student_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '学生编号',
    student_no VARCHAR(20) NOT NULL UNIQUE COMMENT '学号',
    name VARCHAR(50) NOT NULL COMMENT '姓名',
    gender ENUM('male','female') NOT NULL COMMENT '性别',
    college VARCHAR(100) DEFAULT NULL COMMENT '学院',
    major VARCHAR(100) DEFAULT NULL COMMENT '专业',
    class VARCHAR(50) DEFAULT NULL COMMENT '班级',
    phone VARCHAR(20) DEFAULT NULL COMMENT '联系电话',
    email VARCHAR(100) DEFAULT NULL COMMENT '电子邮箱',
    check_status ENUM('not_checked_in','checked_in','checked_out') NOT NULL DEFAULT 'not_checked_in' COMMENT '入住状态'
)ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='学生表';

-- 3.公寓管理员表
CREATE TABLE apartment_manager(
    manager_id INT PRIMARY KEY AUTO_INCREMENT COMMENT '管理员编号',
    employee_no VARCHAR(20) NOT NULL UNIQUE COMMENT '工号',
    name VARCHAR(50) NOT NULL COMMENT '姓名',
    gender ENUM('male','female') NOT NULL COMMENT '性别',
    phone VARCHAR(20) DEFAULT NULL COMMENT '联系电话',
    email VARCHAR(100) DEFAULT NULL COMMENT '电子邮箱',
    status ENUM('active','inactive') NOT NULL DEFAULT 'active' COMMENT '工作状态'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='公寓管理员表';

-- 4.公寓表
CREATE TABLE apartment(
    apartment_id INT PRIMARY KEY AUTO_INCREMENT COMMENT '公寓编号',
    apartment_name VARCHAR(100) NOT NULL UNIQUE COMMENT '公寓名称',
    address VARCHAR(255) DEFAULT NULL COMMENT '公寓地址',
    floor_count INT NOT NULL COMMENT '楼层数',
    manager_id INT DEFAULT NULL COMMENT '管理员编号',
    description TEXT DEFAULT NULL COMMENT '公寓描述',

    CONSTRAINT fk_apartment_manager
        FOREIGN KEY (manager_id) 
        REFERENCES apartment_manager(manager_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL,
    CONSTRAINT chk_floor_count CHECK (floor_count > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='公寓表';

-- 5.房间表
CREATE TABLE room(
    room_id INT PRIMARY KEY AUTO_INCREMENT COMMENT '房间编号',
    apartment_id INT NOT NULL COMMENT '公寓编号',
    room_no VARCHAR(20) NOT NULL COMMENT '房间号',
    floor INT NOT NULL COMMENT '楼层',
    room_type ENUM('single','double','quad','six') NOT NULL COMMENT '房间类型',
    capacity INT NOT NULL COMMENT '房间容量',
    current_count INT NOT NULL DEFAULT 0 COMMENT '当前入住人数',
    status ENUM('normal','repairing','disabled') NOT NULL DEFAULT 'normal' COMMENT '房间状态',
    CONSTRAINT fk_room_apartment
        FOREIGN KEY (apartment_id)
        REFERENCES apartment(apartment_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    CONSTRAINT uq_room_no UNIQUE (apartment_id, room_no),
    CONSTRAINT chk_floor CHECK (floor > 0),
    CONSTRAINT chk_capacity CHECK (capacity > 0),
    CONSTRAINT chk_current_count CHECK (current_count >= 0 AND current_count <= capacity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='房间表';

-- 6.住宿记录表
CREATE TABLE accommodation(
    accommodation_id INT PRIMARY KEY AUTO_INCREMENT COMMENT '住宿记录编号',
    student_id INT NOT NULL COMMENT '学生编号',
    room_id INT NOT NULL COMMENT '房间编号',
    bed_no INT NOT NULL COMMENT '床位号',
    check_in_date DATE NOT NULL COMMENT '入住日期',
    check_out_date DATE DEFAULT NULL COMMENT '退房日期',
    status ENUM('living','checkout','changed') NOT NULL DEFAULT 'living' COMMENT '住宿状态',
    CONSTRAINT fk_accommodation_student
        FOREIGN KEY (student_id)
        REFERENCES student(student_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT fk_accommodation_room
        FOREIGN KEY (room_id)
        REFERENCES room(room_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT chk_accommodation_dates CHECK (check_out_date IS NULL OR check_out_date >= check_in_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='住宿记录表';

CREATE INDEX idx_accommodation_student ON accommodation(student_id);
CREATE INDEX idx_accommodation_room ON accommodation(room_id);
CREATE INDEX idx_accommodation_status ON accommodation(status);

-- 7.维修记录表
CREATE TABLE repair_request(
    repair_id INT PRIMARY KEY AUTO_INCREMENT COMMENT '维修编号',
    student_id INT NOT NULL COMMENT '申报学生编号',
    room_id INT NOT NULL COMMENT '维修房间编号',
    repair_type VARCHAR(100) NOT NULL COMMENT '维修类型',
    description TEXT DEFAULT NULL COMMENT '维修描述',
    image_path VARCHAR(255) DEFAULT NULL COMMENT '图片路径',
    status ENUM('pending','processing','completed') NOT NULL DEFAULT 'pending' COMMENT '维修状态',
    submit_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '提交时间',
    handle_time DATETIME DEFAULT NULL COMMENT '处理时间',
    handler_id INT DEFAULT NULL COMMENT '处理人编号',
    result TEXT DEFAULT NULL COMMENT '处理结果说明',
    result_image_path VARCHAR(255) DEFAULT NULL COMMENT '处理结果图片路径',
    CONSTRAINT fk_repair_student
        FOREIGN KEY (student_id)
        REFERENCES student(student_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT fk_repair_room
        FOREIGN KEY (room_id)
        REFERENCES room(room_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT fk_repair_handler
        FOREIGN KEY (handler_id)
        REFERENCES apartment_manager(manager_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
)ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='维修记录表';

CREATE INDEX idx_repair_student ON repair_request(student_id);
CREATE INDEX idx_repair_room ON repair_request(room_id);
CREATE INDEX idx_repair_status ON repair_request(status);

-- 8.访客登记表
CREATE TABLE visitor_log(
    visitor_id INT PRIMARY KEY AUTO_INCREMENT COMMENT '访客编号',
    visitor_name VARCHAR(50) NOT NULL COMMENT '访客姓名',
    visitor_phone VARCHAR(20) DEFAULT NULL COMMENT '访客联系电话',
    id_card VARCHAR(30) DEFAULT NULL COMMENT '访客身份证号',
    student_id INT NOT NULL COMMENT '被访学生编号',
    room_id INT NOT NULL COMMENT '被访房间编号',
    visit_reason VARCHAR(255) DEFAULT NULL COMMENT '访问事由',
    visit_time DATETIME NOT NULL COMMENT '访问时间',
    leave_time DATETIME DEFAULT NULL COMMENT '离开时间',
    register_manager_id INT DEFAULT NULL COMMENT '登记管理员编号',
    remark TEXT DEFAULT NULL COMMENT '备注信息',
    CONSTRAINT fk_visitor_student
        FOREIGN KEY (student_id)
        REFERENCES student(student_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT fk_visitor_room
        FOREIGN KEY (room_id)
        REFERENCES room(room_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    CONSTRAINT chk_visit_times CHECK (leave_time IS NULL OR leave_time >= visit_time)
)ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='访客登记表';

CREATE INDEX idx_visitor_student ON visitor_log(student_id);
CREATE INDEX idx_visitor_room ON visitor_log(room_id);
CREATE INDEX idx_visitor_visit_time ON visitor_log(visit_time);

-- 9.公告表
CREATE TABLE notice(
    notice_id INT PRIMARY KEY AUTO_INCREMENT COMMENT '公告编号',
    title VARCHAR(255) NOT NULL COMMENT '公告标题',
    content TEXT NOT NULL COMMENT '公告内容',
    image_path VARCHAR(255) DEFAULT NULL COMMENT '公告图片路径',
    file_path VARCHAR(255) DEFAULT NULL COMMENT '公告附件路径',
    video_path VARCHAR(255) DEFAULT NULL COMMENT '公告视频路径',
    publish_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '发布时间',
    publisher_id INT DEFAULT NULL COMMENT '发布人编号',
    CONSTRAINT fk_notice_publisher
        FOREIGN KEY (publisher_id)
        REFERENCES apartment_manager(manager_id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
)ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='公告表';

CREATE INDEX idx_notice_publisher ON notice(publisher_id);
CREATE INDEX idx_notice_publish_time ON notice(publish_time);

-- 10.系统日志表
CREATE TABLE system_log(
    log_id INT PRIMARY KEY AUTO_INCREMENT COMMENT '日志编号',
    user_id INT NOT NULL COMMENT '操作用户编号',
    operation VARCHAR(100) NOT NULL COMMENT '操作类型',
    operation_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',
    ip_address VARCHAR(50) DEFAULT NULL COMMENT 'IP地址',
    description TEXT DEFAULT NULL COMMENT '操作说明',
    CONSTRAINT fk_log_user
        FOREIGN KEY (user_id)
        REFERENCES user_account(user_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
)ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统日志表';

CREATE INDEX idx_log_user ON system_log(user_id);
CREATE INDEX idx_log_operation_time ON system_log(operation_time);