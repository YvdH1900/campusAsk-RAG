-- ================================================
-- CampusAsk-RAG 数据库初始化脚本
-- ================================================
-- 此脚本会删除旧数据库并创建新数据库
-- 所有时间字段使用 DATETIME 类型，存储北京时间
-- ================================================

-- 删除旧数据库（如果存在）
DROP DATABASE IF EXISTS campus_ask_rag;

-- 创建新数据库
CREATE DATABASE campus_ask_rag 
DEFAULT CHARACTER SET utf8mb4 
DEFAULT COLLATE utf8mb4_unicode_ci;

-- 使用数据库
USE campus_ask_rag;

-- ================================================
-- 1. 用户表
-- ================================================
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '用户 ID',
    username VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
    email VARCHAR(100) UNIQUE COMMENT '邮箱',
    hashed_password VARCHAR(255) NOT NULL COMMENT '哈希密码',
    role VARCHAR(20) NOT NULL DEFAULT 'student' COMMENT '用户角色：student/teacher/admin',
    is_active BOOLEAN NOT NULL DEFAULT TRUE COMMENT '是否激活',
    pending_approval BOOLEAN NOT NULL DEFAULT FALSE COMMENT '是否待审核（教师注册）',
    approval_status VARCHAR(20) NOT NULL DEFAULT 'approved' COMMENT '审核状态：pending/approved/rejected',
    ban_until DATETIME COMMENT '封禁截止时间',
    can_modify_profile BOOLEAN NOT NULL DEFAULT TRUE COMMENT '是否允许修改个人信息',
    max_questions_per_day INT NOT NULL DEFAULT 100 COMMENT '每日最大提问次数',
    max_uploads_per_day INT NOT NULL DEFAULT 10 COMMENT '每日最大上传文件次数',
    questions_today INT NOT NULL DEFAULT 0 COMMENT '今日已提问次数',
    uploads_today INT NOT NULL DEFAULT 0 COMMENT '今日已上传次数',
    last_reset_date DATE COMMENT '上次重置计数日期',
    current_session_id VARCHAR(100) COMMENT '当前登录会话 ID',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_username (username),
    INDEX idx_email (email),
    INDEX idx_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- ================================================
-- 2. 对话会话表
-- ================================================
CREATE TABLE chat_sessions (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '会话 ID',
    user_id INT NOT NULL COMMENT '用户 ID',
    title VARCHAR(200) NOT NULL COMMENT '会话标题',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='对话会话表';

-- ================================================
-- 3. 对话消息表
-- ================================================
CREATE TABLE messages (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '消息 ID',
    session_id INT NOT NULL COMMENT '会话 ID',
    role VARCHAR(20) NOT NULL COMMENT '消息角色：user/assistant',
    content TEXT NOT NULL COMMENT '消息内容',
    sources TEXT COMMENT '引用来源 (JSON 格式)',
    confidence VARCHAR(20) COMMENT '答案置信度: 高/中/低',
    features TEXT COMMENT '功能状态 (JSON 格式)',
    token_usage TEXT COMMENT 'Token 使用详情 (JSON 格式)',
    feedback VARCHAR(10) COMMENT '用户反馈：up/down',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_session_id (session_id),
    INDEX idx_created_at (created_at),
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='对话消息表';

-- ================================================
-- 4. 文档表
-- ================================================
CREATE TABLE documents (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '文档 ID',
    filename VARCHAR(255) NOT NULL COMMENT '文件名',
    file_path VARCHAR(500) NOT NULL COMMENT '文件存储路径',
    file_size INT NOT NULL DEFAULT 0 COMMENT '文件大小 (字节)',
    category VARCHAR(50) COMMENT '文档分类',
    description TEXT COMMENT '文档描述',
    status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '处理状态：pending/processing/completed/failed',
    review_status VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '审核状态：pending/approved/rejected',
    reviewed_by INT COMMENT '审核人 ID',
    reviewed_at DATETIME COMMENT '审核时间',
    reject_reason TEXT COMMENT '驳回理由',
    uploaded_by INT COMMENT '上传人 ID',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_status (status),
    INDEX idx_review_status (review_status),
    INDEX idx_uploaded_by (uploaded_by),
    INDEX idx_created_at (created_at),
    FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='文档表';

-- ================================================
-- 5. 公告表
-- ================================================
CREATE TABLE announcements (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '公告 ID',
    title VARCHAR(200) NOT NULL COMMENT '公告标题',
    content TEXT NOT NULL COMMENT '公告内容',
    is_active BOOLEAN NOT NULL DEFAULT TRUE COMMENT '是否启用',
    is_popup BOOLEAN NOT NULL DEFAULT TRUE COMMENT '是否弹窗显示',
    show_once BOOLEAN NOT NULL DEFAULT TRUE COMMENT '是否只显示一次',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_is_active (is_active),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='公告表';

-- ================================================
-- 6. 系统设置表
-- ================================================
CREATE TABLE system_settings (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '设置 ID',
    setting_key VARCHAR(100) NOT NULL UNIQUE COMMENT '设置键',
    setting_value VARCHAR(500) COMMENT '设置值',
    description VARCHAR(500) COMMENT '设置描述',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_setting_key (setting_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统设置表';

-- ================================================
-- 7. 登录记录表
-- ================================================
CREATE TABLE login_records (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '记录 ID',
    user_id INT NOT NULL COMMENT '用户 ID',
    username VARCHAR(50) NOT NULL COMMENT '用户名',
    login_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '登录时间',
    ip_address VARCHAR(50) COMMENT 'IP 地址',
    user_agent VARCHAR(500) COMMENT '浏览器信息',
    success BOOLEAN NOT NULL DEFAULT TRUE COMMENT '登录是否成功',
    failure_reason VARCHAR(200) COMMENT '失败原因',
    INDEX idx_user_id (user_id),
    INDEX idx_login_time (login_time),
    INDEX idx_success (success)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='登录记录表';

-- ================================================
-- 8. 模型配置表
-- ================================================
CREATE TABLE model_configs (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '配置 ID',
    model_type VARCHAR(20) NOT NULL COMMENT '模型类型：llm/embedding',
    model_name VARCHAR(100) NOT NULL COMMENT '模型名称',
    api_key VARCHAR(500) NOT NULL COMMENT 'API 密钥',
    api_base_url VARCHAR(500) COMMENT 'API 基础 URL',
    dimension INT DEFAULT NULL COMMENT '向量维度（仅 embedding 模型）',
    is_active BOOLEAN NOT NULL DEFAULT FALSE COMMENT '是否启用',
    is_default BOOLEAN NOT NULL DEFAULT FALSE COMMENT '是否默认',
    config JSON COMMENT '额外配置 (JSON)',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_model_type (model_type),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='模型配置表';

-- ================================================
-- 9. 问题统计表
-- ================================================
CREATE TABLE question_stats (
    id INT PRIMARY KEY AUTO_INCREMENT COMMENT '统计 ID',
    content VARCHAR(500) NOT NULL COMMENT '问题内容',
    count INT NOT NULL DEFAULT 1 COMMENT '提问次数',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '首次提问时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
    INDEX idx_question_stats_content (content),
    INDEX idx_question_stats_count (count)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='问题统计表';

-- ================================================
-- 插入默认数据
-- ================================================

-- 默认管理员账号（由应用首次启动时通过代码自动创建）
-- 密码通过环境变量 DEFAULT_ADMIN_PASSWORD 设置，未设置时自动生成随机密码
-- 如果数据库已存在管理员账号，则跳过创建
-- INSERT INTO users (username, email, hashed_password, role, is_active) 
-- VALUES ('admin', 'admin@example.com', '<auto-generated>', 'admin', TRUE);

-- 默认系统设置
INSERT INTO system_settings (setting_key, setting_value, description) VALUES
('registration_enabled', 'true', '是否允许注册'),
('login_enabled', 'true', '是否允许登录');

-- ================================================
-- 完成提示
-- ================================================
SELECT '数据库初始化完成！' AS message;
