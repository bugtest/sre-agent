# 测试计划 - SRE Agent

**创建日期**: 2026-03-14  
**创建者**: Test Agent  
**状态**: draft

---

## 1. 测试范围

### 1.1 测试模块
| 模块 | 测试类型 | 优先级 |
|------|----------|--------|
| 告警接收器 | 单元测试 + 集成测试 | P0 |
| 分析引擎 | 单元测试 + 集成测试 | P0 |
| 知识库 | 单元测试 + 集成测试 | P1 |
| 执行引擎 | 单元测试 + 集成测试 + E2E | P0 |
| API 接口 | 集成测试 | P0 |
| 安全控制 | 安全测试 | P0 |

### 1.2 不测试范围
- 第三方系统内部逻辑（Prometheus/Loki/K8s）
- UI 界面（第一阶段无 UI）

---

## 2. 测试用例

### 2.1 告警接收器测试

#### TC-ALERT-001: 接收有效告警
- **输入**: 有效的告警 JSON
- **预期**: 返回 200，生成 alert_id
- **优先级**: P0

#### TC-ALERT-002: 接收无效告警
- **输入**: 缺少必填字段的告警
- **预期**: 返回 400，错误信息清晰
- **优先级**: P0

#### TC-ALERT-003: 告警风暴处理
- **输入**: 100 条相同告警在 1 秒内
- **预期**: 聚合处理，不重复分析
- **优先级**: P1

### 2.2 分析引擎测试

#### TC-ANALYSIS-001: 指标数据分析
- **输入**: CPU 告警 + 指标数据
- **预期**: 正确识别 CPU 异常模式
- **优先级**: P0

#### TC-ANALYSIS-002: 日志关联分析
- **输入**: 告警 + 时间段日志
- **预期**: 找到相关错误日志
- **优先级**: P0

#### TC-ANALYSIS-003: 多源数据关联
- **输入**: 指标 + 日志 + 链路数据
- **预期**: 综合分析报告
- **优先级**: P0

#### TC-ANALYSIS-004: 数据源不可用降级
- **输入**: 日志系统不可用
- **预期**: 基于指标继续分析，标注数据缺失
- **优先级**: P1

### 2.3 知识库测试

#### TC-KB-001: Runbook 创建
- **输入**: 有效 Runbook 数据
- **预期**: 创建成功，可查询
- **优先级**: P1

#### TC-KB-002: 相似度搜索
- **输入**: 告警上下文
- **预期**: 返回相似历史案例
- **优先级**: P1

#### TC-KB-003: 成功率统计
- **输入**: 多次执行记录
- **预期**: 正确计算成功率
- **优先级**: P2

### 2.4 执行引擎测试

#### TC-EXEC-001: 执行低风险操作
- **输入**: low risk Runbook，已审批
- **预期**: 执行成功，记录结果
- **优先级**: P0

#### TC-EXEC-002: 执行高风险操作未审批
- **输入**: high risk Runbook，无审批
- **预期**: 拒绝执行，返回 403
- **优先级**: P0

#### TC-EXEC-003: 执行失败回滚
- **输入**: 会失败的操作
- **预期**: 自动回滚，记录回滚结果
- **优先级**: P0

#### TC-EXEC-004: K8s 资源更新
- **输入**: 更新 Pod 资源限制
- **预期**: K8s 资源正确更新
- **优先级**: P0

#### TC-EXEC-005: Pod 重启
- **输入**: 重启指定 Pod
- **预期**: Pod 重启成功
- **优先级**: P0

### 2.5 API 集成测试

#### TC-API-001: 完整告警处理流程
- **步骤**:
  1. POST /alerts 提交告警
  2. GET /alerts/{id}/analysis 获取分析
  3. GET /alerts/{id}/solutions 获取方案
  4. POST /executions 执行修复
  5. GET /executions/{id} 确认结果
- **预期**: 全流程成功，MTTR < 2 分钟
- **优先级**: P0

#### TC-API-002: 并发告警处理
- **输入**: 10 个告警并发提交
- **预期**: 所有告警正确处理，无丢失
- **优先级**: P1

### 2.6 安全测试

#### TC-SEC-001: 未授权访问
- **输入**: 无 Token 访问 API
- **预期**: 返回 401
- **优先级**: P0

#### TC-SEC-002: 权限不足
- **输入**: Operator 尝试执行 Admin 操作
- **预期**: 返回 403
- **优先级**: P0

#### TC-SEC-003: 审计日志记录
- **输入**: 执行修复操作
- **预期**: 审计日志完整记录
- **优先级**: P0

#### TC-SEC-004: 敏感信息脱敏
- **输入**: 包含敏感数据的日志
- **预期**: 输出中敏感信息已脱敏
- **优先级**: P0

---

## 3. 测试数据

### 3.1 模拟告警数据
```json
{
  "HighCPUUsage": {
    "alert_name": "HighCPUUsage",
    "service_name": "payment-service",
    "severity": "critical",
    "metric_value": 95.5,
    "threshold": 80
  },
  "HighMemoryUsage": {
    "alert_name": "HighMemoryUsage",
    "service_name": "order-service",
    "severity": "warning",
    "metric_value": 85.0,
    "threshold": 80
  },
  "ServiceDown": {
    "alert_name": "ServiceDown",
    "service_name": "user-service",
    "severity": "critical"
  }
}
```

### 3.2 模拟 Runbook
```json
{
  "scale-up-pod": {
    "title": "扩容 Pod 资源",
    "steps": [
      {"action": "get_pod", "params": {"name": "{{pod_name}}"}},
      {"action": "update_resources", "params": {"cpu": "2000m", "memory": "4Gi"}}
    ],
    "risk_level": "low",
    "requires_approval": false
  },
  "restart-pod": {
    "title": "重启 Pod",
    "steps": [
      {"action": "delete_pod", "params": {"name": "{{pod_name}}"}}
    ],
    "risk_level": "medium",
    "requires_approval": true
  }
}
```

---

## 4. 测试环境

### 4.1 环境配置
| 组件 | 配置 | 用途 |
|------|------|------|
| K8s Cluster | Kind 本地集群 | 执行测试 |
| Prometheus | 模拟指标数据 | 分析测试 |
| Loki | 模拟日志数据 | 分析测试 |
| PostgreSQL | 测试数据库 | 数据存储 |

### 4.2 测试数据准备
```bash
# 部署测试 K8s 资源
kubectl apply -f tests/fixtures/test-pods.yaml

# 导入测试告警数据
psql -h localhost -U postgres -d sre_test -f tests/fixtures/test_alerts.sql

# 导入测试 Runbook
psql -h localhost -U postgres -d sre_test -f tests/fixtures/test_runbooks.sql
```

---

## 5. 覆盖率目标

| 模块 | 语句覆盖率 | 分支覆盖率 |
|------|------------|------------|
| 告警接收器 | 90% | 85% |
| 分析引擎 | 85% | 80% |
| 执行引擎 | 90% | 85% |
| API 接口 | 95% | 90% |
| **整体** | **80%** | **75%** |

---

## 6. 测试执行计划

### Phase 1: 单元测试
- **时间**: Week 3
- **执行者**: Dev Agent + Test Agent
- **目标**: 核心模块单元测试

### Phase 2: 集成测试
- **时间**: Week 4
- **执行者**: Test Agent
- **目标**: 模块间集成 + 外部系统集成

### Phase 3: E2E 测试
- **时间**: Week 4
- **执行者**: Test Agent
- **目标**: 完整告警→分析→解决流程

### Phase 4: 安全测试
- **时间**: Week 4
- **执行者**: Test Agent
- **目标**: 权限、审计、回滚测试

---

## 7. 通过标准

- [ ] 所有 P0 测试用例通过
- [ ] P1 测试用例通过率 > 95%
- [ ] 测试覆盖率达标（80%+）
- [ ] 无严重 Bug
- [ ] 安全测试通过

---

## 8. 风险和问题

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| K8s 测试环境不稳定 | 测试阻塞 | 准备 Mock 备用 |
| 外部系统 API 变更 | 集成测试失败 | 版本锁定 + Mock |
| 测试数据不足 | 覆盖率不达标 | 提前准备数据生成脚本 |

---

**下一步**:
- [ ] Dev Agent: 完成数据模型实现后通知 Test Agent
- [ ] Test Agent: 准备测试数据和 Mock 服务
- [ ] Test Agent: 编写单元测试框架
