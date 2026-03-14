"""
告警服务层
处理告警的创建、查询、更新等业务逻辑
"""

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from datetime import datetime
from typing import List, Optional, Dict, Any
import logging

from models.database import Alert, Investigation, Runbook

logger = logging.getLogger(__name__)


class AlertService:
    """告警服务"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create_alert(self, alert_data: Dict[str, Any]) -> Alert:
        """
        创建告警
        
        Args:
            alert_data: 告警数据字典
            
        Returns:
            Alert: 创建的告警对象
        """
        alert = Alert(
            alert_name=alert_data['alert_name'],
            service_name=alert_data['service_name'],
            severity=alert_data['severity'],
            triggered_at=datetime.fromisoformat(alert_data.get('triggered_at')) if alert_data.get('triggered_at') else datetime.now(),
            metric_name=alert_data.get('metric_name'),
            metric_value=alert_data.get('metric_value'),
            threshold=alert_data.get('threshold'),
            labels=alert_data.get('labels', {}),
            status='open'
        )
        
        self.session.add(alert)
        self.session.commit()
        self.session.refresh(alert)
        
        logger.info(f"创建告警：id={alert.id}, name={alert.alert_name}, service={alert.service_name}")
        
        return alert
    
    def get_alert(self, alert_id: int) -> Optional[Alert]:
        """
        获取告警详情
        
        Args:
            alert_id: 告警 ID
            
        Returns:
            Alert 或 None
        """
        return self.session.query(Alert).filter(Alert.id == alert_id).first()
    
    def list_alerts(
        self,
        status: Optional[str] = None,
        service_name: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Alert]:
        """
        获取告警列表
        
        Args:
            status: 状态过滤
            service_name: 服务名称过滤
            severity: 严重等级过滤
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            Alert 列表
        """
        query = self.session.query(Alert)
        
        # 应用过滤条件
        if status:
            query = query.filter(Alert.status == status)
        if service_name:
            query = query.filter(Alert.service_name == service_name)
        if severity:
            query = query.filter(Alert.severity == severity)
        
        # 分页
        alerts = query.order_by(Alert.triggered_at.desc()).offset(offset).limit(limit).all()
        
        return alerts
    
    def update_alert_status(self, alert_id: int, status: str) -> Optional[Alert]:
        """
        更新告警状态
        
        Args:
            alert_id: 告警 ID
            status: 新状态
            
        Returns:
            更新后的 Alert 或 None
        """
        alert = self.get_alert(alert_id)
        if not alert:
            return None
        
        alert.status = status
        
        if status == 'resolved':
            alert.resolved_at = datetime.now()
        
        self.session.commit()
        self.session.refresh(alert)
        
        logger.info(f"更新告警状态：id={alert_id}, status={status}")
        
        return alert
    
    def check_duplicate_alert(
        self,
        alert_name: str,
        service_name: str,
        window_seconds: int = 300
    ) -> Optional[Alert]:
        """
        检查重复告警（告警风暴抑制）
        
        Args:
            alert_name: 告警名称
            service_name: 服务名称
            window_seconds: 时间窗口（秒）
            
        Returns:
            如果存在重复告警则返回，否则 None
        """
        from datetime import timedelta
        
        window_start = datetime.now() - timedelta(seconds=window_seconds)
        
        duplicate = self.session.query(Alert).filter(
            and_(
                Alert.alert_name == alert_name,
                Alert.service_name == service_name,
                Alert.status.in_(['open', 'investigating']),
                Alert.triggered_at >= window_start
            )
        ).first()
        
        if duplicate:
            logger.info(f"检测到重复告警：{alert_name} - {service_name} (最近一次：{duplicate.triggered_at})")
        
        return duplicate
    
    def create_investigation(
        self,
        alert_id: int,
        root_cause: Optional[str] = None,
        analysis_result: Optional[Dict] = None
    ) -> Investigation:
        """
        创建问题分析记录
        
        Args:
            alert_id: 告警 ID
            root_cause: 根因
            analysis_result: 分析结果
            
        Returns:
            Investigation: 创建的分析记录
        """
        investigation = Investigation(
            alert_id=alert_id,
            root_cause=root_cause,
            analysis_result=analysis_result or {},
            related_logs=[],
            related_metrics={}
        )
        
        self.session.add(investigation)
        self.session.commit()
        self.session.refresh(investigation)
        
        logger.info(f"创建问题分析：id={investigation.id}, alert_id={alert_id}")
        
        return investigation
    
    def get_investigation(self, investigation_id: int) -> Optional[Investigation]:
        """
        获取问题分析记录
        
        Args:
            investigation_id: 分析记录 ID
            
        Returns:
            Investigation 或 None
        """
        return self.session.query(Investigation).filter(
            Investigation.id == investigation_id
        ).first()
    
    def get_runbooks_by_pattern(self, alert_pattern: str, limit: int = 3) -> List[Runbook]:
        """
        根据告警模式获取推荐 Runbook
        
        Args:
            alert_pattern: 告警模式（支持正则）
            limit: 返回数量限制
            
        Returns:
            Runbook 列表
        """
        import re
        
        runbooks = self.session.query(Runbook).filter(
            or_(
                Runbook.alert_pattern == alert_pattern,
                Runbook.alert_pattern.like(f'%{alert_pattern}%')
            )
        ).order_by(
            Runbook.success_rate.desc(),
            Runbook.risk_level.asc()
        ).limit(limit).all()
        
        # 如果没有精确匹配，尝试模糊匹配
        if not runbooks:
            all_runbooks = self.session.query(Runbook).all()
            matched = []
            for rb in all_runbooks:
                if rb.alert_pattern and re.search(rb.alert_pattern, alert_pattern, re.IGNORECASE):
                    matched.append(rb)
            runbooks = sorted(matched, key=lambda x: x.success_rate or 0, reverse=True)[:limit]
        
        return runbooks
    
    def get_active_alerts_count(self, service_name: Optional[str] = None) -> int:
        """
        获取活跃告警数量
        
        Args:
            service_name: 可选的服务名称过滤
            
        Returns:
            活跃告警数量
        """
        query = self.session.query(Alert).filter(
            Alert.status.in_(['open', 'investigating'])
        )
        
        if service_name:
            query = query.filter(Alert.service_name == service_name)
        
        return query.count()
