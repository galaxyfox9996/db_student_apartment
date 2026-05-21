USE student_apartment_system;

SHOW TABLES;
SELECT * FROM student;

SELECT * FROM room;

SELECT * FROM accommodation;

SELECT room_id, room_no, capacity, current_count,
       func_get_available_beds(room_id) AS available_beds
FROM room;

CALL proc_auto_assign_room(3, 1, 'quad');
SELECT * FROM accommodation WHERE student_id = 3;
SELECT * FROM room WHERE apartment_id = 1;

ALTER DATABASE student_apartment_system 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_general_ci;

ALTER TABLE user_account 
CONVERT TO CHARACTER SET utf8mb4 
COLLATE utf8mb4_general_ci;

ALTER TABLE student 
CONVERT TO CHARACTER SET utf8mb4 
COLLATE utf8mb4_general_ci;

ALTER TABLE apartment_manager 
CONVERT TO CHARACTER SET utf8mb4 
COLLATE utf8mb4_general_ci;

ALTER TABLE apartment 
CONVERT TO CHARACTER SET utf8mb4 
COLLATE utf8mb4_general_ci;

ALTER TABLE room 
CONVERT TO CHARACTER SET utf8mb4 
COLLATE utf8mb4_general_ci;

ALTER TABLE accommodation 
CONVERT TO CHARACTER SET utf8mb4 
COLLATE utf8mb4_general_ci;

ALTER TABLE repair_request 
CONVERT TO CHARACTER SET utf8mb4 
COLLATE utf8mb4_general_ci;

ALTER TABLE visitor_log
CONVERT TO CHARACTER SET utf8mb4 
COLLATE utf8mb4_general_ci;

ALTER TABLE notice 
CONVERT TO CHARACTER SET utf8mb4 
COLLATE utf8mb4_general_ci;

ALTER TABLE system_log 
CONVERT TO CHARACTER SET utf8mb4 
COLLATE utf8mb4_general_ci;

