-- =====================================================================
-- Employee Management System - MySQL 8.x Schema
-- 19 tables.  Run:  mysql -u root -p < schema.sql  (or: python create_db.py)
-- =====================================================================
CREATE DATABASE IF NOT EXISTS employee_management
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE employee_management;

-- 1. ROLES
CREATE TABLE roles (
    role_id     INT AUTO_INCREMENT PRIMARY KEY,
    role_name   VARCHAR(50) NOT NULL UNIQUE,
    description VARCHAR(255)
) ENGINE=InnoDB;

-- 2. PERMISSIONS
CREATE TABLE permissions (
    permission_id    INT AUTO_INCREMENT PRIMARY KEY,
    permission_name  VARCHAR(100) NOT NULL UNIQUE,
    description      VARCHAR(255)
) ENGINE=InnoDB;

-- 3. ROLE_PERMISSIONS (many-to-many)
CREATE TABLE role_permissions (
    role_id        INT NOT NULL,
    permission_id  INT NOT NULL,
    PRIMARY KEY (role_id, permission_id),
    CONSTRAINT fk_rp_role FOREIGN KEY (role_id) REFERENCES roles(role_id) ON DELETE CASCADE,
    CONSTRAINT fk_rp_perm FOREIGN KEY (permission_id) REFERENCES permissions(permission_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 4. DEPARTMENTS
CREATE TABLE departments (
    department_id   INT AUTO_INCREMENT PRIMARY KEY,
    department_name VARCHAR(100) NOT NULL UNIQUE,
    description     VARCHAR(255),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 5. POSITIONS
CREATE TABLE positions (
    position_id    INT AUTO_INCREMENT PRIMARY KEY,
    department_id  INT NOT NULL,
    title          VARCHAR(100) NOT NULL,
    level          VARCHAR(50),
    CONSTRAINT fk_pos_dept FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 6. EMPLOYMENT TYPES
CREATE TABLE employment_types (
    employment_type_id INT AUTO_INCREMENT PRIMARY KEY,
    type_name          VARCHAR(50) NOT NULL UNIQUE
) ENGINE=InnoDB;

-- 7. SHIFTS
CREATE TABLE shifts (
    shift_id             INT AUTO_INCREMENT PRIMARY KEY,
    shift_name           VARCHAR(100) NOT NULL,
    start_time           TIME NOT NULL,
    end_time             TIME NOT NULL,
    grace_minutes        INT DEFAULT 15,
    late_cutoff          TIME,
    min_half_day_hours   DECIMAL(4,2) DEFAULT 4.00,
    max_ot_hours_per_day DECIMAL(4,2) DEFAULT 2.00,
    requires_ot_approval TINYINT(1) DEFAULT 1
) ENGINE=InnoDB;

-- 8. EMPLOYEES
CREATE TABLE employees (
    employee_id         INT AUTO_INCREMENT PRIMARY KEY,
    full_name           VARCHAR(150) NOT NULL,
    email               VARCHAR(190) NOT NULL UNIQUE,
    phone               VARCHAR(30),
    personal_email      VARCHAR(190) NULL UNIQUE,
    date_of_birth       DATE,
    date_joined         DATE NOT NULL,
    department_id       INT,
    position_id         INT,
    employment_type_id  INT,
    shift_id            INT,
    manager_id          INT,
    status              ENUM('Active','Inactive','Terminated') DEFAULT 'Active',
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_emp_dept    FOREIGN KEY (department_id)      REFERENCES departments(department_id),
    CONSTRAINT fk_emp_pos     FOREIGN KEY (position_id)        REFERENCES positions(position_id),
    CONSTRAINT fk_emp_type    FOREIGN KEY (employment_type_id) REFERENCES employment_types(employment_type_id),
    CONSTRAINT fk_emp_shift   FOREIGN KEY (shift_id)           REFERENCES shifts(shift_id),
    CONSTRAINT fk_emp_manager FOREIGN KEY (manager_id)         REFERENCES employees(employee_id)
) ENGINE=InnoDB;

-- 9. USERS (login / auth / 2FA)
CREATE TABLE users (
    user_id               INT AUTO_INCREMENT PRIMARY KEY,
    employee_id           INT UNIQUE,
    username              VARCHAR(100) NOT NULL UNIQUE,
    email                 VARCHAR(190) NOT NULL UNIQUE,
    password_hash         VARCHAR(255) NOT NULL,
    role_id               INT NOT NULL,
    role_name             ENUM('Admin','HR','Manager','Employee') NOT NULL,
    is_verified           TINYINT(1) DEFAULT 0,
    otp_code              VARCHAR(10),
    otp_expiry            DATETIME,
    verification_token    VARCHAR(255),
    must_reset_password   TINYINT(1) DEFAULT 1,
    failed_login_attempts INT DEFAULT 0,
    locked_until          DATETIME,
    is_active             TINYINT(1) DEFAULT 1,
    last_login            DATETIME,
    created_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
    totp_secret           VARCHAR(64),
    totp_enabled          TINYINT(1) DEFAULT 0,
    setup_token_hash      VARCHAR(64) NULL,
    setup_token_expiry    DATETIME NULL,
    setup_token_used_at   DATETIME NULL,
    setup_reminded_at     DATETIME NULL,
    CONSTRAINT fk_user_emp  FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE,
    CONSTRAINT fk_user_role FOREIGN KEY (role_id)     REFERENCES roles(role_id)
) ENGINE=InnoDB;

-- 10. ATTENDANCE
CREATE TABLE attendance (
    attendance_id  INT AUTO_INCREMENT PRIMARY KEY,
    employee_id    INT NOT NULL,
    shift_id       INT,
    work_date      DATE NOT NULL,
    check_in       DATETIME,
    check_out      DATETIME,
    total_hours    DECIMAL(5,2),
    status         ENUM('Pending','Present','Half Day','Absent') DEFAULT 'Pending',
    status_reason  VARCHAR(100),
    is_late        TINYINT(1) DEFAULT 0,
    created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_att_emp_date (employee_id, work_date),
    CONSTRAINT fk_att_emp   FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE,
    CONSTRAINT fk_att_shift FOREIGN KEY (shift_id)    REFERENCES shifts(shift_id)
) ENGINE=InnoDB;

-- 11. OVERTIME
CREATE TABLE overtime (
    overtime_id    INT AUTO_INCREMENT PRIMARY KEY,
    employee_id    INT NOT NULL,
    attendance_id  INT,
    work_date      DATE NOT NULL,
    hours          DECIMAL(4,2) NOT NULL,
    status         ENUM('Pending','Approved','Rejected') DEFAULT 'Pending',
    approved_by    INT,
    applied_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    decided_at     DATETIME,
    last_reminded_at DATETIME NULL,
    CONSTRAINT fk_ot_emp  FOREIGN KEY (employee_id)   REFERENCES employees(employee_id) ON DELETE CASCADE,
    CONSTRAINT fk_ot_att  FOREIGN KEY (attendance_id) REFERENCES attendance(attendance_id),
    CONSTRAINT fk_ot_user FOREIGN KEY (approved_by)   REFERENCES users(user_id)
) ENGINE=InnoDB;

-- 12. LEAVE TYPES
CREATE TABLE leave_types (
    leave_type_id     INT AUTO_INCREMENT PRIMARY KEY,
    type_name         VARCHAR(100) NOT NULL UNIQUE,
    max_days_per_year INT
) ENGINE=InnoDB;

-- 13. LEAVE REQUESTS
CREATE TABLE leave_requests (
    leave_request_id INT AUTO_INCREMENT PRIMARY KEY,
    employee_id      INT NOT NULL,
    leave_type_id    INT NOT NULL,
    start_date       DATE NOT NULL,
    end_date         DATE NOT NULL,
    reason           VARCHAR(500),
    status           ENUM('Pending','Approved','Rejected') DEFAULT 'Pending',
    approved_by      INT,
    applied_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    decided_at       DATETIME,
    last_reminded_at DATETIME NULL,
    CONSTRAINT fk_lr_emp   FOREIGN KEY (employee_id)   REFERENCES employees(employee_id) ON DELETE CASCADE,
    CONSTRAINT fk_lr_type  FOREIGN KEY (leave_type_id) REFERENCES leave_types(leave_type_id),
    CONSTRAINT fk_lr_user  FOREIGN KEY (approved_by)   REFERENCES users(user_id)
) ENGINE=InnoDB;

-- 14. LEAVE BALANCE
CREATE TABLE leave_balance (
    leave_balance_id INT AUTO_INCREMENT PRIMARY KEY,
    employee_id      INT NOT NULL,
    leave_type_id    INT NOT NULL,
    year             INT NOT NULL,
    allocated_days   DECIMAL(5,1) NOT NULL,
    used_days        DECIMAL(5,1) DEFAULT 0,
    UNIQUE KEY uq_lb (employee_id, leave_type_id, year),
    CONSTRAINT fk_lb_emp  FOREIGN KEY (employee_id)   REFERENCES employees(employee_id) ON DELETE CASCADE,
    CONSTRAINT fk_lb_type FOREIGN KEY (leave_type_id) REFERENCES leave_types(leave_type_id)
) ENGINE=InnoDB;

-- 15. LEAVE ATTACHMENTS
CREATE TABLE leave_attachments (
    attachment_id    INT AUTO_INCREMENT PRIMARY KEY,
    leave_request_id INT NOT NULL,
    file_path        VARCHAR(500) NOT NULL,
    file_name        VARCHAR(255),
    uploaded_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_la_lr FOREIGN KEY (leave_request_id) REFERENCES leave_requests(leave_request_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 16. HOLIDAYS
CREATE TABLE holidays (
    holiday_id   INT AUTO_INCREMENT PRIMARY KEY,
    holiday_date DATE NOT NULL UNIQUE,
    name         VARCHAR(150) NOT NULL
) ENGINE=InnoDB;

-- 17. NOTIFICATIONS
CREATE TABLE notifications (
    notification_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT NOT NULL,
    employee_id     INT,
    title           VARCHAR(200) NOT NULL,
    message         TEXT NOT NULL,
    reference_table VARCHAR(100),
    reference_id    INT,
    is_read         TINYINT(1) DEFAULT 0,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_nt_user FOREIGN KEY (user_id)     REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_nt_emp  FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
) ENGINE=InnoDB;

-- 17b. EMAIL QUEUE (queue + delivery history in one table)
CREATE TABLE email_queue (
    email_id        INT AUTO_INCREMENT PRIMARY KEY,
    to_address      VARCHAR(190) NOT NULL,
    user_id         INT NULL,
    category        VARCHAR(30)  NOT NULL,
    template        VARCHAR(50)  NOT NULL,
    subject         VARCHAR(255) NOT NULL,
    body            MEDIUMTEXT   NOT NULL,
    body_html       MEDIUMTEXT   NULL,
    status          ENUM('Pending','Sent','Failed') NOT NULL DEFAULT 'Pending',
    attempts        INT NOT NULL DEFAULT 0,
    last_error      VARCHAR(500) NULL,
    next_attempt_at DATETIME NOT NULL,
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sent_at         DATETIME NULL,
    CONSTRAINT fk_eq_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL,
    INDEX idx_eq_due (status, next_attempt_at),
    INDEX idx_eq_user (user_id)
) ENGINE=InnoDB;

-- 17c. EMAIL PREFERENCES (no row = enabled)
CREATE TABLE email_preferences (
    user_id  INT NOT NULL,
    category VARCHAR(30) NOT NULL,
    enabled  TINYINT(1) NOT NULL DEFAULT 1,
    PRIMARY KEY (user_id, category),
    CONSTRAINT fk_ep_user FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- 18. EMPLOYEE HISTORY
CREATE TABLE employee_history (
    history_id     INT AUTO_INCREMENT PRIMARY KEY,
    employee_id    INT NOT NULL,
    field_changed  VARCHAR(100) NOT NULL,
    old_value      VARCHAR(255),
    new_value      VARCHAR(255),
    changed_by     INT,
    changed_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_eh_emp  FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE,
    CONSTRAINT fk_eh_user FOREIGN KEY (changed_by)  REFERENCES users(user_id)
) ENGINE=InnoDB;

-- 19. AUDIT LOG
CREATE TABLE audit_log (
    log_id      INT AUTO_INCREMENT PRIMARY KEY,
    user_id     INT,
    action      VARCHAR(50) NOT NULL,
    table_name  VARCHAR(100) NOT NULL,
    record_id   INT,
    details     TEXT,
    `timestamp` DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_al_user FOREIGN KEY (user_id) REFERENCES users(user_id)
) ENGINE=InnoDB;

-- INDEXES
CREATE INDEX idx_attendance_employee_date ON attendance(employee_id, work_date);
CREATE INDEX idx_overtime_employee        ON overtime(employee_id);
CREATE INDEX idx_leave_employee           ON leave_requests(employee_id);
CREATE INDEX idx_employees_department     ON employees(department_id);
CREATE INDEX idx_leave_balance_employee   ON leave_balance(employee_id, year);
CREATE INDEX idx_notifications_user       ON notifications(user_id, is_read);
CREATE INDEX idx_users_setup_token        ON users(setup_token_hash);
CREATE INDEX idx_employee_history_emp     ON employee_history(employee_id);

-- SEED DATA
INSERT INTO roles (role_name, description) VALUES
    ('Admin','Full system access'),
    ('HR','Manage employees, attendance, leave approval'),
    ('Manager','View/approve team attendance & leave'),
    ('Employee','Self check-in/out, apply leave, view own records');

INSERT INTO employment_types (type_name) VALUES
    ('Full-time'),('Part-time'),('Contract'),('Intern'),('Probation');

INSERT INTO leave_types (type_name, max_days_per_year) VALUES
    ('Sick Leave',12),('Casual Leave',12),('Earned Leave',15),
    ('Unpaid Leave',NULL),('Maternity/Paternity Leave',90);

INSERT INTO permissions (permission_name, description) VALUES
    ('manage_employees','Edit/suspend/reactivate employee records'),
    ('assign_roles','Create employee accounts and assign/change their role (Admin: any role. HR: Manager/Employee only.)'),
    ('edit_employee_assignment','Edit an employee''s department/position/employment type/shift/manager only'),
    ('manage_departments','Add/edit departments & positions'),
    ('manage_shifts','Configure shift timings & rules'),
    ('manage_holidays','Add/edit company holidays'),
    ('edit_attendance','Manually correct attendance entries'),
    ('approve_leave','Approve/reject leave requests'),
    ('approve_overtime','Approve/reject overtime requests'),
    ('view_reports','View attendance/leave reports'),
    ('self_checkin','Mark own check-in/check-out'),
    ('apply_leave','Submit own leave requests'),
    ('edit_org_structure','Edit (not add/delete) existing departments, positions, and shifts');

INSERT INTO role_permissions (role_id, permission_id)
    SELECT (SELECT role_id FROM roles WHERE role_name='Admin'), permission_id FROM permissions;
INSERT INTO role_permissions (role_id, permission_id)
    SELECT (SELECT role_id FROM roles WHERE role_name='HR'), permission_id FROM permissions
    WHERE permission_name IN ('manage_employees','assign_roles','edit_employee_assignment','manage_holidays',
        'edit_attendance','approve_leave','approve_overtime','view_reports','self_checkin','apply_leave','edit_org_structure');
INSERT INTO role_permissions (role_id, permission_id)
    SELECT (SELECT role_id FROM roles WHERE role_name='Manager'), permission_id FROM permissions
    WHERE permission_name IN ('edit_employee_assignment','approve_leave','approve_overtime','view_reports',
        'self_checkin','apply_leave','edit_org_structure');
INSERT INTO role_permissions (role_id, permission_id)
    SELECT (SELECT role_id FROM roles WHERE role_name='Employee'), permission_id FROM permissions
    WHERE permission_name IN ('self_checkin','apply_leave');

INSERT INTO shifts (shift_name, start_time, end_time, grace_minutes, late_cutoff, min_half_day_hours, max_ot_hours_per_day, requires_ot_approval)
VALUES ('General Shift','09:00:00','18:00:00',15,'13:00:00',4.0,2.0,1);
