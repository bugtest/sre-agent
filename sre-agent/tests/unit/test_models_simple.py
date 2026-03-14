"""
数据模型单元测试 - SQLite 兼容版本
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, JSON, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base

TestBase = declarative_base()


class Alert(TestBase):
    """简化版 Alert 模型用于测试"""
    __tablename__ = 'alerts'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_name = Column(String(200), nullable=False)
    service_name = Column(String(100), nullable=False)
    severity = Column(String(20), nullable=False)
    triggered_at = Column(DateTime, default=datetime.now)
    resolved_at = Column(DateTime)
    status = Column(String(20), default='open')
    metric_name = Column(String(100))
    metric_value = Column(Float)
    threshold = Column(Float)
    labels = Column(JSON, default=dict)
    
    def to_dict(self):
        return {
            'id': self.id,
            'alert_name': self.alert_name,
            'service_name': self.service_name,
            'severity': self.severity,
            'status': self.status,
            'metric_value': self.metric_value,
            'labels': self.labels or {}
        }
    
    def __repr__(self):
        return f"<Alert(id={self.id}, name='{self.alert_name}')>"


@pytest.fixture
def session():
    """创建测试会话"""
    engine = create_engine('sqlite:///:memory:', echo=False)
    TestBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_alert():
    """测试告警数据"""
    return Alert(
        alert_name="HighCPUUsage",
        service_name="payment-service",
        severity="critical",
        triggered_at=datetime.now(),
        metric_name="cpu_usage",
        metric_value=95.5,
        threshold=80.0,
        labels={"instance": "prod-01"},
        status="open"
    )


class TestAlertModel:
    """Alert 模型测试"""
    
    def test_create_alert(self, session, sample_alert):
        """测试创建告警"""
        session.add(sample_alert)
        session.commit()
        session.refresh(sample_alert)
        
        assert sample_alert.id is not None
        assert sample_alert.id > 0
        assert sample_alert.alert_name == "HighCPUUsage"
        assert sample_alert.service_name == "payment-service"
        assert sample_alert.severity == "critical"
        assert sample_alert.status == "open"
        assert sample_alert.metric_value == 95.5
    
    def test_alert_to_dict(self, session, sample_alert):
        """测试转字典"""
        session.add(sample_alert)
        session.commit()
        
        alert_dict = sample_alert.to_dict()
        
        assert alert_dict['alert_name'] == "HighCPUUsage"
        assert alert_dict['service_name'] == "payment-service"
        assert alert_dict['severity'] == "critical"
        assert alert_dict['metric_value'] == 95.5
        assert alert_dict['labels']['instance'] == "prod-01"
    
    def test_alert_repr(self, sample_alert):
        """测试字符串表示"""
        repr_str = repr(sample_alert)
        assert "Alert" in repr_str
        assert "HighCPUUsage" in repr_str
    
    def test_alert_status_transitions(self, session, sample_alert):
        """测试状态流转"""
        session.add(sample_alert)
        session.commit()
        
        # open -> investigating
        sample_alert.status = "investigating"
        session.commit()
        assert sample_alert.status == "investigating"
        
        # investigating -> resolved
        sample_alert.status = "resolved"
        sample_alert.resolved_at = datetime.now()
        session.commit()
        assert sample_alert.status == "resolved"
        assert sample_alert.resolved_at is not None
    
    def test_alert_labels_json(self, session, sample_alert):
        """测试 JSON 标签"""
        session.add(sample_alert)
        session.commit()
        
        assert sample_alert.labels['instance'] == "prod-01"
        
        # 更新标签
        sample_alert.labels = {"env": "prod", "team": "payment"}
        session.commit()
        assert sample_alert.labels['env'] == "prod"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
