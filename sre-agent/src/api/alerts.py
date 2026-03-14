"""
告警接收器 API
负责接收和处理告警事件
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])

# 导入服务层
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from core.database import get_session
from services.alert_service import AlertService
from core.analysis_engine import get_rule_engine


# ==================== 请求/响应模型 ====================

class AlertCreateRequest(BaseModel):
    """告警创建请求"""
    alert_name: str = Field(..., description="告警名称", json_schema_extra={"example": "HighCPUUsage"})
    service_name: str = Field(..., description="服务名称", json_schema_extra={"example": "payment-service"})
    severity: str = Field(..., description="严重等级", json_schema_extra={"example": "critical"})
    metric_name: Optional[str] = Field(None, description="指标名称", json_schema_extra={"example": "cpu_usage"})
    metric_value: Optional[float] = Field(None, description="指标值", json_schema_extra={"example": 95.5})
    threshold: Optional[float] = Field(None, description="阈值", json_schema_extra={"example": 80.0})
    labels: Optional[Dict[str, str]] = Field(default_factory=dict, description="额外标签")
    
    @field_validator('severity')
    @classmethod
    def validate_severity(cls, v):
        allowed = ['critical', 'warning', 'info']
        if v not in allowed:
            raise ValueError(f"severity must be one of {allowed}")
        return v
    
    @field_validator('labels')
    @classmethod
    def validate_labels(cls, v):
        # 确保标签值都是字符串
        return {str(k): str(v) for k, v in v.items()} if v else {}


class AlertResponse(BaseModel):
    """告警响应"""
    id: int
    alert_name: str
    service_name: str
    severity: str
    status: str
    triggered_at: datetime
    resolved_at: Optional[datetime]
    metric_name: Optional[str]
    metric_value: Optional[float]
    threshold: Optional[float]
    labels: Dict[str, str]
    created_at: datetime


class AlertCreateResponse(BaseModel):
    """告警创建响应"""
    alert_id: int
    status: str
    analysis_url: str
    message: str = "告警已接收，正在分析..."


class AlertAnalysisResponse(BaseModel):
    """告警分析响应"""
    alert_id: int
    root_cause: Optional[str]
    confidence: float
    possible_causes: List[Dict[str, Any]]
    related_logs: List[Dict[str, Any]]
    related_metrics: Dict[str, Any]
    investigation_id: Optional[int]


class AlertSolutionResponse(BaseModel):
    """告警解决方案响应"""
    alert_id: int
    solutions: List[Dict[str, Any]]


# ==================== API 端点 ====================

@router.post("", response_model=AlertCreateResponse, status_code=200)
async def create_alert(
    request: AlertCreateRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    """
    接收告警
    
    接收来自监控系统的告警事件，创建告警记录并触发分析流程
    """
    logger.info(f"收到告警：{request.alert_name} - {request.service_name} (severity={request.severity})")
    
    try:
        # 创建服务实例
        alert_service = AlertService(session)
        
        # 1. 检查重复告警（告警风暴抑制）
        duplicate = alert_service.check_duplicate_alert(
            alert_name=request.alert_name,
            service_name=request.service_name,
            window_seconds=300  # 5 分钟窗口
        )
        
        if duplicate:
            logger.info(f"重复告警抑制：{request.alert_name} - {request.service_name}")
            return AlertCreateResponse(
                alert_id=duplicate.id,
                status=duplicate.status,
                analysis_url=f"/api/v1/alerts/{duplicate.id}/analysis",
                message=f"重复告警，已关联到告警 #{duplicate.id}"
            )
        
        # 2. 创建告警记录
        alert = alert_service.create_alert({
            'alert_name': request.alert_name,
            'service_name': request.service_name,
            'severity': request.severity,
            'metric_name': request.metric_name,
            'metric_value': request.metric_value,
            'threshold': request.threshold,
            'labels': request.labels
        })
        
        # 3. 创建问题分析记录
        investigation = alert_service.create_investigation(
            alert_id=alert.id,
            root_cause="分析中..."
        )
        
        # 4. 后台执行分析
        background_tasks.add_task(
            run_analysis,
            alert.id,
            investigation.id,
            request.dict()
        )
        
        logger.info(f"告警创建成功：id={alert.id}, investigation_id={investigation.id}")
        
        return AlertCreateResponse(
            alert_id=alert.id,
            status="investigating",
            analysis_url=f"/api/v1/alerts/{alert.id}/analysis",
            message="告警已接收，正在分析..."
        )
        
    except Exception as e:
        logger.error(f"创建告警失败：{e}")
        raise HTTPException(status_code=500, detail=f"创建告警失败：{str(e)}")


async def run_analysis(alert_id: int, investigation_id: int, alert_data: Dict[str, Any]):
    """
    后台执行分析任务
    
    Args:
        alert_id: 告警 ID
        investigation_id: 分析记录 ID
        alert_data: 告警数据
    """
    from sqlalchemy.orm import Session
    from core.database import get_db_manager
    
    logger.info(f"开始后台分析：alert_id={alert_id}, investigation_id={investigation_id}")
    
    try:
        # 获取数据库会话
        db_manager = get_db_manager()
        with next(db_manager.get_session()) as session:
            # 获取规则引擎
            rule_engine = get_rule_engine()
            
            # 准备分析上下文
            analysis_context = {
                'alert_id': alert_id,
                'alert_name': alert_data.get('alert_name'),
                'service_name': alert_data.get('service_name'),
                'metric_name': alert_data.get('metric_name'),
                'metric_value': alert_data.get('metric_value'),
                'threshold': alert_data.get('threshold'),
                'severity': alert_data.get('severity'),
                'labels': alert_data.get('labels', {})
            }
            
            # 执行规则引擎分析
            analysis_result = rule_engine.analyze(analysis_context)
            
            # 获取告警服务
            alert_service = AlertService(session)
            
            # 更新分析记录
            investigation = alert_service.get_investigation(investigation_id)
            if investigation:
                investigation.root_cause = analysis_result.root_cause
                investigation.analysis_result = {
                    'confidence': analysis_result.confidence,
                    'possible_causes': analysis_result.possible_causes,
                    'recommended_actions': analysis_result.recommended_actions
                }
                investigation.related_metrics = {
                    'metric_name': analysis_context['metric_name'],
                    'metric_value': analysis_context['metric_value'],
                    'threshold': analysis_context['threshold']
                }
                session.commit()
                
                logger.info(f"分析完成：alert_id={alert_id}, root_cause={analysis_result.root_cause}")
            
    except Exception as e:
        logger.error(f"后台分析失败：alert_id={alert_id}, error={e}")


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(alert_id: int):
    """
    获取告警详情
    """
    logger.info(f"获取告警详情：{alert_id}")
    
    # TODO: 实现获取告警逻辑
    # 1. 查询 Alert 记录
    # 2. 返回告警详情
    
    raise HTTPException(status_code=404, detail="告警不存在")


@router.get("/{alert_id}/analysis", response_model=AlertAnalysisResponse)
async def get_alert_analysis(alert_id: int, session: Session = Depends(get_session)):
    """
    获取告警分析报告
    
    返回分析引擎生成的分析报告，包括：
    - 根因分析
    - 可能原因排序
    - 相关日志和指标
    """
    logger.info(f"获取告警分析：{alert_id}")
    
    try:
        alert_service = AlertService(session)
        
        # 查询 Investigation 记录
        # 先获取告警，再获取关联的分析
        alert = alert_service.get_alert(alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail="告警不存在")
        
        # 查询分析记录（取最新的一条）
        from models.database import Investigation
        investigation = session.query(Investigation).filter(
            Investigation.alert_id == alert_id
        ).order_by(Investigation.created_at.desc()).first()
        
        if not investigation:
            return AlertAnalysisResponse(
                alert_id=alert_id,
                root_cause="分析中...",
                confidence=0.0,
                possible_causes=[],
                related_logs=[],
                related_metrics={},
                investigation_id=None
            )
        
        analysis_result = investigation.analysis_result or {}
        
        return AlertAnalysisResponse(
            alert_id=alert_id,
            root_cause=investigation.root_cause,
            confidence=analysis_result.get('confidence', 0.0),
            possible_causes=analysis_result.get('possible_causes', []),
            related_logs=investigation.related_logs or [],
            related_metrics=investigation.related_metrics or {},
            investigation_id=investigation.id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取分析结果失败：{e}")
        raise HTTPException(status_code=500, detail=f"获取分析结果失败：{str(e)}")


@router.get("/{alert_id}/solutions", response_model=AlertSolutionResponse)
async def get_alert_solutions(alert_id: int):
    """
    获取推荐解决方案
    
    基于历史案例和知识库推荐解决方案
    """
    logger.info(f"获取告警解决方案：{alert_id}")
    
    # TODO: 实现获取解决方案逻辑
    # 1. 查询告警类型
    # 2. 匹配 Runbook
    # 3. 返回推荐方案
    
    # 临时实现（占位）
    return AlertSolutionResponse(
        alert_id=alert_id,
        solutions=[]
    )


@router.get("", response_model=List[AlertResponse])
async def list_alerts(
    status: Optional[str] = None,
    service_name: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """
    获取告警列表
    
    支持按状态、服务名称、严重等级过滤
    """
    logger.info(f"获取告警列表：status={status}, service={service_name}, severity={severity}")
    
    # TODO: 实现告警列表查询
    # 1. 构建查询条件
    # 2. 分页查询
    # 3. 返回告警列表
    
    return []
