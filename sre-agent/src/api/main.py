"""
SRE Agent 主应用入口
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from api.alerts import router as alerts_router
from core.database import get_db_manager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("SRE Agent 启动中...")
    
    # 初始化数据库
    try:
        db_manager = get_db_manager()
        logger.info("数据库连接成功")
    except Exception as e:
        logger.warning(f"数据库连接失败：{e}")
    
    yield
    
    # 关闭时
    logger.info("SRE Agent 关闭中...")


# 创建 FastAPI 应用
app = FastAPI(
    title="SRE Agent",
    description="智能运维问题定位与解决系统",
    version="0.1.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(alerts_router)


@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "SRE Agent",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "version": "0.1.0"
    }


@app.get("/metrics")
async def metrics():
    """Prometheus 指标（简化版）"""
    return {
        "sre_agent_up": 1,
        "sre_agent_version": 1
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
