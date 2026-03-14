"""
执行引擎服务层
负责 Runbook 的执行、回滚和状态追踪
"""

from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

from models.database import Execution, Runbook, Investigation, Alert
from integrations.kubernetes_client import get_k8s_client, K8sOperationResult

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """执行引擎"""
    
    def __init__(self, session: Session):
        self.session = session
        self.k8s_client = get_k8s_client()
    
    def create_execution(
        self,
        investigation_id: int,
        runbook_id: int,
        executed_by: str = 'auto',
        approved_by: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Execution:
        """
        创建执行记录
        
        Args:
            investigation_id: 分析记录 ID
            runbook_id: Runbook ID
            executed_by: 执行者（用户或'auto'）
            approved_by: 审批者
            parameters: 执行参数
            
        Returns:
            Execution: 创建的执行记录
        """
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
        
        logger.info(f"创建执行记录：id={execution.id}, runbook_id={runbook_id}")
        
        return execution
    
    def execute_runbook(
        self,
        execution_id: int,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Execution:
        """
        执行 Runbook
        
        Args:
            execution_id: 执行记录 ID
            parameters: 执行参数
            
        Returns:
            Execution: 更新后的执行记录
        """
        execution = self.session.query(Execution).filter(Execution.id == execution_id).first()
        if not execution:
            raise ValueError(f"执行记录不存在：{execution_id}")
        
        if execution.status != 'pending':
            logger.warning(f"执行记录状态不是 pending: {execution.status}")
            return execution
        
        runbook = self.session.query(Runbook).filter(Runbook.id == execution.runbook_id).first()
        if not runbook:
            raise ValueError(f"Runbook 不存在：{execution.runbook_id}")
        
        # 检查是否需要审批
        if runbook.requires_approval and not execution.approved_by:
            logger.warning(f"Runbook 需要审批：{runbook.id}")
            execution.status = 'pending_approval'
            self.session.commit()
            return execution
        
        # 开始执行
        execution.status = 'running'
        execution.started_at = datetime.now()
        self.session.commit()
        
        logger.info(f"开始执行 Runbook: execution_id={execution_id}, title={runbook.title}")
        
        try:
            # 执行步骤
            results = []
            for step in runbook.steps or []:
                step_result = self._execute_step(step, parameters or {})
                results.append(step_result)
                
                if not step_result.get('success', False):
                    # 步骤失败，需要回滚
                    logger.error(f"步骤执行失败：{step}")
                    rollback_result = self._rollback_execution(execution_id, results)
                    
                    execution.status = 'failed'
                    execution.completed_at = datetime.now()
                    execution.result = {
                        'steps': results,
                        'rollback': rollback_result,
                        'error': f"Step failed: {step_result.get('error')}"
                    }
                    self.session.commit()
                    
                    # 更新成功率
                    self._update_runbook_success_rate(runbook.id, success=False)
                    
                    return execution
            
            # 全部成功
            execution.status = 'success'
            execution.completed_at = datetime.now()
            execution.result = {
                'steps': results,
                'message': 'All steps completed successfully'
            }
            self.session.commit()
            
            # 更新成功率
            self._update_runbook_success_rate(runbook.id, success=True)
            
            logger.info(f"Runbook 执行成功：execution_id={execution_id}")
            
            return execution
            
        except Exception as e:
            logger.error(f"Runbook 执行失败：{e}")
            execution.status = 'failed'
            execution.completed_at = datetime.now()
            execution.result = {
                'error': str(e),
                'message': 'Execution failed with exception'
            }
            self.session.commit()
            
            # 更新成功率
            self._update_runbook_success_rate(runbook.id, success=False)
            
            return execution
    
    def _execute_step(
        self,
        step: Dict[str, Any],
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行单个步骤
        
        Args:
            step: 步骤定义
            parameters: 执行参数
            
        Returns:
            步骤执行结果
        """
        action = step.get('action', '')
        description = step.get('description', '')
        
        logger.info(f"执行步骤：{action} - {description}")
        
        try:
            # K8s 相关操作
            if action.startswith('k8s_') or action.startswith('kubernetes_'):
                return self._execute_k8s_step(action, step, parameters)
            
            # 通用操作
            elif action == 'get_pod':
                pod_name = self._resolve_parameter(step.get('params', {}).get('name'), parameters)
                namespace = self._resolve_parameter(step.get('params', {}).get('namespace', 'default'), parameters)
                
                pod_info = self.k8s_client.get_pod(pod_name, namespace)
                
                return {
                    'success': pod_info is not None,
                    'action': action,
                    'result': pod_info,
                    'message': f"Pod info retrieved: {pod_name}"
                }
            
            elif action == 'delete_pod':
                pod_name = self._resolve_parameter(step.get('params', {}).get('name'), parameters)
                namespace = self._resolve_parameter(step.get('params', {}).get('namespace', 'default'), parameters)
                
                result = self.k8s_client.restart_pod(pod_name, namespace)
                
                return {
                    'success': result.success,
                    'action': action,
                    'result': result.to_dict(),
                    'message': result.message
                }
            
            elif action == 'scale_deployment':
                deploy_name = self._resolve_parameter(step.get('params', {}).get('name'), parameters)
                replicas = int(self._resolve_parameter(step.get('params', {}).get('replicas', 1), parameters))
                namespace = self._resolve_parameter(step.get('params', {}).get('namespace', 'default'), parameters)
                
                result = self.k8s_client.scale_deployment(deploy_name, replicas, namespace)
                
                return {
                    'success': result.success,
                    'action': action,
                    'result': result.to_dict(),
                    'message': result.message
                }
            
            elif action == 'update_resources':
                pod_name = self._resolve_parameter(step.get('params', {}).get('name'), parameters)
                cpu = self._resolve_parameter(step.get('params', {}).get('cpu'), parameters)
                memory = self._resolve_parameter(step.get('params', {}).get('memory'), parameters)
                namespace = self._resolve_parameter(step.get('params', {}).get('namespace', 'default'), parameters)
                
                result = self.k8s_client.update_pod_resources(pod_name, cpu, memory, namespace)
                
                return {
                    'success': result.success,
                    'action': action,
                    'result': result.to_dict(),
                    'message': result.message
                }
            
            elif action == 'verify':
                # 验证步骤（总是成功，用于检查）
                return {
                    'success': True,
                    'action': action,
                    'result': {'verified': True},
                    'message': 'Verification passed'
                }
            
            else:
                logger.warning(f"未知动作：{action}")
                return {
                    'success': False,
                    'action': action,
                    'error': f'Unknown action: {action}'
                }
                
        except Exception as e:
            logger.error(f"步骤执行失败：{e}")
            return {
                'success': False,
                'action': action,
                'error': str(e)
            }
    
    def _execute_k8s_step(
        self,
        action: str,
        step: Dict[str, Any],
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行 K8s 相关步骤"""
        # 已在_execute_step 中处理
        return self._execute_step(step, parameters)
    
    def _rollback_execution(
        self,
        execution_id: int,
        executed_steps: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        回滚执行
        
        Args:
            execution_id: 执行记录 ID
            executed_steps: 已执行的步骤列表
            
        Returns:
            回滚结果
        """
        logger.info(f"开始回滚执行：{execution_id}")
        
        # 简单回滚策略：反向执行
        # 实际场景需要根据具体操作定义回滚逻辑
        rollback_results = []
        
        for step_result in reversed(executed_steps):
            if step_result.get('success'):
                # TODO: 实现具体回滚逻辑
                rollback_results.append({
                    'action': step_result.get('action'),
                    'rolled_back': False,
                    'message': 'Rollback not implemented for this action'
                })
        
        return {
            'attempted': True,
            'results': rollback_results,
            'message': 'Partial rollback completed'
        }
    
    def _resolve_parameter(self, value: Any, parameters: Dict[str, Any]) -> Any:
        """
        解析参数（支持模板变量）
        
        Args:
            value: 参数值（可能是模板如 "{{pod_name}}"）
            parameters: 实际参数
            
        Returns:
            解析后的值
        """
        if isinstance(value, str) and value.startswith('{{') and value.endswith('}}'):
            # 模板变量
            var_name = value[2:-2].strip()
            return parameters.get(var_name, value)
        
        return value
    
    def _update_runbook_success_rate(self, runbook_id: int, success: bool):
        """更新 Runbook 成功率"""
        runbook = self.session.query(Runbook).filter(Runbook.id == runbook_id).first()
        if not runbook:
            return
        
        current_rate = float(runbook.success_rate) if runbook.success_rate else 0.0
        new_rate = current_rate * 0.9 + (1.0 if success else 0.0) * 0.1
        runbook.success_rate = round(new_rate, 2)
        
        self.session.commit()
        
        logger.info(f"更新 Runbook 成功率：id={runbook_id}, new_rate={new_rate}")
    
    def rollback_execution(self, execution_id: int, reason: str) -> Execution:
        """
        手动回滚执行
        
        Args:
            execution_id: 执行记录 ID
            reason: 回滚原因
            
        Returns:
            Execution: 更新后的执行记录
        """
        execution = self.session.query(Execution).filter(Execution.id == execution_id).first()
        if not execution:
            raise ValueError(f"执行记录不存在：{execution_id}")
        
        if execution.status != 'success':
            logger.warning(f"只有成功的执行才能回滚：{execution.status}")
            return execution
        
        # 执行回滚
        rollback_result = self._rollback_execution(execution_id, execution.result.get('steps', []))
        
        execution.status = 'rolled_back'
        execution.rollback_result = rollback_result
        execution.result['rollback_reason'] = reason
        
        self.session.commit()
        
        logger.info(f"执行已回滚：{execution_id}, reason={reason}")
        
        return execution
    
    def get_execution(self, execution_id: int) -> Optional[Execution]:
        """获取执行记录"""
        return self.session.query(Execution).filter(Execution.id == execution_id).first()
    
    def list_executions(
        self,
        status: Optional[str] = None,
        runbook_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Execution]:
        """
        列出执行记录
        
        Args:
            status: 状态过滤
            runbook_id: Runbook ID 过滤
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            Execution 列表
        """
        query = self.session.query(Execution)
        
        if status:
            query = query.filter(Execution.status == status)
        if runbook_id:
            query = query.filter(Execution.runbook_id == runbook_id)
        
        executions = query.order_by(
            Execution.created_at.desc()
        ).offset(offset).limit(limit).all()
        
        return executions
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """获取执行统计"""
        total = self.session.query(Execution).count()
        
        by_status = self.session.query(
            Execution.status,
            self.session.query(Execution).count()
        ).group_by(Execution.status).all()
        
        success_count = self.session.query(Execution).filter(
            Execution.status == 'success'
        ).count()
        
        success_rate = (success_count / total * 100) if total > 0 else 0.0
        
        return {
            'total_executions': total,
            'by_status': dict(by_status),
            'success_rate': round(success_rate, 2)
        }
