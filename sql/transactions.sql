USE student_apartment_system;

-- =========================================
-- transactions.sql
-- 学生公寓管理系统事务示例
-- 事务：学生换宿
-- =========================================

DROP PROCEDURE IF EXISTS proc_change_room;

DELIMITER $$
CREATE PROCEDURE proc_change_room(
    IN p_student_id INT,
    IN p_new_room_id INT,
    IN p_new_bed_no INT
)
BEGIN
    DECLARE v_old_accommodation_id INT DEFAULT NULL;
    DECLARE v_old_room_id INT DEFAULT NULL;
    DECLARE v_available_room_count INT DEFAULT 0;

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        -- 发生异常时回滚事务
        ROLLBACK;
        SELECT '换宿失败，发生异常' AS message;
    END;

    START TRANSACTION;
    -- 1. 获取学生当前的住宿信息
    SELECT accommodation_id, room_id
    INTO v_old_accommodation_id, v_old_room_id
    FROM accommodation
    WHERE student_id = p_student_id AND status = 'living'
    LIMIT 1;

    IF v_old_accommodation_id IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '学生当前没有住宿记录';
    END IF;

    -- 2. 判断该床位是否有人
    SELECT COUNT(*) INTO v_available_room_count
    FROM accommodation    
    WHERE room_id = p_new_room_id AND bed_no = p_new_bed_no AND status = 'living';

    IF v_available_room_count > 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '该床位已经有人入住';
    END IF;

    -- 3. 更新原住宿记录的状态为 changed
    UPDATE accommodation
    SET status = 'changed', check_out_date = CURDATE()
    WHERE accommodation_id = v_old_accommodation_id AND status = 'living';

    -- 4. 插入新的住宿记录
    INSERT INTO accommodation (student_id, room_id, bed_no, check_in_date, status)
    VALUES (p_student_id, p_new_room_id, p_new_bed_no, CURDATE(), 'living');

    -- 5.更新学生入住状态
    UPDATE student
    SET check_status = 'checked_in'
    WHERE student_id = p_student_id;

    COMMIT;
    SELECT '换宿成功' AS message,
    p_student_id AS student_id,
    v_old_room_id AS old_room_id,
    p_new_room_id AS new_room_id,
    p_new_bed_no AS new_bed_no;
END $$
DELIMITER ;
    