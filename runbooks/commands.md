# 常用诊断命令

## CPU 问题
```bash
top -bn1
ps aux --sort=-%cpu | head -10
```

## 内存问题
```bash
free -h
dmesg | grep -i oom | tail -10
```

## 磁盘问题
```bash
df -h
du -sh /var/*
```

## 网络问题
```bash
netstat -tulnp
ss -s
ping -c 4 <host>
```

## 进程问题
```bash
# 查找进程
ps aux | grep <name>
lsof -i :<port>

# 终止进程（谨慎）
kill -15 <pid>  # 优雅终止
kill -9 <pid>   # 强制终止
```

## Docker
```bash
docker ps
docker logs <container> --tail=100
docker stats
```

## Kubernetes
```bash
kubectl get pods -n <ns>
kubectl logs <pod> -n <ns>
kubectl describe pod <pod> -n <ns>
```

## 日志检索
```bash
tail -f /var/log/syslog
grep -i error /var/log/app.log | tail -50
journalctl -xe --since "1 hour ago"
```
