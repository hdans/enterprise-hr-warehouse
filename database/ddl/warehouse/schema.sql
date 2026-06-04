-- Data Warehouse Star Schema DDL

-- =========================================================
-- 1. DIMENSION TABLES
-- =========================================================

CREATE TABLE dim_employee (
    employee_id INT PRIMARY KEY,
    employee_code VARCHAR(50) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    sex VARCHAR(10),
    birth_date DATE,
    hire_date DATE,
    employment_status VARCHAR(50)
);

CREATE TABLE dim_job (
    job_id INT PRIMARY KEY,
    job_code VARCHAR(50) NOT NULL,
    job_title VARCHAR(100) NOT NULL
);

CREATE TABLE dim_department (
    department_id INT PRIMARY KEY,
    department_code VARCHAR(50) NOT NULL,
    department_name VARCHAR(100) NOT NULL
);

CREATE TABLE dim_store (
    store_id INT PRIMARY KEY,
    outlet_code VARCHAR(50) NOT NULL
);

CREATE TABLE dim_shift (
    shift_id INT PRIMARY KEY,
    shift_code VARCHAR(50) NOT NULL,
    start_time TIME,
    end_time TIME
);

CREATE TABLE dim_date (
    date_id INT PRIMARY KEY, -- Format YYYYMMDD
    full_date DATE NOT NULL,
    day INT NOT NULL,
    month INT NOT NULL,
    year INT NOT NULL,
    quarter INT NOT NULL,
    day_of_week INT NOT NULL,
    is_weekend BOOLEAN NOT NULL
);

-- =========================================================
-- 2. FACT TABLES
-- =========================================================

CREATE TABLE fact_attendance (
    attendance_log_id INT PRIMARY KEY,
    employee_id INT NOT NULL,
    date_id INT NOT NULL,
    shift_id INT NOT NULL,
    check_in_time TIME,
    check_out_time TIME,
    attendance_status VARCHAR(50),
    FOREIGN KEY (employee_id) REFERENCES dim_employee(employee_id),
    FOREIGN KEY (date_id) REFERENCES dim_date(date_id),
    FOREIGN KEY (shift_id) REFERENCES dim_shift(shift_id)
);

CREATE TABLE fact_payroll (
    payroll_transaction_id INT PRIMARY KEY,
    employee_id INT NOT NULL,
    date_id INT NOT NULL,
    base_salary DECIMAL(15,2),
    overtime_pay DECIMAL(15,2),
    bonus DECIMAL(15,2),
    deduction DECIMAL(15,2),
    total_salary DECIMAL(15,2),
    FOREIGN KEY (employee_id) REFERENCES dim_employee(employee_id),
    FOREIGN KEY (date_id) REFERENCES dim_date(date_id)
);

CREATE TABLE fact_performance (
    performance_log_id INT PRIMARY KEY,
    employee_id INT NOT NULL,
    store_id INT NOT NULL,
    date_id INT NOT NULL,
    sales_amount DECIMAL(15,2),
    customer_rating DECIMAL(3,2),
    tasks_completed INT,
    FOREIGN KEY (employee_id) REFERENCES dim_employee(employee_id),
    FOREIGN KEY (store_id) REFERENCES dim_store(store_id),
    FOREIGN KEY (date_id) REFERENCES dim_date(date_id)
);
