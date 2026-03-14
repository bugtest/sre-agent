"""
SRE Agent 数据模型层
数据库：PostgreSQL
ORM: SQLAlchemy
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import Column, BigInteger, String, Text, DateTime, DECIMAL, Boolean, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import json

Base = declarative_base()


class Alert(Base):
    """告警记录表"""
    __tablename__ = 'alerts'
    
    id = Column(BigInteger, primary_key=True)
    alert_name = Column(String(200), nullable=False, index=True)
    service_name = Column(String(100), nullable=False, index=True)
    severity = Column(String(20), nullable=False)  # critical/warning/info
    triggered_at = Column(DateTime, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    status = Column(String(20), default='open', index=True)  # open/investigating/resolved
    metric_name = Column(String(100), nullable=True)
    metric_value = Column(DECIMAL(10, 2), nullable=True)
    threshold = Column(DECIMAL(10, 2), nullable=True)
    labels = Column(JSON, nullable=True)  # 额外标签
    created_at = Column(DateTime, server_default=func.now())
    
    # 关系
    investigations = relationship("Investigation", back_populates="alert", cascade="all, delete-orphan")
    incidents = relationship("Incident", back_populates="alert", cascade="all, delete-orphan")
    
    # 索引
    __table_args__ = (
        Index('idx_alerts_service_status', 'service_name', 'status'),
        Index('idx_alerts_triggered_at', 'triggered_at'),
        Index('idx_alerts_labels', 'labels', postgresql_using='gin'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'alert_name': self.alert_name,
            'service_name': self.service_name,
            'severity': self.severity,
            'triggered_at': self.triggered_at.isoformat() if self.triggered_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'status': self.status,
            'metric_name': self.metric_name,
            'metric_value': float(self.metric_value) if self.metric_value else None,
            'threshold': float(self.threshold) if self.threshold else None,
            'labels': self.labels or {},
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f"<Alert(id={self.id}, name='{self.alert_name}', service='{self.service_name}', status='{self.status}')>"


class Investigation(Base):
    """问题分析记录表"""
    __tablename__ = 'investigations'
    
    id = Column(BigInteger, primary_key=True)
    alert_id = Column(BigInteger, ForeignKey('alerts.id'), nullable=False, index=True)
    root_cause = Column(Text, nullable=True)
    analysis_result = Column(JSON, nullable=True)  # 分析结果
    related_logs = Column(JSON, nullable=True)  # 相关日志片段
    related_metrics = Column(JSON, nullable=True)  # 相关指标
    created_at = Column(DateTime, server_default=func.now())
    
    # 关系
    alert = relationship("Alert", back_populates="investigations")
    executions = relationship("Execution", back_populates="investigation", cascade="all, delete-orphan")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'alert_id': self.alert_id,
            'root_cause': self.root_cause,
            'analysis_result': self.analysis_result or {},
            'related_logs': self.related_logs or [],
            'related_metrics': self.related_metrics or {},
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f"<Investigation(id={self.id}, alert_id={self.alert_id}, root_cause='{self.root_cause[:50] if self.root_cause else 'None'}...')>"


class Runbook(Base):
    """解决方案/操作手册表"""
    __tablename__ = 'runbooks'
    
    id = Column(BigInteger, primary_key=True)
    title = Column(String(200), nullable=False)
    alert_pattern = Column(String(200), nullable=True, index=True)  # 匹配的告警模式
    description = Column(Text, nullable=True)
    steps = Column(JSON, nullable=False)  # 执行步骤
    success_rate = Column(DECIMAL(5, 2), nullable=True, default=0.0)  # 成功率
    risk_level = Column(String(20), default='medium')  # low/medium/high
    requires_approval = Column(Boolean, default=True)
    estimated_duration_seconds = Column(BigInteger, default=60)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # 关系
    executions = relationship("Execution", back_populates="runbook")
    
    # 索引
    __table_args__ = (
        Index('idx_runbooks_pattern', 'alert_pattern'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'title': self.title,
            'alert_pattern': self.alert_pattern,
            'description': self.description,
            'steps': self.steps or [],
            'success_rate': float(self.success_rate) if self.success_rate else 0.0,
            'risk_level': self.risk_level,
            'requires_approval': self.requires_approval,
            'estimated_duration_seconds': self.estimated_duration_seconds,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f"<Runbook(id={self.id}, title='{self.title}', risk='{self.risk_level}')>"


class Execution(Base):
    """执行记录表"""
    __tablename__ = 'executions'
    
    id = Column(BigInteger, primary_key=True)
    investigation_id = Column(BigInteger, ForeignKey('investigations.id'), nullable=False, index=True)
    runbook_id = Column(BigInteger, ForeignKey('runbooks.id'), nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True)  # pending/running/success/failed/rolled_back
    executed_by = Column(String(100), nullable=True)  # user or 'auto'
    approved_by = Column(String(100), nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    result = Column(JSON, nullable=True)
    rollback_result = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    
    # 关系
    investigation = relationship("Investigation", back_populates="executions")
    runbook = relationship("Runbook", back_populates="executions")
    
    # 索引
    __table_args__ = (
        Index('idx_executions_status_created', 'status', 'created_at'),
    )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'investigation_id': self.investigation_id,
            'runbook_id': self.runbook_id,
            'status': self.status,
            'executed_by': self.executed_by,
            'approved_by': self.approved_by,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'result': self.result or {},
            'rollback_result': self.rollback_result or {},
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f"<Execution(id={self.id}, status='{self.status}', runbook_id={self.runbook_id})>"


class Incident(Base):
    """事故报告表"""
    __tablename__ = 'incidents'
    
    id = Column(BigInteger, primary_key=True)
    alert_id = Column(BigInteger, ForeignKey('alerts.id'), nullable=False, index=True, unique=True)
    title = Column(String(200), nullable=False)
    summary = Column(Text, nullable=True)
    timeline = Column(JSON, nullable=True)  # 时间线
    impact = Column(Text, nullable=True)  # 影响范围
    root_cause = Column(Text, nullable=True)
    lessons_learned = Column(JSON, nullable=True)  # 改进建议
    mttr_seconds = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    
    # 关系
    alert = relationship("Alert", back_populates="incidents")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'alert_id': self.alert_id,
            'title': self.title,
            'summary': self.summary,
            'timeline': self.timeline or [],
            'impact': self.impact,
            'root_cause': self.root_cause,
            'lessons_learned': self.lessons_learned or [],
            'mttr_seconds': self.mttr_seconds,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f"<Incident(id={self.id}, title='{self.title}', mttr={self.mttr_seconds}s)>"
