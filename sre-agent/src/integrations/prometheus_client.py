"""
Prometheus 客户端封装
提供指标查询接口
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging
import urllib.request
import urllib.parse
import json

logger = logging.getLogger(__name__)


class PrometheusClient:
    """
    Prometheus API 客户端
    
    支持 PromQL 查询和常用指标获取
    """
    
    def __init__(self, url: str = 'http://localhost:9090', timeout: int = 10):
        """
        初始化 Prometheus 客户端
        
        Args:
            url: Prometheus API 地址
            timeout: 请求超时时间（秒）
        """
        self.url = url.rstrip('/')
        self.timeout = timeout
        self._mock_mode = True  # 默认模拟模式
        self._mock_data = self._init_mock_data()
    
    def _init_mock_data(self) -> Dict[str, Any]:
        """初始化模拟数据"""
        return {
            'cpu_usage': {
                'payment-service': [95.5, 92.3, 88.1, 85.6, 90.2],
                'order-service': [45.2, 48.1, 50.3, 47.8, 46.5],
            },
            'memory_usage': {
                'payment-service': [78.5, 80.2, 82.1, 79.8, 81.5],
                'order-service': [55.2, 56.1, 54.8, 57.2, 55.9],
            },
            'request_rate': {
                'payment-service': [1000, 1200, 1500, 1800, 2000],
                'order-service': [500, 520, 480, 510, 530],
            },
            'error_rate': {
                'payment-service': [0.1, 0.2, 0.5, 1.2, 2.5],
                'order-service': [0.1, 0.1, 0.2, 0.1, 0.1],
            },
            'disk_usage': {
                'node-1': [75.5, 76.2, 77.1, 78.5, 79.2],
                'node-2': [65.2, 65.8, 66.1, 66.5, 67.2],
            }
        }
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        发送 HTTP 请求
        
        Args:
            endpoint: API 端点（如 /api/v1/query）
            params: 查询参数
            
        Returns:
            响应数据字典
        """
        if self._mock_mode:
            logger.info(f"[MOCK] Prometheus 请求：{endpoint}, params={params}")
            return self._mock_query(endpoint, params)
        
        try:
            query_string = urllib.parse.urlencode(params) if params else ''
            url = f"{self.url}{endpoint}?{query_string}"
            
            req = urllib.request.Request(url)
            req.add_header('Content-Type', 'application/json')
            
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                data = json.loads(response.read().decode())
                return data.get('data')
                
        except Exception as e:
            logger.error(f"Prometheus 请求失败：{e}")
            return None
    
    def _mock_query(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """模拟查询"""
        if not params:
            return None
        
        query = params.get('query', '')
        
        # 简单的 PromQL 解析
        if 'cpu_usage' in query or 'node_cpu' in query:
            metric = 'cpu_usage'
        elif 'memory' in query:
            metric = 'memory_usage'
        elif 'request_rate' in query or 'rate(' in query:
            metric = 'request_rate'
        elif 'error_rate' in query or 'error' in query:
            metric = 'error_rate'
        elif 'disk' in query:
            metric = 'disk_usage'
        else:
            metric = 'cpu_usage'
        
        service = 'payment-service'
        for key in self._mock_data.get(metric, {}).keys():
            if key in query:
                service = key
                break
        
        values = self._mock_data.get(metric, {}).get(service, [50.0])
        
        return {
            'resultType': 'matrix',
            'result': [{
                'metric': {'__name__': metric, 'service': service},
                'values': [
                    [datetime.now().timestamp() - (len(values) - i - 1) * 60, str(val)]
                    for i, val in enumerate(values)
                ]
            }]
        }
    
    def query(self, promql: str, time: Optional[datetime] = None) -> Optional[Dict]:
        """
        即时查询
        
        Args:
            promql: PromQL 查询语句
            time: 查询时间点（默认当前时间）
            
        Returns:
            查询结果
        """
        params = {'query': promql}
        if time:
            params['time'] = str(int(time.timestamp()))
        
        logger.info(f"查询 Prometheus: {promql}")
        return self._make_request('/api/v1/query', params)
    
    def query_range(
        self,
        promql: str,
        start: datetime,
        end: datetime,
        step: int = 60
    ) -> Optional[Dict]:
        """
        范围查询
        
        Args:
            promql: PromQL 查询语句
            start: 开始时间
            end: 结束时间
            step: 步长（秒）
            
        Returns:
            查询结果
        """
        params = {
            'query': promql,
            'start': str(int(start.timestamp())),
            'end': str(int(end.timestamp())),
            'step': str(step)
        }
        
        logger.info(f"范围查询 Prometheus: {promql}, start={start}, end={end}")
        return self._make_request('/api/v1/query_range', params)
    
    def get_metric_value(
        self,
        metric_name: str,
        service_name: str,
        namespace: str = 'default'
    ) -> Optional[float]:
        """
        获取指标当前值
        
        Args:
            metric_name: 指标名称
            service_name: 服务名称
            namespace: 命名空间
            
        Returns:
            指标值
        """
        # 模拟模式直接返回模拟数据
        if self._mock_mode:
            for key in self._mock_data.keys():
                if metric_name.lower() in key.lower():
                    values = self._mock_data[key].get(service_name, [50.0])
                    return float(values[-1]) if values else 50.0
            return 50.0
        
        promql = f'{metric_name}{{service="{service_name}", namespace="{namespace}"}}'
        result = self.query(promql)
        
        if result and result.get('result'):
            value = result['result'][0].get('value', [None, None])[1]
            return float(value) if value else None
        
        return None
    
    def get_metric_history(
        self,
        metric_name: str,
        service_name: str,
        duration_minutes: int = 60,
        step_seconds: int = 60
    ) -> List[Dict[str, Any]]:
        """
        获取指标历史数据
        
        Args:
            metric_name: 指标名称
            service_name: 服务名称
            duration_minutes: 查询时长（分钟）
            step_seconds: 步长（秒）
            
        Returns:
            历史数据列表 [{timestamp, value}]
        """
        end = datetime.now()
        start = end - timedelta(minutes=duration_minutes)
        
        promql = f'{metric_name}{{service="{service_name}"}}'
        result = self.query_range(promql, start, end, step_seconds)
        
        if not result or not result.get('result'):
            return []
        
        values = result['result'][0].get('values', [])
        return [
            {'timestamp': datetime.fromtimestamp(ts), 'value': float(val)}
            for ts, val in values
        ]
    
    def get_cpu_usage(self, service_name: str, namespace: str = 'default') -> Dict[str, Any]:
        """
        获取 CPU 使用率
        
        Args:
            service_name: 服务名称
            namespace: 命名空间
            
        Returns:
            CPU 使用率数据
        """
        promql = f'avg(rate(container_cpu_usage_seconds_total{{service="{service_name}", namespace="{namespace}"}}[5m])) * 100'
        
        current = self.get_metric_value('container_cpu_usage_seconds_total', service_name, namespace)
        history = self.get_metric_history('container_cpu_usage_seconds_total', service_name)
        
        return {
            'metric_name': 'cpu_usage',
            'service': service_name,
            'current': current,
            'history': history,
            'trend': self._calculate_trend(history) if history else 'stable'
        }
    
    def get_memory_usage(self, service_name: str, namespace: str = 'default') -> Dict[str, Any]:
        """
        获取内存使用率
        
        Args:
            service_name: 服务名称
            namespace: 命名空间
            
        Returns:
            内存使用率数据
        """
        promql = f'avg(container_memory_usage_bytes{{service="{service_name}", namespace="{namespace}"}}) / avg(container_spec_memory_limit_bytes{{service="{service_name}", namespace="{namespace}"}}) * 100'
        
        current = self.get_metric_value('container_memory_usage_bytes', service_name, namespace)
        history = self.get_metric_history('container_memory_usage_bytes', service_name)
        
        return {
            'metric_name': 'memory_usage',
            'service': service_name,
            'current': current,
            'history': history,
            'trend': self._calculate_trend(history) if history else 'stable'
        }
    
    def get_request_rate(self, service_name: str, namespace: str = 'default') -> Dict[str, Any]:
        """
        获取请求速率
        
        Args:
            service_name: 服务名称
            namespace: 命名空间
            
        Returns:
            请求速率数据
        """
        promql = f'sum(rate(http_requests_total{{service="{service_name}", namespace="{namespace}"}}[5m]))'
        
        current = self.get_metric_value('http_requests_total', service_name, namespace)
        history = self.get_metric_history('http_requests_total', service_name)
        
        return {
            'metric_name': 'request_rate',
            'service': service_name,
            'current': current,
            'history': history,
            'trend': self._calculate_trend(history) if history else 'stable'
        }
    
    def get_error_rate(self, service_name: str, namespace: str = 'default') -> Dict[str, Any]:
        """
        获取错误率
        
        Args:
            service_name: 服务名称
            namespace: 命名空间
            
        Returns:
            错误率数据
        """
        promql = f'sum(rate(http_requests_total{{service="{service_name}", namespace="{namespace}", status=~"5.."}}[5m])) / sum(rate(http_requests_total{{service="{service_name}", namespace="{namespace}"}}[5m])) * 100'
        
        current = self.get_metric_value('http_requests_total', service_name, namespace)
        history = self.get_metric_history('http_requests_total', service_name)
        
        return {
            'metric_name': 'error_rate',
            'service': service_name,
            'current': current,
            'history': history,
            'trend': self._calculate_trend(history) if history else 'stable'
        }
    
    def _calculate_trend(self, values: List[Dict[str, Any]]) -> str:
        """
        计算趋势
        
        Args:
            values: 历史数据列表
            
        Returns:
            趋势：increasing/decreasing/stable
        """
        if len(values) < 2:
            return 'stable'
        
        recent = [v['value'] for v in values[-5:]]
        if len(recent) < 2:
            return 'stable'
        
        avg_first = sum(recent[:2]) / 2
        avg_last = sum(recent[-2:]) / 2
        
        change_rate = (avg_last - avg_first) / avg_first if avg_first > 0 else 0
        
        if change_rate > 0.1:
            return 'increasing'
        elif change_rate < -0.1:
            return 'decreasing'
        else:
            return 'stable'
    
    def check_health(self) -> bool:
        """
        检查 Prometheus 健康状态
        
        Returns:
            是否健康
        """
        try:
            result = self._make_request('/api/v1/query', {'query': 'up'})
            return result is not None
        except Exception:
            return False
    
    def enable_mock(self, enabled: bool = True):
        """启用/禁用模拟模式"""
        self._mock_mode = enabled
        logger.info(f"Prometheus 模拟模式：{'启用' if enabled else '禁用'}")


# 全局客户端实例
_prometheus_client = None


def get_prometheus_client(url: str = 'http://localhost:9090') -> PrometheusClient:
    """获取全局 Prometheus 客户端"""
    global _prometheus_client
    if _prometheus_client is None:
        _prometheus_client = PrometheusClient(url=url)
    return _prometheus_client
