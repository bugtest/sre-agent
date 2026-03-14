#!/bin/bash
# SRE Agent 部署脚本

set -e

echo "🚀 SRE Agent 部署开始..."

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查依赖
check_dependencies() {
    echo -e "${YELLOW}检查依赖...${NC}"
    
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}错误：Docker 未安装${NC}"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        echo -e "${RED}错误：Docker Compose 未安装${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Docker 和 Docker Compose 已安装${NC}"
}

# 创建必要的目录
setup_directories() {
    echo -e "${YELLOW}创建目录结构...${NC}"
    mkdir -p deploy
    mkdir -p logs
    echo -e "${GREEN}✓ 目录创建完成${NC}"
}

# 初始化数据库
init_database() {
    echo -e "${YELLOW}初始化数据库...${NC}"
    
    # 等待 PostgreSQL 启动
    echo "等待 PostgreSQL 启动..."
    sleep 10
    
    # 运行迁移脚本
    if [ -f "migrations/001_initial_schema.sql" ]; then
        docker exec sre-postgres psql -U postgres -d sre_db -f /docker-entrypoint-initdb.d/001_initial_schema.sql
        echo -e "${GREEN}✓ 数据库初始化完成${NC}"
    else
        echo -e "${RED}警告：迁移文件不存在${NC}"
    fi
}

# 启动服务
start_services() {
    echo -e "${YELLOW}启动服务...${NC}"
    docker-compose up -d
    echo -e "${GREEN}✓ 服务启动完成${NC}"
}

# 健康检查
health_check() {
    echo -e "${YELLOW}健康检查...${NC}"
    
    # 等待服务启动
    sleep 15
    
    # 检查各个服务
    services=("sre-postgres" "sre-prometheus" "sre-loki" "sre-agent")
    
    for service in "${services[@]}"; do
        if docker ps --format '{{.Names}}' | grep -q "^${service}$"; then
            echo -e "${GREEN}✓ $service 运行中${NC}"
        else
            echo -e "${RED}✗ $service 未运行${NC}"
        fi
    done
    
    # 检查 API 健康
    echo "检查 SRE Agent API..."
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ SRE Agent API 正常${NC}"
    else
        echo -e "${YELLOW}⚠ SRE Agent API 未响应（可能正在启动）${NC}"
    fi
}

# 显示访问信息
show_info() {
    echo ""
    echo -e "${GREEN}=====================================${NC}"
    echo -e "${GREEN}🎉 SRE Agent 部署完成！${NC}"
    echo -e "${GREEN}=====================================${NC}"
    echo ""
    echo "服务访问地址:"
    echo -e "  ${YELLOW}SRE Agent API:${NC}  http://localhost:8000"
    echo -e "  ${YELLOW}Grafana:${NC}       http://localhost:3000 (admin/admin)"
    echo -e "  ${YELLOW}Prometheus:${NC}     http://localhost:9090"
    echo -e "  ${YELLOW}Loki:${NC}           http://localhost:3100"
    echo -e "  ${YELLOW}PostgreSQL:${NC}     localhost:5432"
    echo ""
    echo "常用命令:"
    echo -e "  ${YELLOW}查看日志:${NC}     docker-compose logs -f sre-agent"
    echo -e "  ${YELLOW}停止服务:${NC}     docker-compose down"
    echo -e "  ${YELLOW}重启服务:${NC}     docker-compose restart"
    echo -e "  ${YELLOW}查看状态:${NC}     docker-compose ps"
    echo ""
}

# 主流程
main() {
    check_dependencies
    setup_directories
    start_services
    init_database
    health_check
    show_info
}

# 运行主流程
main
