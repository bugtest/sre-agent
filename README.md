# SRE Agent - 智能运维问题定位与解决系统

基于 OpenClaw 多代理架构的智能 SRE 系统，实现告警自动分析、根因定位和自主修复。

## 🎯 核心能力

- **智能告警分析**: 10+ 内置规则引擎，自动识别 CPU、内存、服务宕机等问题
- **知识库驱动**: 基于历史案例和 Runbook 的智能推荐
- **自主修复**: K8s 集成，支持 Pod 重启、扩容、资源更新等自动修复
- **持续学习**: 基于执行结果的成功率学习和置信度提升

## 🏗️ 架构

```
┌─────────────────────────────────────────────────────────────┐
│                    SRE Agent Core                           │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐              │
│  │ 告警接收器 │  │ 分析引擎   │  │ 执行引擎   │              │
│  │ Alert     │  │ Analysis  │  │ Execution │              │
│  │ Receiver  │  │ Engine    │  │ Engine    │              │
│  └───────────┘  └───────────┘  └───────────┘              │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐              │
│  │ 知识库     │  │ 决策引擎   │  │ K8s 集成    │              │
│  │ Knowledge │  │ Decision  │  │ Kubernetes│              │
│  │ Base      │  │ Engine    │  │ Client    │              │
│  └───────────┘  └───────────┘  └───────────┘              │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 1. 安装依赖

```bash
cd sre-agent
pip install -r requirements.txt
```

### 2. 初始化数据库

```bash
psql -U postgres -f migrations/001_initial_schema.sql
```

### 3. 运行测试

```bash
pytest tests/unit/ -v
```

### 4. 启动服务

```bash
# TODO: 添加启动脚本
python -m uvicorn src.api.main:app --reload
```

## 📊 项目进度

- [x] 数据模型 (5 个核心表)
- [x] 告警接收器 (Webhook + 风暴抑制)
- [x] 分析引擎 (10+ 规则)
- [x] 知识库 (Runbook 管理 + 智能搜索)
- [x] 执行引擎 (审批 + 回滚)
- [x] K8s 集成 (Pod 操作 + 扩容)
- [ ] Prometheus 集成
- [ ] Loki 集成

**测试状态**: 19/19 单元测试通过 ✅

## 📁 项目结构

```
my-dev-team/
├── sre-agent/
│   ├── src/
│   │   ├── models/           # 数据模型
│   │   ├── core/             # 核心引擎
│   │   ├── services/         # 服务层
│   │   ├── integrations/     # 外部集成
│   │   └── api/              # API 层
│   ├── tests/
│   │   └── unit/             # 单元测试
│   ├── migrations/           # 数据库迁移
│   └── requirements.txt      # 依赖
├── docs/                     # 文档
│   └── sre-agent/
│       ├── REQUIREMENTS.md   # 需求文档
│       ├── DESIGN.md         # 设计文档
│       └── API.md            # API 文档
├── tests/                    # 测试计划
└── STATE.yaml                # 项目状态
```

## 🔧 核心功能

### 告警接收
```bash
POST /api/v1/alerts
{
  "alert_name": "HighCPUUsage",
  "service_name": "payment-service",
  "severity": "critical",
  "metric_value": 95.5
}
```

### 智能分析
- 规则引擎：10+ 内置规则（CPU、内存、磁盘、延迟等）
- 历史学习：相似案例置信度 +10%
- 根因输出：可能原因排序 + 建议动作

### 知识库搜索
```python
# 根据告警名称搜索 Runbook
runbooks = kb.search_runbooks_by_alert('HighCPUUsage')
# 返回：[CPU 扩容，内存扩容，...]
```

### K8s 操作
```python
# 重启 Pod
k8s.restart_pod("payment-service-abc123")

# 扩容 Deployment
k8s.scale_deployment("payment-service", replicas=3)

# 更新资源限制
k8s.update_pod_resources("payment-service-abc123", cpu="2000m", memory="4Gi")
```

## 📈 测试覆盖率

| 模块 | 测试数 | 通过率 |
|------|--------|--------|
| 数据模型 | 5 | 100% |
| 知识库 | 6 | 100% |
| 执行引擎 | 8 | 100% |
| **总计** | **19** | **100%** |

## 🛠️ 技术栈

- **后端**: Python 3.12+, FastAPI
- **数据库**: PostgreSQL 15+
- **ORM**: SQLAlchemy 2.0
- **测试**: pytest
- **K8s**: kubernetes-python (可选)

## 📝 开发笔记

### 模拟模式
K8s 客户端默认使用模拟模式，无需真实集群即可测试：
```python
client = KubernetesClient()  # mock_mode=True
client.restart_pod("test-pod")
```

### 成功率学习
使用移动平均更新 Runbook 成功率：
```
new_rate = old_rate * 0.9 + (1.0 if success else 0.0) * 0.1
```

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

---

**项目状态**: 🟢 开发中 (87% 完成)  
**最后更新**: 2026-03-14
