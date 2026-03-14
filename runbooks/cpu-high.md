# Runbook: CPU 高告警

## 告警条件
CPU 使用率 > 80% 持续 5 分钟

## 排查步骤

### 1. 登录服务器
```bash
ssh <server>
```

### 2. 查看进程
```bash
top -bn1
```

### 3. 查找CPU占用最高的进程
```bash
ps aux --sort=-%cpu | head -10
```

### 4. 查看进程详情
```bash
# 如果是Java进程
jps -l
jstack <pid>

# 如果是Node进程
ps aux | grep node
```

### 5. 查看系统日志
```bash
dmesg | tail -20
```

## 止血方案

### 方案1：重启进程
```bash
kill -15 <pid>  # 优雅重启
```

### 方案2：重启服务
```bash
systemctl restart <service>
```

### 方案3：扩容（如K8s）
```bash
kubectl scale deployment <name> --replicas=3
```

## 根因分析

常见原因：
1. 业务流量突增
2. 代码死循环
3. 内存泄漏导致CPU高
4. 定时任务并发

## 后续行动
- [ ] 分析access日志定位流量来源
- [ ] 检查是否有异常请求
- [ ] 考虑增加监控告警
