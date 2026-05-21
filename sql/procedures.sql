USE student_apartment_system;

-- =========================================
-- procedures.sql
-- 学生公寓管理系统存储过程设计
-- 存储过程：自动分配宿舍
-- =========================================

DROP PROCEDURE IF EXISTS proc_auto_assign_room;
DELIMITER $$
CREATE PROCEDURE proc_auto_assign_room(
    IN p_student_id INT,
    IN p_apartment_id INT,
    IN p_room_type VARCHAR(20)
)
BEGIN
    DECLARE v_student_count INT DEFAULT 0;
    DECLARE v_living_count INT DEFAULT 0;
    DECLARE v_room_id INT DEFAULT NULL;
    DECLARE v_bed_no INT DEFAULT NULL;
    DECLARE v_current_count INT DEFAULT 0;
    DECLARE v_error_message TEXT DEFAULT '';
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        -- 发生异常时回滚事务
        GET DIAGNOSTICS CONDITION 1 v_error_message = MESSAGE_TEXT;
        ROLLBACK;
        SELECT CONCAT('分配宿舍失败，原因：', v_error_message) AS message;
    END;

    START TRANSACTION;
    -- 1. 判断学生是否存在
    SELECT COUNT(*) INTO v_student_count
    FROM student
    WHERE student_id = p_student_id;

    IF v_student_count = 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '学生不存在';
    END IF;

    -- 2. 判断学生是否已经入住
    SELECT COUNT(*) INTO v_living_count
    FROM accommodation
    WHERE student_id = p_student_id AND status = 'living';

    IF v_living_count > 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '学生已经入住';
    END IF;

    -- 3. 查找符合条件的空闲房间
    SELECT room_id, current_count
    INTO v_room_id, v_current_count
    FROM room
    WHERE apartment_id = p_apartment_id
    AND room_type = p_room_type
    AND status = 'normal'
    AND current_count < capacity
    ORDER BY floor ASC, room_no ASC
    LIMIT 1;

    IF v_room_id IS NULL THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '没有符合条件的空闲房间';
    END IF;

    -- 4. 分配床位号
    SET v_bed_no = v_current_count + 1;

    -- 5. 插入住宿记录
    INSERT INTO accommodation (student_id, room_id, bed_no, check_in_date, status)
    VALUES (p_student_id, v_room_id, v_bed_no, CURDATE(), 'living');

    -- 6. 更新房间当前入住人数
    UPDATE student
    SET check_status = 'checked_in'
    WHERE student_id = p_student_id;

    COMMIT;
    -- 7.更新入住状态
    SELECT CONCAT('分配成功，房间ID:', v_room_id, '，床位号:', v_bed_no) AS message,
            p_student_id AS student_id,
            v_room_id AS room_id,
            v_bed_no AS bed_no;
END $$
DELIMITER ;

