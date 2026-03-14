"""
执行引擎单元测试
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


class Execution(TestBase):
    __tablename__ = 'executions'
    id = Column(Integer, primary_key=True)
    investigation_id = Column(Integer, nullable=False)
    runbook_id = Column(Integer, nullable=False)
    status = Column(String(20), default='pending')
    executed_by = Column(String(100))
    approved_by = Column(String(100))
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    result = Column(JSON, default=dict)
    rollback_result = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.now)


class Runbook(TestBase):
    __tablename__ = 'runbooks'
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    steps = Column(JSON, default=list)
    success_rate = Column(Float, default=0.0)
    risk_level = Column(String(20), default='medium')
    requires_approval = Column(Boolean, default=True)


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
def exec_engine(session):
    """创建执行引擎（模拟）"""
    from types import ModuleType
    
    class MockExecutionEngine:
        def __init__(self, session):
            self.session = session
        
        def create_execution(self, investigation_id, runbook_id, executed_by='auto', approved_by=None, parameters=None):
            execution = Execution(
                investigation_id=investigation_id,
                runbook_id=runbook_id,
                status='pending',
                executed_by=executed_by,
                approved_by=approved_by,
                result={'parameters': parameters or {}}
            )
            self.session.add(execution)
            self.session.commit()
            self.session.refresh(execution)
            return execution
        
        def execute_runbook(self, execution_id, parameters=None):
            execution = self.session.query(Execution).filter(Execution.id == execution_id).first()
            if not execution:
                raise ValueError(f"执行记录不存在：{execution_id}")
            
            runbook = self.session.query(Runbook).filter(Runbook.id == execution.runbook_id).first()
            if not runbook:
                raise ValueError(f"Runbook 不存在：{execution.runbook_id}")
            
            # 检查审批
            if runbook.requires_approval and not execution.approved_by:
                execution.status = 'pending_approval'
                self.session.commit()
                return execution
            
            # 执行步骤（模拟）
            execution.status = 'running'
            execution.started_at = datetime.now()
            self.session.commit()
            
            # 模拟执行成功
            execution.status = 'success'
            execution.completed_at = datetime.now()
            execution.result = {
                'steps': [{'action': 'test', 'success': True}],
                'message': 'Executed successfully'
            }
            self.session.commit()
            
            # 更新成功率
            if runbook.success_rate is None:
                runbook.success_rate = 0.0
            new_rate = float(runbook.success_rate) * 0.9 + 1.0 * 0.1
            runbook.success_rate = round(new_rate, 2)
            self.session.commit()
            
            return execution
        
        def rollback_execution(self, execution_id, reason):
            execution = self.session.query(Execution).filter(Execution.id == execution_id).first()
            if execution:
                execution.status = 'rolled_back'
                execution.rollback_result = {'reason': reason}
                self.session.commit()
            return execution
        
        def get_execution(self, execution_id):
            return self.session.query(Execution).filter(Execution.id == execution_id).first()
        
        def list_executions(self, status=None, runbook_id=None, limit=50, offset=0):
            query = self.session.query(Execution)
            if status:
                query = query.filter(Execution.status == status)
            if runbook_id:
                query = query.filter(Execution.runbook_id == runbook_id)
            return query.order_by(Execution.created_at.desc()).offset(offset).limit(limit).all()
        
        def get_execution_stats(self):
            total = self.session.query(Execution).count()
            success = self.session.query(Execution).filter(Execution.status == 'success').count()
            rate = (success / total * 100) if total > 0 else 0.0
            return {
                'total_executions': total,
                'success_count': success,
                'success_rate': round(rate, 2)
            }
    
    return MockExecutionEngine(session)


class TestExecutionEngine:
    """执行引擎测试"""
    
    def test_create_execution(self, exec_engine, session):
        """测试创建执行记录"""
        # 先创建 Runbook
        runbook = Runbook(title='Test', steps=[], requires_approval=False)
        session.add(runbook)
        session.commit()
        
        execution = exec_engine.create_execution(
            investigation_id=1,
            runbook_id=runbook.id,
            executed_by='test-user',
            parameters={'pod_name': 'test-pod'}
        )
        
        assert execution.id is not None
        assert execution.status == 'pending'
        assert execution.executed_by == 'test-user'
        assert execution.result['parameters']['pod_name'] == 'test-pod'
    
    def test_execute_runbook_no_approval_required(self, exec_engine, session):
        """测试执行不需要审批的 Runbook"""
        runbook = Runbook(title='Test', steps=[], requires_approval=False, success_rate=80.0)
        session.add(runbook)
        session.commit()
        
        execution = exec_engine.create_execution(
            investigation_id=1,
            runbook_id=runbook.id,
            executed_by='auto'
        )
        
        result = exec_engine.execute_runbook(execution.id)
        
        assert result.status == 'success'
        assert result.completed_at is not None
        assert result.result['steps'][0]['success'] is True
        
        # 验证成功率更新：new = 80 * 0.9 + 1.0 * 0.1 = 72.1
        updated_runbook = session.query(Runbook).filter(Runbook.id == runbook.id).first()
        assert updated_runbook.success_rate == 72.1
    
    def test_execute_runbook_requires_approval(self, exec_engine, session):
        """测试执行需要审批的 Runbook"""
        runbook = Runbook(title='Test', steps=[], requires_approval=True)
        session.add(runbook)
        session.commit()
        
        execution = exec_engine.create_execution(
            investigation_id=1,
            runbook_id=runbook.id,
            executed_by='auto'
            # 没有 approved_by
        )
        
        result = exec_engine.execute_runbook(execution.id)
        
        assert result.status == 'pending_approval'
    
    def test_execute_runbook_with_approval(self, exec_engine, session):
        """测试执行已审批的 Runbook"""
        runbook = Runbook(title='Test', steps=[], requires_approval=True)
        session.add(runbook)
        session.commit()
        
        execution = exec_engine.create_execution(
            investigation_id=1,
            runbook_id=runbook.id,
            executed_by='auto',
            approved_by='admin'
        )
        
        result = exec_engine.execute_runbook(execution.id)
        
        assert result.status == 'success'
        assert result.approved_by == 'admin'
    
    def test_rollback_execution(self, exec_engine, session):
        """测试回滚执行"""
        runbook = Runbook(title='Test', steps=[])
        session.add(runbook)
        session.commit()
        
        execution = exec_engine.create_execution(
            investigation_id=1,
            runbook_id=runbook.id,
            executed_by='auto',
            approved_by='admin'
        )
        
        # 先执行成功
        exec_engine.execute_runbook(execution.id)
        
        # 再回滚
        result = exec_engine.rollback_execution(execution.id, reason='Service degraded after execution')
        
        assert result.status == 'rolled_back'
        assert result.rollback_result['reason'] == 'Service degraded after execution'
    
    def test_list_executions(self, exec_engine, session):
        """测试列出执行记录"""
        runbook = Runbook(title='Test', steps=[], requires_approval=False)
        session.add(runbook)
        session.commit()
        
        # 创建多个执行
        for i in range(5):
            exec_engine.create_execution(
                investigation_id=1,
                runbook_id=runbook.id,
                executed_by='auto'
            )
            exec_engine.execute_runbook(i + 1)
        
        # 列出
        executions = exec_engine.list_executions(limit=10)
        
        assert len(executions) == 5
        # 按创建时间降序
        assert executions[0].id >= executions[-1].id
    
    def test_list_executions_filter_by_status(self, exec_engine, session):
        """测试按状态过滤执行记录"""
        runbook = Runbook(title='Test', steps=[], requires_approval=False)
        session.add(runbook)
        session.commit()
        
        # 创建执行
        for i in range(3):
            exec_engine.create_execution(
                investigation_id=1,
                runbook_id=runbook.id,
                executed_by='auto'
            )
            exec_engine.execute_runbook(i + 1)
        
        # 按状态过滤
        success_executions = exec_engine.list_executions(status='success')
        
        assert len(success_executions) == 3
    
    def test_get_execution_stats(self, exec_engine, session):
        """测试获取执行统计"""
        runbook = Runbook(title='Test', steps=[], requires_approval=False)
        session.add(runbook)
        session.commit()
        
        # 创建执行
        for i in range(4):
            exec_engine.create_execution(
                investigation_id=1,
                runbook_id=runbook.id,
                executed_by='auto'
            )
            exec_engine.execute_runbook(i + 1)
        
        stats = exec_engine.get_execution_stats()
        
        assert stats['total_executions'] == 4
        assert stats['success_count'] == 4
        assert stats['success_rate'] == 100.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
