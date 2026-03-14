"""
分析引擎 - 规则引擎部分
负责基于规则的问题分析和根因定位
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """分析结果"""
    alert_id: int
    root_cause: Optional[str] = None
    confidence: float = 0.0
    possible_causes: List[Dict[str, Any]] = field(default_factory=list)
    related_logs: List[Dict[str, Any]] = field(default_factory=list)
    related_metrics: Dict[str, Any] = field(default_factory=dict)
    recommended_actions: List[Dict[str, Any]] = field(default_factory=list)
    analysis_time_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'alert_id': self.alert_id,
            'root_cause': self.root_cause,
            'confidence': self.confidence,
            'possible_causes': self.possible_causes,
            'related_logs': self.related_logs,
            'related_metrics': self.related_metrics,
            'recommended_actions': self.recommended_actions,
            'analysis_time_ms': self.analysis_time_ms
        }


@dataclass
class Rule:
    """分析规则"""
    id: str
    name: str
    description: str
    condition: callable  # 条件判断函数
    action: callable  # 执行动作
    priority: int = 0  # 优先级，越高越先执行
    enabled: bool = True


class RuleEngine:
    """规则引擎"""
    
    def __init__(self):
        self.rules: List[Rule] = []
        self._register_builtin_rules()
    
    def _register_builtin_rules(self):
        """注册内置规则"""
        
        # ==================== CPU 相关规则 ====================
        
        self.rules.append(Rule(
            id='cpu-high-simple',
            name='CPU 使用率过高 - 简单阈值',
            description='当 CPU 使用率超过阈值时触发',
            condition=lambda ctx: (
                ctx.get('metric_name') == 'cpu_usage' and
                ctx.get('metric_value', 0) > ctx.get('threshold', 80)
            ),
            action=self._cpu_high_action,
            priority=10
        ))
        
        self.rules.append(Rule(
            id='cpu-high-traffic-spike',
            name='CPU 使用率过高 - 流量突增',
            description='CPU 高且请求量突增',
            condition=lambda ctx: (
                ctx.get('metric_name') == 'cpu_usage' and
                ctx.get('metric_value', 0) > 80 and
                ctx.get('request_rate_change', 0) > 0.5  # 请求量增长 50%+
            ),
            action=self._cpu_high_traffic_action,
            priority=20
        ))
        
        self.rules.append(Rule(
            id='cpu-high-memory-pressure',
            name='CPU 使用率过高 - 内存压力',
            description='CPU 高且内存使用率也高',
            condition=lambda ctx: (
                ctx.get('metric_name') == 'cpu_usage' and
                ctx.get('metric_value', 0) > 80 and
                ctx.get('memory_usage', 0) > 80
            ),
            action=self._cpu_high_memory_action,
            priority=15
        ))
        
        # ==================== 内存相关规则 ====================
        
        self.rules.append(Rule(
            id='memory-high-simple',
            name='内存使用率过高',
            description='当内存使用率超过阈值时触发',
            condition=lambda ctx: (
                ctx.get('metric_name') == 'memory_usage' and
                ctx.get('metric_value', 0) > ctx.get('threshold', 80)
            ),
            action=self._memory_high_action,
            priority=10
        ))
        
        self.rules.append(Rule(
            id='memory-leak-detect',
            name='内存泄漏检测',
            description='内存持续增长',
            condition=lambda ctx: (
                ctx.get('metric_name') == 'memory_usage' and
                ctx.get('memory_trend', 'stable') == 'increasing'
            ),
            action=self._memory_leak_action,
            priority=25
        ))
        
        # ==================== 服务可用性规则 ====================
        
        self.rules.append(Rule(
            id='service-down',
            name='服务宕机',
            description='服务不可用',
            condition=lambda ctx: (
                ctx.get('alert_name', '').lower().find('down') >= 0 or
                ctx.get('status_code', 200) >= 500
            ),
            action=self._service_down_action,
            priority=30
        ))
        
        self.rules.append(Rule(
            id='pod-crashloop',
            name='Pod 崩溃循环',
            description='Pod 反复重启',
            condition=lambda ctx: (
                ctx.get('alert_name', '').lower().find('crashloop') >= 0 or
                ctx.get('restart_count', 0) > 3
            ),
            action=self._pod_crashloop_action,
            priority=30
        ))
        
        # ==================== 磁盘相关规则 ====================
        
        self.rules.append(Rule(
            id='disk-low',
            name='磁盘空间不足',
            description='磁盘使用率超过阈值',
            condition=lambda ctx: (
                ctx.get('metric_name', '').lower().find('disk') >= 0 and
                ctx.get('metric_value', 0) > ctx.get('threshold', 85)
            ),
            action=self._disk_low_action,
            priority=15
        ))
        
        # ==================== 延迟相关规则 ====================
        
        self.rules.append(Rule(
            id='high-latency',
            name='高延迟',
            description='响应时间超过阈值',
            condition=lambda ctx: (
                ctx.get('metric_name', '').lower().find('latency') >= 0 and
                ctx.get('metric_value', 0) > ctx.get('threshold', 1000)
            ),
            action=self._high_latency_action,
            priority=20
        ))
    
    # ==================== 规则动作实现 ====================
    
    def _cpu_high_action(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """CPU 过高处理动作"""
        metric_value = ctx.get('metric_value', 0)
        
        if metric_value > 95:
            root_cause = "CPU 使用率极高，可能是计算密集型任务或资源不足"
            confidence = 0.8
        elif metric_value > 90:
            root_cause = "CPU 使用率过高，建议检查近期部署和资源使用趋势"
            confidence = 0.7
        else:
            root_cause = "CPU 使用率超过阈值，需要关注"
            confidence = 0.6
        
        return {
            'root_cause': root_cause,
            'confidence': confidence,
            'possible_causes': [
                {'cause': '流量突增', 'probability': 0.4},
                {'cause': '代码性能问题', 'probability': 0.3},
                {'cause': '资源配额不足', 'probability': 0.2},
                {'cause': '异常计算任务', 'probability': 0.1}
            ],
            'recommended_actions': [
                {'action': '检查请求量变化', 'priority': 'high'},
                {'action': '查看 CPU 使用趋势', 'priority': 'high'},
                {'action': '检查近期部署', 'priority': 'medium'},
                {'action': '考虑扩容', 'priority': 'medium'}
            ]
        }
    
    def _cpu_high_traffic_action(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """CPU 高 + 流量突增处理"""
        return {
            'root_cause': '流量突增导致 CPU 资源不足',
            'confidence': 0.9,
            'possible_causes': [
                {'cause': '营销活动', 'probability': 0.4},
                {'cause': '热点事件', 'probability': 0.3},
                {'cause': '爬虫攻击', 'probability': 0.2},
                {'cause': '正常业务增长', 'probability': 0.1}
            ],
            'recommended_actions': [
                {'action': '立即扩容（增加副本）', 'priority': 'critical'},
                {'action': '检查是否有异常流量', 'priority': 'high'},
                {'action': '启用限流保护', 'priority': 'high'}
            ]
        }
    
    def _cpu_high_memory_action(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """CPU 高 + 内存高处理"""
        return {
            'root_cause': '系统资源全面紧张，可能是负载过高或资源泄漏',
            'confidence': 0.85,
            'possible_causes': [
                {'cause': '负载过高', 'probability': 0.5},
                {'cause': '内存泄漏导致 GC 频繁', 'probability': 0.3},
                {'cause': '资源配额不足', 'probability': 0.2}
            ],
            'recommended_actions': [
                {'action': '同时扩容 CPU 和内存', 'priority': 'critical'},
                {'action': '检查 GC 日志', 'priority': 'high'},
                {'action': '分析内存使用分布', 'priority': 'high'}
            ]
        }
    
    def _memory_high_action(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """内存过高处理"""
        return {
            'root_cause': '内存使用率过高',
            'confidence': 0.75,
            'possible_causes': [
                {'cause': '内存泄漏', 'probability': 0.4},
                {'cause': '数据缓存过多', 'probability': 0.3},
                {'cause': '并发请求过多', 'probability': 0.2},
                {'cause': '资源配额不足', 'probability': 0.1}
            ],
            'recommended_actions': [
                {'action': '检查内存使用趋势', 'priority': 'high'},
                {'action': '分析堆内存分布', 'priority': 'high'},
                {'action': '考虑增加内存限制', 'priority': 'medium'}
            ]
        }
    
    def _memory_leak_action(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """内存泄漏处理"""
        return {
            'root_cause': '检测到内存持续增长，可能存在内存泄漏',
            'confidence': 0.8,
            'possible_causes': [
                {'cause': '未释放的对象引用', 'probability': 0.4},
                {'cause': '缓存无上限', 'probability': 0.3},
                {'cause': '连接未关闭', 'probability': 0.2},
                {'cause': '事件监听器未移除', 'probability': 0.1}
            ],
            'recommended_actions': [
                {'action': '生成堆转储分析', 'priority': 'high'},
                {'action': '检查近期代码变更', 'priority': 'high'},
                {'action': '重启服务临时缓解', 'priority': 'medium'}
            ]
        }
    
    def _service_down_action(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """服务宕机处理"""
        return {
            'root_cause': '服务不可用',
            'confidence': 0.95,
            'possible_causes': [
                {'cause': 'Pod 崩溃', 'probability': 0.4},
                {'cause': '节点故障', 'probability': 0.25},
                {'cause': '网络问题', 'probability': 0.2},
                {'cause': '依赖服务故障', 'probability': 0.15}
            ],
            'recommended_actions': [
                {'action': '检查 Pod 状态', 'priority': 'critical'},
                {'action': '查看最近日志', 'priority': 'critical'},
                {'action': '检查节点状态', 'priority': 'high'},
                {'action': '重启服务', 'priority': 'high'}
            ]
        }
    
    def _pod_crashloop_action(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Pod 崩溃循环处理"""
        return {
            'root_cause': 'Pod 反复重启，可能是应用错误或配置问题',
            'confidence': 0.85,
            'possible_causes': [
                {'cause': '应用启动失败', 'probability': 0.4},
                {'cause': '健康检查失败', 'probability': 0.25},
                {'cause': '资源不足被 OOMKilled', 'probability': 0.2},
                {'cause': '配置错误', 'probability': 0.15}
            ],
            'recommended_actions': [
                {'action': '查看 Pod 日志', 'priority': 'critical'},
                {'action': '检查事件记录', 'priority': 'critical'},
                {'action': '验证资源配置', 'priority': 'high'},
                {'action': '检查健康检查配置', 'priority': 'medium'}
            ]
        }
    
    def _disk_low_action(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """磁盘不足处理"""
        return {
            'root_cause': '磁盘空间不足',
            'confidence': 0.9,
            'possible_causes': [
                {'cause': '日志文件过多', 'probability': 0.5},
                {'cause': '数据增长过快', 'probability': 0.3},
                {'cause': '临时文件未清理', 'probability': 0.2}
            ],
            'recommended_actions': [
                {'action': '清理旧日志', 'priority': 'critical'},
                {'action': '检查大文件', 'priority': 'high'},
                {'action': '扩容磁盘', 'priority': 'medium'}
            ]
        }
    
    def _high_latency_action(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """高延迟处理"""
        return {
            'root_cause': '服务响应时间过长',
            'confidence': 0.8,
            'possible_causes': [
                {'cause': '数据库查询慢', 'probability': 0.4},
                {'cause': '外部依赖响应慢', 'probability': 0.25},
                {'cause': '资源不足', 'probability': 0.2},
                {'cause': '网络问题', 'probability': 0.15}
            ],
            'recommended_actions': [
                {'action': '检查慢查询日志', 'priority': 'high'},
                {'action': '分析链路追踪', 'priority': 'high'},
                {'action': '检查依赖服务状态', 'priority': 'medium'}
            ]
        }
    
    def analyze(self, alert_context: Dict[str, Any], historical_data: Optional[Dict] = None) -> AnalysisResult:
        """
        执行分析
        
        Args:
            alert_context: 告警上下文
            historical_data: 历史数据（可选）
                - similar_investigations: 相似历史分析
                - past_solutions: 历史解决方案成功率
            
        Returns:
            AnalysisResult: 分析结果
        """
        import time
        start_time = time.time()
        
        logger.info(f"开始分析告警：{alert_context.get('alert_name')} - {alert_context.get('service_name')}")
        
        # 按优先级排序规则
        sorted_rules = sorted(
            [r for r in self.rules if r.enabled],
            key=lambda r: r.priority,
            reverse=True
        )
        
        # 执行匹配的规则
        matched_results = []
        for rule in sorted_rules:
            try:
                if rule.condition(alert_context):
                    logger.info(f"规则匹配：{rule.id} - {rule.name}")
                    result = rule.action(alert_context)
                    matched_results.append({
                        'rule_id': rule.id,
                        'rule_name': rule.name,
                        'priority': rule.priority,
                        **result
                    })
            except Exception as e:
                logger.error(f"规则执行失败 {rule.id}: {e}")
        
        # 合并结果
        if matched_results:
            # 使用最高优先级的结果
            best_match = matched_results[0]
            
            # 如果有历史数据，调整置信度
            confidence = best_match.get('confidence', 0)
            if historical_data and historical_data.get('similar_investigations'):
                # 有相似历史案例，提高置信度
                confidence = min(confidence + 0.1, 1.0)
                logger.info(f"历史案例提升置信度：{confidence}")
            
            analysis_result = AnalysisResult(
                alert_id=alert_context.get('alert_id', 0),
                root_cause=best_match.get('root_cause'),
                confidence=confidence,
                possible_causes=best_match.get('possible_causes', []),
                recommended_actions=best_match.get('recommended_actions', []),
                analysis_time_ms=(time.time() - start_time) * 1000
            )
            
            # 添加历史案例参考
            if historical_data and historical_data.get('similar_investigations'):
                analysis_result.related_logs = historical_data['similar_investigations']
        else:
            # 无匹配规则
            analysis_result = AnalysisResult(
                alert_id=alert_context.get('alert_id', 0),
                root_cause="未匹配到已知规则，需要人工分析",
                confidence=0.3,
                possible_causes=[{'cause': '未知原因', 'probability': 1.0}],
                recommended_actions=[
                    {'action': '检查相关日志', 'priority': 'high'},
                    {'action': '查看指标趋势', 'priority': 'high'},
                    {'action': '联系相关负责人', 'priority': 'medium'}
                ],
                analysis_time_ms=(time.time() - start_time) * 1000
            )
        
        logger.info(f"分析完成：root_cause={analysis_result.root_cause}, confidence={analysis_result.confidence}")
        
        return analysis_result


# 全局规则引擎实例
_rule_engine = None


def get_rule_engine() -> RuleEngine:
    """获取全局规则引擎"""
    global _rule_engine
    if _rule_engine is None:
        _rule_engine = RuleEngine()
    return _rule_engine
