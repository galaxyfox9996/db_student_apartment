USE student_apartment_system;

-- =========================================
-- functions.sql
-- 学生公寓管理系统函数设计
-- 函数：计算指定房间的剩余床位数
-- =========================================

DROP FUNCTION IF EXISTS func_get_available_beds;
DELIMITER $$
CREATE FUNCTION func_get_available_beds(p_room_id INT)
RETURNS INT
DETERMINISTIC
READS SQL DATA
BEGIN
    DECLARE total_beds INT;
    DECLARE current_count INT;
    DECLARE available_beds INT;

    SELECT capacity , current_count
    INTO total_beds, current_count
    FROM room
    WHERE room_id = p_room_id;

    SET available_beds = total_beds - current_count;

    RETURN available_beds;
END $$
DELIMITER ;