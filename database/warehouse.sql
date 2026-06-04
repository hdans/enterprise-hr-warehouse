CREATE TABLE IF NOT EXISTS dim_job (
    job_id      INT PRIMARY KEY,
    job_code    VARCHAR(50),
    job_title   VARCHAR(100) NOT NULL,
    job_level   VARCHAR(50),
    salary_grade VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS dim_department (
    department_id   INT PRIMARY KEY,
    department_code VARCHAR(50),
    department_name VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_store (
    store_id    INT PRIMARY KEY,
    outlet_code VARCHAR(50),
    store_name  VARCHAR(200),
    city        VARCHAR(100),
    region      VARCHAR(100),
    size_label  VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS dim_shift (
    shift_id    INT PRIMARY KEY,
    shift_code  VARCHAR(50),
    shift_name  VARCHAR(50),
    start_time  TIME,
    end_time    TIME
);

CREATE TABLE IF NOT EXISTS dim_date (
    date_id     INT PRIMARY KEY,     
    full_date   DATE NOT NULL,
    day         INT  NOT NULL,
    month       INT  NOT NULL,
    quarter     INT  NOT NULL,
    year        INT  NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_employee (
    employee_id     INT PRIMARY KEY,
    employee_code   VARCHAR(50),
    employee_name   VARCHAR(100) NOT NULL,
    gender          VARCHAR(10),
    birth_date      DATE,
    hire_date       DATE,
    employment_status VARCHAR(50),
    job_id          INT,
    department_id   INT,
    store_id        INT,
    FOREIGN KEY (job_id)        REFERENCES dim_job(job_id),
    FOREIGN KEY (department_id) REFERENCES dim_department(department_id),
    FOREIGN KEY (store_id)      REFERENCES dim_store(store_id)
);

CREATE TABLE IF NOT EXISTS fact_employee_performance (
    performance_id  INT PRIMARY KEY,
    employee_id     INT NOT NULL,
    date_id         INT NOT NULL,
    store_id        INT NOT NULL,
    job_id          INT,
    shift_id        INT,
    sales_amount    DECIMAL(15, 2),
    customer_rating DECIMAL(3, 2),
    tasks_completed INT,
    FOREIGN KEY (employee_id) REFERENCES dim_employee(employee_id),
    FOREIGN KEY (date_id)     REFERENCES dim_date(date_id),
    FOREIGN KEY (store_id)    REFERENCES dim_store(store_id),
    FOREIGN KEY (job_id)      REFERENCES dim_job(job_id),
    FOREIGN KEY (shift_id)    REFERENCES dim_shift(shift_id)
);

CREATE TABLE IF NOT EXISTS fact_payroll (
    payroll_id      INT PRIMARY KEY,
    employee_id     INT NOT NULL,
    date_id         INT NOT NULL,
    job_id          INT,
    department_id   INT,
    store_id        INT,
    payroll_period  VARCHAR(50),
    base_salary     DECIMAL(15, 2),
    bonus           DECIMAL(15, 2),
    overtime_pay    DECIMAL(15, 2),
    deduction       DECIMAL(15, 2),
    total_salary    DECIMAL(15, 2),
    FOREIGN KEY (employee_id)   REFERENCES dim_employee(employee_id),
    FOREIGN KEY (date_id)       REFERENCES dim_date(date_id),
    FOREIGN KEY (job_id)        REFERENCES dim_job(job_id),
    FOREIGN KEY (department_id) REFERENCES dim_department(department_id),
    FOREIGN KEY (store_id)      REFERENCES dim_store(store_id)
);

CREATE TABLE IF NOT EXISTS fact_attendance (
    attendance_id       INT PRIMARY KEY,
    employee_id         INT NOT NULL,
    date_id             INT NOT NULL,
    shift_id            INT NOT NULL,
    store_id            INT,
    check_in_time       TIME,
    check_out_time      TIME,
    hours_worked        DECIMAL(5, 2),
    overtime_hours      DECIMAL(5, 2),
    attendance_status   VARCHAR(50),
    FOREIGN KEY (employee_id) REFERENCES dim_employee(employee_id),
    FOREIGN KEY (date_id)     REFERENCES dim_date(date_id),
    FOREIGN KEY (shift_id)    REFERENCES dim_shift(shift_id),
    FOREIGN KEY (store_id)    REFERENCES dim_store(store_id)
);