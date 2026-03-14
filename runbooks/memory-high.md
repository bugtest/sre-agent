# Runbook: 内存告警

## 告警条件
内存使用率 > 85%

## 排查步骤

### 1. 查看内存使用
```bash
free -h
```

### 2. 查看OOM Kill
```bash
dmesg | grep -i oom | tail -10
```

### 3. 查找内存占用最高的进程
```bash
ps aux --sort=-%mem | head -10
```

### 4. 查看进程详情
```bash
# Java堆内存
jmap -heap <pid>

# 进程内存映射
pmap -x <pid>
```

## 止血方案

### 方案1：释放缓存
```bash
sync && echo 3 > /proc/sys/vm/drop_caches
```

### 方案2：重启进程
```bash
systemctl restart <service>
```

### 方案3：OOM Kill应急
```bash
# 找到占用最高的进程
ps aux --sort=-%mem | head -5
# 手动kill释放内存
kill -9 <pid>
```

## 根因分析

常见原因：
1. 内存泄漏
2. JVM堆内存配置不足
3. 并发请求过多
4. 大数据加载

## 后续行动
- [ ] 分析Heap Dump定位泄漏
- [ ] 调整JVM参数
- [ ] 增加监控
