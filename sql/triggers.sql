USE student_apartment_system;

-- =========================================
-- triggers.sql
-- 学生公寓管理系统触发器设计
-- =========================================
DROP TRIGGER IF EXISTS trg_after_student_check_in;
DROP TRIGGER IF EXISTS trg_after_accommodation_update;
DROP TRIGGER IF EXISTS trg_after_repair_report_insert;
DROP TRIGGER IF EXISTS trg_after_repair_status_update;

DELIMITER $$
-- 1.触发器：当学生入住时，更新房间的当前入住人数
CREATE TRIGGER trg_after_student_check_in
AFTER INSERT ON accommodation
FOR EACH ROW
BEGIN
    IF NEW.status = 'living' THEN
        UPDATE room
        SET current_count = current_count + 1
        WHERE room_id = NEW.room_id;
    END IF;
END $$


-- 触发器2：住宿状态更新后，自动更新房间当前入住人数
CREATE TRIGGER trg_after_accommodation_update
AFTER UPDATE ON accommodation
FOR EACH ROW
BEGIN
    IF OLD.status = 'living' AND NEW.status IN ('checkout','changed') THEN
        UPDATE room
        SET current_count = current_count - 1
        WHERE room_id = NEW.room_id
        AND current_count > 0; 
END IF;
END $$

-- 触发器3：新增维修申报后，自动写入系统日志
CREATE TRIGGER trg_after_repair_report_insert
AFTER INSERT ON repair_request
FOR EACH ROW
BEGIN
    DECLARE v_user_id INT DEFAULT NULL;
    SELECT user_id 
    INTO v_user_id
    FROM user_account
    WHERE role = 'student' AND related_id = NEW.student_id
    LIMIT 1;

    IF v_user_id IS NOT NULL THEN
        INSERT INTO system_log (user_id,operation,ip_address,description)
        VALUES (v_user_id,'提交维修申报',NULL,CONCAT('学生提交维修申报，维修编号:',NEW.repair_id));
    END IF;
END $$

-- 触发器4：维修状态更新为 completed 时，自动设置处理时间
CREATE TRIGGER trg_after_repair_status_update
BEFORE UPDATE ON repair_request
FOR EACH ROW
BEGIN
    IF NEW.status = 'completed' AND OLD.status <> 'completed' AND NEW.handle_time IS NULL
     THEN
        SET NEW.handle_time = NOW();
    END IF;
END $$
DELIMITER ;