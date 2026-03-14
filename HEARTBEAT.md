# HEARTBEAT.md - 定时任务调度

## 调度规则

### 每 30 分钟
- **所有代理**: 检查 STATE.yaml，继续进行中的任务
- **Architect**: 审查是否有新需求需要分析

### 每小时
- **Test Agent**: 检查 CI/CD 测试结果，更新质量报告
- **Dev Agent**: 检查未处理的 Code Review 和 Issue

### 每天 8:00 AM
- **Architect**: 生成晨间简报
  - 项目整体状态
  - 今日任务计划
  - 阻塞项提醒

### 每天 6:00 PM
- **Test Agent**: 生成质量日报
  - 测试覆盖率
  - Bug 统计
  - CI/CD 状态

### 每周一 9:00 AM
- **Architect**: 制定本周优先级
- **Test Agent**: 生成周质量报告

### 每周五 5:00 PM
- **所有代理**: 周总结
  - 本周完成
  - 遗留问题
  - 下周计划
