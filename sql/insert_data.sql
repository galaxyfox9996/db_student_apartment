USE student_apartment_system;

-- =========================================
-- 1. 插入公寓管理员
-- =========================================
INSERT INTO apartment_manager
(employee_no, name, gender, phone, email, status)
VALUES
('M2026001', '张老师', 'male', '13800000001', 'zhang@example.com', 'active'),
('M2026002', '李老师', 'female', '13800000002', 'li@example.com', 'active');

-- =========================================
-- 2. 插入学生
-- =========================================
INSERT INTO student
(student_no, name, gender, college, major, class, phone, email, check_status)
VALUES
('20260001', '王小明', 'male', '计算机学院', '软件工程', '软件2601', '13900000001', 'wang@example.com', 'checked_in'),
('20260002', '赵小红', 'female', '计算机学院', '数据科学', '数据2601', '13900000002', 'zhao@example.com', 'checked_in'),
('20260003', '刘小强', 'male', '信息学院', '网络工程', '网络2601', '13900000003', 'liu@example.com', 'not_checked_in');

-- =========================================
-- 3. 插入用户账号
-- =========================================
INSERT INTO user_account
(username, password, role, related_id, status)
VALUES
('admin', '123456', 'admin', 0, 'active'),
('manager001', '123456', 'manager', 1, 'active'),
('manager002', '123456', 'manager', 2, 'active'),
('20260001', '123456', 'student', 1, 'active'),
('20260002', '123456', 'student', 2, 'active'),
('20260003', '123456', 'student', 3, 'active');

-- =========================================
-- 4. 插入公寓
-- =========================================
INSERT INTO apartment
(apartment_name, address, floor_count, manager_id, description)
VALUES
('一号公寓', '校园东区', 6, 1, '主要入住男生'),
('二号公寓', '校园西区', 6, 2, '主要入住女生');

-- =========================================
-- 5. 插入房间
-- =========================================
INSERT INTO room
(apartment_id, room_no, floor, room_type, capacity, current_count, status)
VALUES
(1, '101', 1, 'quad', 4, 1, 'normal'),
(1, '102', 1, 'quad', 4, 0, 'normal'),
(1, '201', 2, 'quad', 4, 0, 'normal'),
(2, '101', 1, 'quad', 4, 1, 'normal'),
(2, '102', 1, 'quad', 4, 0, 'normal'),
(2, '201', 2, 'quad', 4, 0, 'repairing');

-- =========================================
-- 6. 插入住宿记录
-- =========================================
INSERT INTO accommodation
(student_id, room_id, bed_no, check_in_date, check_out_date, status)
VALUES
(1, 1, 1, '2026-05-01', NULL, 'living'),
(2, 4, 1, '2026-05-01', NULL, 'living');

-- =========================================
-- 7. 插入维修申报
-- =========================================
INSERT INTO repair_request
(student_id, room_id, repair_type, description, image_path, status, submit_time, handler_id, result)
VALUES
(1, 1, '水电维修', '宿舍灯管损坏，需要更换。', '/uploads/repair_images/light.jpg', 'pending', NOW(), NULL, NULL),
(2, 4, '门窗维修', '窗户无法正常关闭。', '/uploads/repair_images/window.jpg', 'processing', NOW(), 2, '已联系维修人员处理');

-- =========================================
-- 8. 插入访客记录
-- =========================================
INSERT INTO visitor_log
(visitor_name, visitor_phone, id_card, student_id, room_id, visit_reason, visit_time, leave_time, register_manager_id, remark)
VALUES
('王先生', '13700000001', '110101199901010011', 1, 1, '探望学生', '2026-05-15 10:00:00', '2026-05-15 11:00:00', 1, '正常离开'),
('赵女士', '13700000002', '110101199902020022', 2, 4, '送生活用品', '2026-05-15 14:00:00', NULL, 2, '尚未登记离开');

-- =========================================
-- 9. 插入公告
-- =========================================
INSERT INTO notice
(title, content, publisher_id, file_path, image_path, video_path)
VALUES
('关于宿舍安全检查的通知', '本周五下午进行宿舍安全检查，请同学们提前整理宿舍。', 1, '/uploads/notice_files/safety.pdf', NULL, NULL),
('公寓消防安全宣传', '请同学们认真学习消防安全知识。', 2, NULL, '/uploads/notice_images/fire.jpg', '/uploads/notice_videos/fire_safety.mp4');

-- =========================================
-- 10. 插入系统日志
-- =========================================
INSERT INTO system_log
(user_id, operation, ip_address, description)
VALUES
(1, '初始化数据', '127.0.0.1', '系统管理员初始化测试数据');