-- Master Data Tables
CREATE TABLE IF NOT EXISTS departments (
    department_id INT PRIMARY KEY,
    department_code VARCHAR(50),
    department_name VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id INT PRIMARY KEY,
    job_code VARCHAR(50),
    job_title VARCHAR(100) NOT NULL,
    job_level VARCHAR(50),
    salary_grade VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS shifts (
    shift_id INT PRIMARY KEY,
    shift_code VARCHAR(50),
    shift_name VARCHAR(50),
    start_time TIME,
    end_time TIME
);

CREATE TABLE IF NOT EXISTS stores (
    store_id INT PRIMARY KEY,
    outlet_code VARCHAR(50),
    outlet_name VARCHAR(200),
    city VARCHAR(100),
    region VARCHAR(100),
    size_label VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS employees (
    employee_id INT PRIMARY KEY,
    employee_code VARCHAR(50),
    full_name VARCHAR(100) NOT NULL,
    sex VARCHAR(10),
    birth_date DATE,
    hire_date DATE,
    job_id INT,
    department_id INT,
    store_id INT,
    employment_status VARCHAR(50),
    FOREIGN KEY (job_id) REFERENCES jobs(job_id),
    FOREIGN KEY (department_id) REFERENCES departments(department_id),
    FOREIGN KEY (store_id) REFERENCES stores(store_id)
);

-- Transactional Data Tables
CREATE TABLE IF NOT EXISTS attendance_logs (
    attendance_log_id INT PRIMARY KEY,
    employee_id INT NOT NULL,
    attendance_date DATE NOT NULL,
    shift_id INT NOT NULL,
    check_in_time TIME,
    check_out_time TIME,
    attendance_status VARCHAR(50),
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
    FOREIGN KEY (shift_id) REFERENCES shifts(shift_id)
);

CREATE TABLE IF NOT EXISTS payroll_transactions (
    payroll_transaction_id INT PRIMARY KEY,
    employee_id INT NOT NULL,
    payroll_period VARCHAR(50),
    base_salary DECIMAL(15, 2),
    overtime_pay DECIMAL(15, 2),
    bonus DECIMAL(15, 2),
    deduction DECIMAL(15, 2),
    total_salary DECIMAL(15, 2),
    payment_date DATE,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);

CREATE TABLE IF NOT EXISTS performance_logs (
    performance_log_id INT PRIMARY KEY,
    employee_id INT NOT NULL,
    performance_date DATE NOT NULL,
    store_id INT NOT NULL,
    sales_amount DECIMAL(15, 2),
    customer_rating DECIMAL(3, 2),
    tasks_completed INT,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
    FOREIGN KEY (store_id) REFERENCES stores(store_id)
);
