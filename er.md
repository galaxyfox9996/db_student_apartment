```mermaid
erDiagram
    USER {
        int user_id PK
        varchar username
        varchar password
        varchar role
        int related_id
        varchar status
        datetime created_time
    }

    STUDENT {
        int student_id PK
        varchar student_no UK
        varchar name
        varchar gender
        varchar college
        varchar major
        varchar class_name
        varchar phone
        varchar email
        varchar checkin_status
    }

    APARTMENT_MANAGER {
        int manager_id PK
        varchar employee_no UK
        varchar name
        varchar gender
        varchar phone
        varchar email
        varchar status
    }

    APARTMENT {
        int apartment_id PK
        varchar apartment_name
        varchar address
        int floor_count
        int manager_id FK
        text description
    }

    ROOM {
        int room_id PK
        int apartment_id FK
        varchar room_no
        int floor
        varchar room_type
        int capacity
        int current_count
        varchar status
    }

    ACCOMMODATION {
        int accommodation_id PK
        int student_id FK
        int room_id FK
        varchar bed_no
        date checkin_date
        date checkout_date
        varchar status
    }

    REPAIR_REQUEST {
        int repair_id PK
        int student_id FK
        int room_id FK
        varchar repair_type
        text description
        varchar image_path
        varchar status
        datetime submit_time
        datetime handle_time
        int handler_id FK
        text result_description
        varchar result_file_path
    }

    VISITOR_RECORD {
        int visitor_id PK
        varchar visitor_name
        varchar visitor_phone
        varchar id_card
        int student_id FK
        int room_id FK
        varchar visit_reason
        datetime visit_time
        datetime leave_time
        int register_manager_id FK
        text remark
    }

    NOTICE {
        int notice_id PK
        varchar title
        text content
        int publisher_id FK
        datetime publish_time
        varchar file_path
        varchar video_path
        varchar status
    }

    SYSTEM_LOG {
        int log_id PK
        int user_id FK
        varchar operation
        datetime operation_time
        varchar ip_address
        text description
    }

    APARTMENT_MANAGER ||--o{ APARTMENT : manages
    APARTMENT ||--o{ ROOM : contains

    STUDENT ||--o{ ACCOMMODATION : has
    ROOM ||--o{ ACCOMMODATION : provides

    STUDENT ||--o{ REPAIR_REQUEST : submits
    ROOM ||--o{ REPAIR_REQUEST : belongs_to
    APARTMENT_MANAGER ||--o{ REPAIR_REQUEST : handles

    STUDENT ||--o{ VISITOR_RECORD : visited_by
    ROOM ||--o{ VISITOR_RECORD : visit_room
    APARTMENT_MANAGER ||--o{ VISITOR_RECORD : registers

    APARTMENT_MANAGER ||--o{ NOTICE : publishes

    USER ||--o{ SYSTEM_LOG : generates
```
