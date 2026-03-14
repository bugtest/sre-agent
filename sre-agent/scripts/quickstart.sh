#!/bin/bash
# SRE Agent 快速启动脚本（模拟模式）

set -e

echo "🚀 SRE Agent 快速启动（模拟模式）..."

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 安装依赖
echo -e "${YELLOW}安装依赖...${NC}"
pip install -q fastapi uvicorn sqlalchemy pydantic pytest

# 启动服务（后台）
echo -e "${YELLOW}启动 SRE Agent...${NC}"
cd "$(dirname "$0")/.."

# 设置模拟模式环境变量
export MOCK_MODE=true

# 启动
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload &

# 等待启动
sleep 5

# 健康检查
echo -e "${YELLOW}健康检查...${NC}"
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ SRE Agent 启动成功${NC}"
    echo ""
    echo "访问地址：http://localhost:8000"
    echo "API 文档：http://localhost:8000/docs"
    echo ""
    echo "测试告警:"
    echo 'curl -X POST http://localhost:8000/api/v1/alerts \'
    echo '  -H "Content-Type: application/json" \'
    echo '  -d '\''{
    "alert_name": "HighCPUUsage",
    "service_name": "payment-service",
    "severity": "critical",
    "metric_value": 95.5
  }'\'''
else
    echo -e "${RED}✗ 启动失败${NC}"
    exit 1
fi
