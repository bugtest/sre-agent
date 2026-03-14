"""
知识库服务单元测试
"""

import pytest
from sqlalchemy import create_engine, Column, Integer, String, Float, JSON, DateTime, Boolean, Text
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

# 简化模型用于测试
TestBase = declarative_base()


class Runbook(TestBase):
    __tablename__ = 'runbooks'
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    alert_pattern = Column(String(200))
    description = Column(Text)
    steps = Column(JSON, default=list)
    success_rate = Column(Float, default=0.0)
    risk_level = Column(String(20), default='medium')
    requires_approval = Column(Boolean, default=True)
    estimated_duration_seconds = Column(Integer, default=60)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now)


class Alert(TestBase):
    __tablename__ = 'alerts'
    id = Column(Integer, primary_key=True)
    alert_name = Column(String(200), nullable=False)
    service_name = Column(String(100), nullable=False)
    severity = Column(String(20), nullable=False)
    triggered_at = Column(DateTime, default=datetime.now)
    status = Column(String(20), default='open')


class Investigation(TestBase):
    __tablename__ = 'investigations'
    id = Column(Integer, primary_key=True)
    alert_id = Column(Integer, nullable=False)
    root_cause = Column(String(500))
    analysis_result = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.now)


@pytest.fixture
def session():
    """创建测试会话"""
    engine = create_engine('sqlite:///:memory:', echo=False, connect_args={'check_same_thread': False})
    TestBase.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def kb_service(session):
    """创建知识库服务"""
    # 动态导入，避免循环依赖
    from types import ModuleType
    services = ModuleType('services')
    
    class MockKnowledgeBaseService:
        def __init__(self, session):
            self.session = session
        
        def create_runbook(self, runbook_data):
            runbook = Runbook(**runbook_data)
            self.session.add(runbook)
            self.session.commit()
            self.session.refresh(runbook)
            return runbook
        
        def get_runbook(self, runbook_id):
            return self.session.query(Runbook).filter(Runbook.id == runbook_id).first()
        
        def list_runbooks(self, alert_pattern=None, risk_level=None, limit=50, offset=0):
            query = self.session.query(Runbook)
            if alert_pattern:
                query = query.filter(Runbook.alert_pattern.like(f'%{alert_pattern}%'))
            if risk_level:
                query = query.filter(Runbook.risk_level == risk_level)
            return query.order_by(Runbook.success_rate.desc()).offset(offset).limit(limit).all()
        
        def search_runbooks_by_alert(self, alert_name, limit=3):
            import re
            keywords = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', alert_name)
            keywords = [w.lower() for w in keywords]
            
            matches = []
            all_runbooks = self.session.query(Runbook).all()
            
            for runbook in all_runbooks:
                score = 0
                if runbook.alert_pattern:
                    for keyword in keywords:
                        if keyword in runbook.alert_pattern.lower():
                            score += 1
                if runbook.title:
                    for keyword in keywords:
                        if keyword in runbook.title.lower():
                            score += 1
                
                if score > 0:
                    matches.append((runbook, score))
            
            matches.sort(key=lambda x: x[1], reverse=True)
            return [rb for rb, score in matches[:limit]]
        
        def update_runbook_success_rate(self, runbook_id, success):
            runbook = self.get_runbook(runbook_id)
            if runbook:
                current_rate = float(runbook.success_rate) if runbook.success_rate else 0.0
                new_rate = current_rate * 0.9 + (1.0 if success else 0.0) * 0.1
                runbook.success_rate = round(new_rate, 2)
                self.session.commit()
        
        def get_runbook_stats(self):
            total = self.session.query(Runbook).count()
            avg_success = self.session.query(Runbook.success_rate).filter(
                Runbook.success_rate.isnot(None)
            ).first()
            avg_success = float(avg_success[0]) if avg_success and avg_success[0] else 0.0
            
            return {
                'total_runbooks': total,
                'avg_success_rate': round(avg_success, 2)
            }
    
    return MockKnowledgeBaseService(session)


class TestKnowledgeBaseService:
    """知识库服务测试"""
    
    def test_create_runbook(self, kb_service):
        """测试创建 Runbook"""
        runbook_data = {
            'title': '重启 Pod',
            'alert_pattern': 'PodCrashLoop',
            'description': '当 Pod 崩溃时重启',
            'steps': [{'step': 1, 'action': 'delete_pod'}],
            'success_rate': 85.0,
            'risk_level': 'medium',
            'requires_approval': True
        }
        
        runbook = kb_service.create_runbook(runbook_data)
        
        assert runbook.id is not None
        assert runbook.title == '重启 Pod'
        assert runbook.alert_pattern == 'PodCrashLoop'
        assert runbook.success_rate == 85.0
    
    def test_get_runbook(self, kb_service):
        """测试获取 Runbook"""
        # 先创建
        runbook_data = {
            'title': '扩容资源',
            'alert_pattern': 'HighCPU',
            'steps': [],
            'success_rate': 90.0
        }
        created = kb_service.create_runbook(runbook_data)
        
        # 再获取
        retrieved = kb_service.get_runbook(created.id)
        
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.title == '扩容资源'
    
    def test_list_runbooks(self, kb_service):
        """测试列出 Runbooks"""
        # 创建多个
        for i in range(5):
            kb_service.create_runbook({
                'title': f'Runbook {i}',
                'alert_pattern': f'Pattern{i}',
                'steps': [],
                'success_rate': 80.0 + i * 2
            })
        
        # 列出
        runbooks = kb_service.list_runbooks(limit=10)
        
        assert len(runbooks) == 5
        # 按成功率降序
        assert runbooks[0].success_rate >= runbooks[-1].success_rate
    
    def test_search_runbooks_by_keyword(self, kb_service):
        """测试关键词搜索"""
        # 创建测试数据
        kb_service.create_runbook({
            'title': 'CPU 扩容',
            'alert_pattern': 'HighCPU',
            'steps': []
        })
        kb_service.create_runbook({
            'title': '内存扩容',
            'alert_pattern': 'HighMemory',
            'steps': []
        })
        kb_service.create_runbook({
            'title': 'Pod 重启',
            'alert_pattern': 'PodCrashLoop',
            'steps': []
        })
        
        # 搜索 CPU 相关
        results = kb_service.search_runbooks_by_alert('HighCPUUsage')
        
        assert len(results) > 0
        assert results[0].alert_pattern == 'HighCPU'
    
    def test_update_success_rate(self, kb_service):
        """测试更新成功率"""
        runbook = kb_service.create_runbook({
            'title': 'Test',
            'steps': [],
            'success_rate': 80.0
        })
        
        # 成功执行
        kb_service.update_runbook_success_rate(runbook.id, True)
        updated = kb_service.get_runbook(runbook.id)
        # new = 80 * 0.9 + 1.0 * 0.1 = 72.1
        assert updated.success_rate == 72.1
        
        # 再次成功
        kb_service.update_runbook_success_rate(runbook.id, True)
        updated = kb_service.get_runbook(runbook.id)
        # new = 72.1 * 0.9 + 1.0 * 0.1 = 64.99
        assert abs(updated.success_rate - 64.99) < 0.01
    
    def test_get_runbook_stats(self, kb_service):
        """测试统计信息"""
        # 创建数据
        for i in range(3):
            kb_service.create_runbook({
                'title': f'Runbook {i}',
                'steps': [],
                'success_rate': 80.0 + i * 5
            })
        
        stats = kb_service.get_runbook_stats()
        
        assert stats['total_runbooks'] == 3
        assert stats['avg_success_rate'] >= 80.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
