# API 文档 - SRE Agent

**版本**: 1.0.0  
**最后更新**: 2026-03-14  
**状态**: draft

---

## 1. 概述

### 1.1 基础信息
- **Base URL**: `/api/v1`
- **认证方式**: Bearer Token
- **数据格式**: JSON
- **字符编码**: UTF-8

### 1.2 通用响应格式
```json
{
  "code": 0,
  "message": "success",
  "data": {},
  "timestamp": 1234567890
}
```

### 1.3 错误码定义
| 错误码 | 描述 | HTTP 状态码 |
|--------|------|-------------|
| 0 | 成功 | 200 |
| 40001 | 请求参数错误 | 400 |
| 40101 | 未授权 | 401 |
| 40301 | 权限不足 | 403 |
| 40401 | 资源不存在 | 404 |
| 50001 | 服务器错误 | 500 |
| 50301 | 数据源不可用 | 503 |

---

## 2. 认证

### 2.1 获取 Token
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "string",
  "password": "string"
}
```

**响应**:
```json
{
  "code": 0,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "expires_in": 3600,
    "role": "operator"
  }
}
```

---

## 3. API 端点

### 3.1 告警管理

#### POST /alerts
接收告警

**请求**:
```json
{
  "alert_name": "HighCPUUsage",
  "service_name": "payment-service",
  "severity": "critical",
  "metric_name": "cpu_usage",
  "metric_value": 95.5,
  "threshold": 80,
  "labels": {
    "instance": "prod-payment-01",
    "namespace": "production"
  }
}
```

**响应 (200)**:
```json
{
  "code": 0,
  "data": {
    "alert_id": "alert-123",
    "status": "investigating",
    "analysis_url": "/api/v1/alerts/alert-123/analysis"
  }
}
```

#### GET /alerts/{id}
获取告警详情

**响应**:
```json
{
  "code": 0,
  "data": {
    "id": "alert-123",
    "alert_name": "HighCPUUsage",
    "service_name": "payment-service",
    "severity": "critical",
    "status": "resolved",
    "triggered_at": "2026-03-14T08:00:00Z",
    "resolved_at": "2026-03-14T08:15:00Z",
    "metric_value": 95.5,
    "threshold": 80
  }
}
```

#### GET /alerts/{id}/analysis
获取分析报告

**响应**:
```json
{
  "code": 0,
  "data": {
    "alert_id": "alert-123",
    "root_cause": "Pod 资源不足导致 CPU 飙升",
    "confidence": 0.85,
    "possible_causes": [
      {"cause": "流量突增", "probability": 0.6},
      {"cause": "代码性能问题", "probability": 0.3},
      {"cause": "资源配额不足", "probability": 0.1}
    ],
    "related_logs": [
      {"timestamp": "2026-03-14T08:00:00Z", "message": "CPU throttling detected", "level": "warn"}
    ],
    "related_metrics": {
      "cpu_usage": [95.5, 92.3, 88.1],
      "memory_usage": [70.2, 72.5, 75.8]
    }
  }
}
```

#### GET /alerts/{id}/solutions
获取推荐解决方案

**响应**:
```json
{
  "code": 0,
  "data": {
    "alert_id": "alert-123",
    "solutions": [
      {
        "runbook_id": "runbook-456",
        "title": "扩容 Pod 资源",
        "success_rate": 95.5,
        "risk_level": "low",
        "requires_approval": false,
        "estimated_duration": "30s",
        "steps": [
          {"step": 1, "action": "update_resource_limit", "target": "prod-payment-01"}
        ]
      },
      {
        "runbook_id": "runbook-457",
        "title": "重启问题 Pod",
        "success_rate": 80.0,
        "risk_level": "medium",
        "requires_approval": true,
        "estimated_duration": "60s"
      }
    ]
  }
}
```

### 3.2 执行管理

#### POST /executions
执行修复

**请求**:
```json
{
  "alert_id": "alert-123",
  "runbook_id": "runbook-456",
  "approved_by": "user-789",
  "parameters": {
    "target_pod": "prod-payment-01",
    "new_cpu_limit": "2000m"
  }
}
```

**响应 (202)**:
```json
{
  "code": 0,
  "data": {
    "execution_id": "exec-789",
    "status": "running",
    "estimated_duration": "30s",
    "status_url": "/api/v1/executions/exec-789"
  }
}
```

#### GET /executions/{id}
获取执行状态

**响应**:
```json
{
  "code": 0,
  "data": {
    "id": "exec-789",
    "alert_id": "alert-123",
    "runbook_id": "runbook-456",
    "status": "success",
    "executed_by": "user-789",
    "started_at": "2026-03-14T08:10:00Z",
    "completed_at": "2026-03-14T08:10:30Z",
    "result": {
      "message": "Pod resource limit updated successfully",
      "new_cpu_limit": "2000m"
    }
  }
}
```

#### POST /executions/{id}/rollback
回滚操作

**请求**:
```json
{
  "reason": "执行后服务异常"
}
```

**响应**:
```json
{
  "code": 0,
  "data": {
    "execution_id": "exec-789",
    "rollback_id": "rollback-001",
    "status": "running"
  }
}
```

### 3.3 事故报告

#### GET /incidents/{id}/report
获取事故报告

**响应**:
```json
{
  "code": 0,
  "data": {
    "id": "incident-001",
    "title": "Payment Service High CPU Incident",
    "summary": "CPU usage spiked to 95% due to traffic surge",
    "timeline": [
      {"time": "08:00", "event": "告警触发"},
      {"time": "08:02", "event": "开始分析"},
      {"time": "08:05", "event": "定位根因"},
      {"time": "08:10", "event": "执行扩容"},
      {"time": "08:15", "event": "服务恢复"}
    ],
    "impact": "支付服务响应时间增加 200%，持续 15 分钟",
    "root_cause": "流量突增导致 Pod 资源不足",
    "lessons_learned": [
      "需要增加自动扩容策略",
      "需要优化流量预测模型"
    ],
    "mttr_seconds": 900
  }
}
```

### 3.4 知识库

#### GET /runbooks
获取 Runbook 列表

**查询参数**:
| 参数 | 类型 | 描述 |
|------|------|------|
| alert_pattern | string | 告警模式过滤 |
| risk_level | string | 风险等级过滤 |

**响应**:
```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "id": "runbook-456",
        "title": "扩容 Pod 资源",
        "alert_pattern": "HighCPU",
        "success_rate": 95.5,
        "risk_level": "low"
      }
    ],
    "total": 10
  }
}
```

#### POST /runbooks
创建 Runbook

**请求**:
```json
{
  "title": "扩容 Pod 资源",
  "alert_pattern": "HighCPU",
  "steps": [
    {"step": 1, "action": "get_pod_info", "description": "获取 Pod 信息"},
    {"step": 2, "action": "update_resource_limit", "description": "更新资源限制"}
  ],
  "risk_level": "low",
  "requires_approval": false
}
```

---

## 4. 速率限制

| 端点 | 限制 |
|------|------|
| 默认 | 100 次/分钟 |
| /alerts | 1000 次/分钟（告警高峰） |
| /executions | 10 次/分钟（高危操作） |

---

## 5. Webhook

### 5.1 告警通知
```json
{
  "event": "alert.resolved",
  "alert_id": "alert-123",
  "resolution": "auto_fixed",
  "execution_id": "exec-789"
}
```

### 5.2 执行状态通知
```json
{
  "event": "execution.completed",
  "execution_id": "exec-789",
  "status": "success",
  "alert_id": "alert-123"
}
```

---

## 6. 变更日志

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| 1.0.0 | 2026-03-14 | 初始版本 |
