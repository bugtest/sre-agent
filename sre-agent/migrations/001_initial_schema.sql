-- SRE Agent 初始数据库迁移
-- 创建时间：2026-03-14
-- 版本：v0.1.0

-- 启用扩展
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 告警记录表
CREATE TABLE alerts (
    id BIGSERIAL PRIMARY KEY,
    alert_name VARCHAR(200) NOT NULL,
    service_name VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL, -- critical/warning/info
    triggered_at TIMESTAMP NOT NULL,
    resolved_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'open', -- open/investigating/resolved
    metric_name VARCHAR(100),
    metric_value DECIMAL(10, 2),
    threshold DECIMAL(10, 2),
    labels JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 告警表索引
CREATE INDEX idx_alerts_name ON alerts(alert_name);
CREATE INDEX idx_alerts_service ON alerts(service_name);
CREATE INDEX idx_alerts_status ON alerts(status);
CREATE INDEX idx_alerts_service_status ON alerts(service_name, status);
CREATE INDEX idx_alerts_triggered_at ON alerts(triggered_at);
CREATE INDEX idx_alerts_labels ON alerts USING GIN(labels);

-- 问题分析记录表
CREATE TABLE investigations (
    id BIGSERIAL PRIMARY KEY,
    alert_id BIGINT NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    root_cause TEXT,
    analysis_result JSONB,
    related_logs JSONB,
    related_metrics JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 分析表索引
CREATE INDEX idx_investigations_alert_id ON investigations(alert_id);
CREATE INDEX idx_investigations_created_at ON investigations(created_at);

-- 解决方案/操作手册表
CREATE TABLE runbooks (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    alert_pattern VARCHAR(200),
    description TEXT,
    steps JSONB NOT NULL,
    success_rate DECIMAL(5, 2) DEFAULT 0.0,
    risk_level VARCHAR(20) DEFAULT 'medium', -- low/medium/high
    requires_approval BOOLEAN DEFAULT TRUE,
    estimated_duration_seconds BIGINT DEFAULT 60,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Runbook 表索引
CREATE INDEX idx_runbooks_alert_pattern ON runbooks(alert_pattern);
CREATE INDEX idx_runbooks_risk_level ON runbooks(risk_level);

-- 执行记录表
CREATE TABLE executions (
    id BIGSERIAL PRIMARY KEY,
    investigation_id BIGINT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
    runbook_id BIGINT NOT NULL REFERENCES runbooks(id),
    status VARCHAR(20) NOT NULL, -- pending/running/success/failed/rolled_back
    executed_by VARCHAR(100),
    approved_by VARCHAR(100),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    result JSONB,
    rollback_result JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 执行表索引
CREATE INDEX idx_executions_investigation_id ON executions(investigation_id);
CREATE INDEX idx_executions_runbook_id ON executions(runbook_id);
CREATE INDEX idx_executions_status ON executions(status);
CREATE INDEX idx_executions_status_created ON executions(status, created_at);

-- 事故报告表
CREATE TABLE incidents (
    id BIGSERIAL PRIMARY KEY,
    alert_id BIGINT NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    summary TEXT,
    timeline JSONB,
    impact TEXT,
    root_cause TEXT,
    lessons_learned JSONB,
    mttr_seconds BIGINT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 事故表索引
CREATE INDEX idx_incidents_alert_id ON incidents(alert_id);
CREATE INDEX idx_incidents_created_at ON incidents(created_at);

-- 唯一约束：一个告警对应一个事故
CREATE UNIQUE INDEX idx_incidents_alert_unique ON incidents(alert_id);

-- 更新时间触发器函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为 runbooks 表添加更新时间触发器
CREATE TRIGGER update_runbooks_updated_at
    BEFORE UPDATE ON runbooks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 插入初始 Runbook 数据
INSERT INTO runbooks (title, alert_pattern, description, steps, success_rate, risk_level, requires_approval, estimated_duration_seconds) VALUES
('扩容 Pod CPU 资源', 'HighCPU', '当 Pod CPU 使用率过高时，增加 CPU 限制', 
 '[{"step": 1, "action": "get_pod", "description": "获取 Pod 当前配置"}, {"step": 2, "action": "update_cpu_limit", "description": "更新 CPU 限制为 2000m"}, {"step": 3, "action": "verify", "description": "验证 Pod 正常运行"}]',
 95.5, 'low', false, 30),

('扩容 Pod 内存资源', 'HighMemory', '当 Pod 内存使用率过高时，增加内存限制',
 '[{"step": 1, "action": "get_pod", "description": "获取 Pod 当前配置"}, {"step": 2, "action": "update_memory_limit", "description": "更新内存限制为 4Gi"}, {"step": 3, "action": "verify", "description": "验证 Pod 正常运行"}]',
 93.2, 'low', false, 30),

('重启问题 Pod', 'PodCrashLoop|PodError', '重启处于异常状态的 Pod',
 '[{"step": 1, "action": "get_pod_status", "description": "获取 Pod 状态"}, {"step": 2, "action": "delete_pod", "description": "删除 Pod（ReplicaSet 会自动重建）"}, {"step": 3, "action": "wait_ready", "description": "等待新 Pod 就绪"}]',
 85.0, 'medium', true, 60),

('服务扩容（增加副本）', 'HighLoad|HighLatency', '增加服务副本数以分担负载',
 '[{"step": 1, "action": "get_deployment", "description": "获取当前 Deployment 配置"}, {"step": 2, "action": "scale_up", "description": "副本数 +1"}, {"step": 3, "action": "wait_ready", "description": "等待新副本就绪"}, {"step": 4, "action": "verify", "description": "验证负载下降"}]',
 90.0, 'low', false, 120),

('清理磁盘空间', 'LowDiskSpace', '清理服务器磁盘空间',
 '[{"step": 1, "action": "check_disk_usage", "description": "检查磁盘使用情况"}, {"step": 2, "action": "clean_logs", "description": "清理旧日志文件"}, {"step": 3, "action": "clean_cache", "description": "清理缓存"}, {"step": 4, "action": "verify", "description": "验证磁盘空间释放"}]',
 88.5, 'medium', true, 180),

('数据库连接池扩容', 'HighDBConnections', '增加数据库连接池大小',
 '[{"step": 1, "action": "get_db_config", "description": "获取当前数据库配置"}, {"step": 2, "action": "update_pool_size", "description": "增加连接池大小"}, {"step": 3, "action": "verify", "description": "验证连接数下降"}]',
 82.0, 'medium', true, 60);

-- 创建视图：活跃告警
CREATE VIEW active_alerts AS
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
CREATE VIEW alert_stats AS
SELECT 
    service_name,
    COUNT(*) as total_alerts,
    COUNT(CASE WHEN status = 'resolved' THEN 1 END) as resolved_count,
    COUNT(CASE WHEN status = 'open' THEN 1 END) as open_count,
    AVG(EXTRACT(EPOCH FROM (resolved_at - triggered_at))) as avg_mttr_seconds
FROM alerts
GROUP BY service_name;

-- 权限设置（根据实际环境调整）
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO sre_agent;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO sre_agent;

COMMENT ON TABLE alerts IS '告警记录表 - 存储所有告警事件';
COMMENT ON TABLE investigations IS '问题分析记录表 - 存储告警分析结果';
COMMENT ON TABLE runbooks IS '解决方案/操作手册表 - 存储标准修复操作';
COMMENT ON TABLE executions IS '执行记录表 - 存储 Runbook 执行记录';
COMMENT ON TABLE incidents IS '事故报告表 - 存储重大事故报告';
