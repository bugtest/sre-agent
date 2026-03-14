-- SRE Agent 初始数据库迁移 (MySQL 版本)
-- 创建时间：2026-03-14
-- 版本：v0.1.0

-- 创建数据库（如果需要）
-- CREATE DATABASE IF NOT EXISTS sre_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 使用数据库
USE sre_db;

-- 告警记录表
CREATE TABLE alerts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    alert_name VARCHAR(200) NOT NULL,
    service_name VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL COMMENT 'critical/warning/info',
    triggered_at DATETIME NOT NULL,
    resolved_at DATETIME,
    status VARCHAR(20) DEFAULT 'open' COMMENT 'open/investigating/resolved',
    metric_name VARCHAR(100),
    metric_value DECIMAL(10, 2),
    threshold DECIMAL(10, 2),
    labels JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_alerts_name (alert_name),
    INDEX idx_alerts_service (service_name),
    INDEX idx_alerts_status (status),
    INDEX idx_alerts_service_status (service_name, status),
    INDEX idx_alerts_triggered_at (triggered_at),
    INDEX idx_alerts_labels ((CAST(labels->>'$.instance' AS CHAR(100))))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='告警记录表 - 存储所有告警事件';

-- 问题分析记录表
CREATE TABLE investigations (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    alert_id BIGINT NOT NULL,
    root_cause TEXT,
    analysis_result JSON,
    related_logs JSON,
    related_metrics JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_investigations_alert_id (alert_id),
    INDEX idx_investigations_created_at (created_at),
    CONSTRAINT fk_investigations_alert FOREIGN KEY (alert_id) REFERENCES alerts(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='问题分析记录表 - 存储告警分析结果';

-- 解决方案/操作手册表
CREATE TABLE runbooks (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    alert_pattern VARCHAR(200),
    description TEXT,
    steps JSON NOT NULL,
    success_rate DECIMAL(5, 2) DEFAULT 0.0,
    risk_level VARCHAR(20) DEFAULT 'medium' COMMENT 'low/medium/high',
    requires_approval BOOLEAN DEFAULT TRUE,
    estimated_duration_seconds BIGINT DEFAULT 60,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_runbooks_alert_pattern (alert_pattern),
    INDEX idx_runbooks_risk_level (risk_level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='解决方案/操作手册表 - 存储标准修复操作';

-- 执行记录表
CREATE TABLE executions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    investigation_id BIGINT NOT NULL,
    runbook_id BIGINT NOT NULL,
    status VARCHAR(20) NOT NULL COMMENT 'pending/running/success/failed/rolled_back',
    executed_by VARCHAR(100),
    approved_by VARCHAR(100),
    started_at DATETIME,
    completed_at DATETIME,
    result JSON,
    rollback_result JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_executions_investigation_id (investigation_id),
    INDEX idx_executions_runbook_id (runbook_id),
    INDEX idx_executions_status (status),
    INDEX idx_executions_status_created (status, created_at),
    CONSTRAINT fk_executions_investigation FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE,
    CONSTRAINT fk_executions_runbook FOREIGN KEY (runbook_id) REFERENCES runbooks(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='执行记录表 - 存储 Runbook 执行记录';

-- 事故报告表
CREATE TABLE incidents (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    alert_id BIGINT NOT NULL UNIQUE,
    title VARCHAR(200) NOT NULL,
    summary TEXT,
    timeline JSON,
    impact TEXT COMMENT '影响范围',
    root_cause TEXT,
    lessons_learned JSON COMMENT '改进建议',
    mttr_seconds BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_incidents_alert_id (alert_id),
    INDEX idx_incidents_created_at (created_at),
    CONSTRAINT fk_incidents_alert FOREIGN KEY (alert_id) REFERENCES alerts(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='事故报告表 - 存储重大事故报告';

-- 更新时间触发器
DELIMITER $$

CREATE TRIGGER update_runbooks_updated_at
BEFORE UPDATE ON runbooks
FOR EACH ROW
BEGIN
    SET NEW.updated_at = NOW();
END$$

DELIMITER ;

-- 插入初始 Runbook 数据
INSERT INTO runbooks (title, alert_pattern, description, steps, success_rate, risk_level, requires_approval, estimated_duration_seconds) VALUES
('扩容 Pod CPU 资源', 'HighCPU', '当 Pod CPU 使用率过高时，增加 CPU 限制', 
 '[{"step": 1, "action": "get_pod", "description": "获取 Pod 当前配置"}, {"step": 2, "action": "update_cpu_limit", "description": "更新 CPU 限制为 2000m"}, {"step": 3, "action": "verify", "description": "验证 Pod 正常运行"}]',
 95.5, 'low', FALSE, 30),

('扩容 Pod 内存资源', 'HighMemory', '当 Pod 内存使用率过高时，增加内存限制',
 '[{"step": 1, "action": "get_pod", "description": "获取 Pod 当前配置"}, {"step": 2, "action": "update_memory_limit", "description": "更新内存限制为 4Gi"}, {"step": 3, "action": "verify", "description": "验证 Pod 正常运行"}]',
 93.2, 'low', FALSE, 30),

('重启问题 Pod', 'PodCrashLoop|PodError', '重启处于异常状态的 Pod',
 '[{"step": 1, "action": "get_pod_status", "description": "获取 Pod 状态"}, {"step": 2, "action": "delete_pod", "description": "删除 Pod（ReplicaSet 会自动重建）"}, {"step": 3, "action": "wait_ready", "description": "等待新 Pod 就绪"}]',
 85.0, 'medium', TRUE, 60),

('服务扩容（增加副本）', 'HighLoad|HighLatency', '增加服务副本数以分担负载',
 '[{"step": 1, "action": "get_deployment", "description": "获取当前 Deployment 配置"}, {"step": 2, "action": "scale_up", "description": "副本数 +1"}, {"step": 3, "action": "wait_ready", "description": "等待新副本就绪"}, {"step": 4, "action": "verify", "description": "验证负载下降"}]',
 90.0, 'low', FALSE, 120),

('清理磁盘空间', 'LowDiskSpace', '清理服务器磁盘空间',
 '[{"step": 1, "action": "check_disk_usage", "description": "检查磁盘使用情况"}, {"step": 2, "action": "clean_logs", "description": "清理旧日志文件"}, {"step": 3, "action": "clean_cache", "description": "清理缓存"}, {"step": 4, "action": "verify", "description": "验证磁盘空间释放"}]',
 88.5, 'medium', TRUE, 180),

('数据库连接池扩容', 'HighDBConnections', '增加数据库连接池大小',
 '[{"step": 1, "action": "get_db_config", "description": "获取当前数据库配置"}, {"step": 2, "action": "update_pool_size", "description": "增加连接池大小"}, {"step": 3, "action": "verify", "description": "验证连接数下降"}]',
 82.0, 'medium', TRUE, 60);

-- 创建视图：活跃告警
CREATE OR REPLACE VIEW active_alerts AS
SELECT * FROM alerts
WHERE status IN ('open', 'investigating')
ORDER BY 
    CASE severity 
        WHEN 'critical' THEN 1 
        WHEN 'warning' THEN 2 
        WHEN 'info' THEN 3 
    END,
    triggered_at DESC;

-- 创建视图：告警统计
CREATE OR REPLACE VIEW alert_stats AS
SELECT 
    service_name,
    COUNT(*) as total_alerts,
    SUM(CASE WHEN status = 'resolved' THEN 1 ELSE 0 END) as resolved_count,
    SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open_count,
    AVG(TIMESTAMPDIFF(SECOND, triggered_at, resolved_at)) as avg_mttr_seconds
FROM alerts
GROUP BY service_name;

-- 插入测试数据（可选）
-- INSERT INTO alerts (alert_name, service_name, severity, triggered_at, metric_name, metric_value, threshold, labels) VALUES
-- ('HighCPUUsage', 'payment-service', 'critical', NOW(), 'cpu_usage', 95.5, 80.0, '{"instance": "prod-payment-01", "namespace": "production"}');
