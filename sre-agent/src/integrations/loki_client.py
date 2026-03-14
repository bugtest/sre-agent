"""
Loki 客户端封装
提供日志查询接口
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging
import urllib.request
import urllib.parse
import json

logger = logging.getLogger(__name__)


class LokiClient:
    """
    Loki API 客户端
    
    支持 LogQL 查询和日志检索
    """
    
    def __init__(self, url: str = 'http://localhost:3100', timeout: int = 10):
        """
        初始化 Loki 客户端
        
        Args:
            url: Loki API 地址
            timeout: 请求超时时间（秒）
        """
        self.url = url.rstrip('/')
        self.timeout = timeout
        self._mock_mode = True  # 默认模拟模式
        self._mock_logs = self._init_mock_logs()
    
    def _init_mock_logs(self) -> List[Dict[str, Any]]:
        """初始化模拟日志"""
        base_time = datetime.now()
        
        return [
            {
                'timestamp': (base_time - timedelta(minutes=i)).isoformat(),
                'line': f'[ERROR] payment-service - Connection timeout to database',
                'labels': {
                    'service': 'payment-service',
                    'level': 'error',
                    'namespace': 'production'
                }
            }
            for i in range(5)
        ] + [
            {
                'timestamp': (base_time - timedelta(minutes=i)).isoformat(),
                'line': f'[WARN] payment-service - High latency detected: {200 + i*50}ms',
                'labels': {
                    'service': 'payment-service',
                    'level': 'warn',
                    'namespace': 'production'
                }
            }
            for i in range(10)
        ] + [
            {
                'timestamp': (base_time - timedelta(minutes=i)).isoformat(),
                'line': f'[INFO] payment-service - Request processed successfully',
                'labels': {
                    'service': 'payment-service',
                    'level': 'info',
                    'namespace': 'production'
                }
            }
            for i in range(20)
        ]
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        发送 HTTP 请求
        
        Args:
            endpoint: API 端点
            params: 查询参数
            
        Returns:
            响应数据字典
        """
        if self._mock_mode:
            logger.info(f"[MOCK] Loki 请求：{endpoint}, params={params}")
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
            logger.error(f"Loki 请求失败：{e}")
            return None
    
    def _mock_query(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """模拟查询"""
        if not params:
            return {'streams': []}
        
        query = params.get('query', '')
        limit = int(params.get('limit', 100))
        
        # 简单的 LogQL 解析
        filtered_logs = self._mock_logs
        
        if 'error' in query.lower() or 'level="error"' in query:
            filtered_logs = [log for log in self._mock_logs if 'ERROR' in log['line']]
        elif 'warn' in query.lower() or 'level="warn"' in query:
            filtered_logs = [log for log in self._mock_logs if 'WARN' in log['line']]
        
        # 按服务过滤
        if 'payment-service' in query:
            filtered_logs = [log for log in filtered_logs if log['labels'].get('service') == 'payment-service']
        elif 'order-service' in query:
            filtered_logs = [log for log in filtered_logs if log['labels'].get('service') == 'order-service']
        
        # 限制数量
        filtered_logs = filtered_logs[:limit]
        
        # 转换为 Loki 格式
        streams = {}
        for log in filtered_logs:
            labels_key = str(sorted(log['labels'].items()))
            if labels_key not in streams:
                streams[labels_key] = {
                    'stream': log['labels'],
                    'values': []
                }
            streams[labels_key]['values'].append([
                log['timestamp'],
                log['line']
            ])
        
        return {
            'streams': list(streams.values()),
            'stats': {
                'summary': {
                    'bytesProcessed': len(filtered_logs) * 100,
                    'entriesReturned': len(filtered_logs)
                }
            }
        }
    
    def query(
        self,
        logql: str,
        limit: int = 100,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        direction: str = 'backward'
    ) -> Optional[Dict]:
        """
        查询日志
        
        Args:
            logql: LogQL 查询语句
            limit: 返回行数限制
            start: 开始时间
            end: 结束时间
            direction: 排序方向（forward/backward）
            
        Returns:
            查询结果
        """
        params = {
            'query': logql,
            'limit': str(limit),
            'direction': direction
        }
        
        if start:
            params['start'] = str(int(start.timestamp() * 1e9))  # Loki 使用纳秒
        if end:
            params['end'] = str(int(end.timestamp() * 1e9))
        
        logger.info(f"查询 Loki: {logql}")
        return self._make_request('/loki/api/v1/query_range', params)
    
    def query_instant(
        self,
        logql: str,
        timestamp: Optional[datetime] = None
    ) -> Optional[Dict]:
        """
        即时查询（最新日志）
        
        Args:
            logql: LogQL 查询语句
            timestamp: 查询时间点
            
        Returns:
            查询结果
        """
        params = {'query': logql}
        if timestamp:
            params['ts'] = str(int(timestamp.timestamp() * 1e9))
        
        logger.info(f"即时查询 Loki: {logql}")
        return self._make_request('/loki/api/v1/query', params)
    
    def get_logs(
        self,
        service_name: str,
        namespace: str = 'default',
        level: Optional[str] = None,
        limit: int = 100,
        duration_minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """
        获取服务日志
        
        Args:
            service_name: 服务名称
            namespace: 命名空间
            level: 日志级别（error/warn/info）
            limit: 返回行数限制
            duration_minutes: 查询时长（分钟）
            
        Returns:
            日志列表
        """
        end = datetime.now()
        start = end - timedelta(minutes=duration_minutes)
        
        # 构建 LogQL
        labels = f'{{service="{service_name}", namespace="{namespace}"'
        if level:
            labels += f', level="{level}"'
        labels += '}'
        
        logql = labels
        
        result = self.query(logql, limit=limit, start=start, end=end)
        
        if not result or not result.get('streams'):
            return []
        
        logs = []
        for stream in result['streams']:
            for timestamp, line in stream.get('values', []):
                logs.append({
                    'timestamp': timestamp,
                    'line': line,
                    'labels': stream.get('stream', {})
                })
        
        # 按时间排序
        logs.sort(key=lambda x: x['timestamp'])
        
        return logs
    
    def get_error_logs(
        self,
        service_name: str,
        namespace: str = 'default',
        limit: int = 50,
        duration_minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """
        获取错误日志
        
        Args:
            service_name: 服务名称
            namespace: 命名空间
            limit: 返回行数限制
            duration_minutes: 查询时长（分钟）
            
        Returns:
            错误日志列表
        """
        return self.get_logs(
            service_name=service_name,
            namespace=namespace,
            level='error',
            limit=limit,
            duration_minutes=duration_minutes
        )
    
    def get_warn_logs(
        self,
        service_name: str,
        namespace: str = 'default',
        limit: int = 50,
        duration_minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """
        获取警告日志
        """
        return self.get_logs(
            service_name=service_name,
            namespace=namespace,
            level='warn',
            limit=limit,
            duration_minutes=duration_minutes
        )
    
    def search_logs(
        self,
        pattern: str,
        service_name: Optional[str] = None,
        namespace: str = 'default',
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        搜索日志（按关键词）
        
        Args:
            pattern: 搜索关键词
            service_name: 服务名称（可选）
            namespace: 命名空间
            limit: 返回行数限制
            
        Returns:
            匹配的日志列表
        """
        end = datetime.now()
        start = end - timedelta(minutes=60)
        
        # 构建 LogQL（使用正则匹配）
        if service_name:
            logql = f'{{service="{service_name}", namespace="{namespace}"}} |= "{pattern}"'
        else:
            logql = f'{{namespace="{namespace}"}} |= "{pattern}"'
        
        result = self.query(logql, limit=limit, start=start, end=end)
        
        if not result or not result.get('streams'):
            return []
        
        logs = []
        for stream in result['streams']:
            for timestamp, line in stream.get('values', []):
                if pattern.lower() in line.lower():
                    logs.append({
                        'timestamp': timestamp,
                        'line': line,
                        'labels': stream.get('stream', {}),
                        'match_score': self._calculate_match_score(line, pattern)
                    })
        
        # 按匹配度排序
        logs.sort(key=lambda x: x['match_score'], reverse=True)
        
        return logs
    
    def _calculate_match_score(self, line: str, pattern: str) -> float:
        """计算匹配分数"""
        score = 0.0
        
        # 完全匹配
        if pattern.lower() in line.lower():
            score += 1.0
        
        # 多次出现
        count = line.lower().count(pattern.lower())
        score += min(count * 0.2, 1.0)
        
        # 出现在开头
        if line.lower().startswith(pattern.lower()):
            score += 0.5
        
        return score
    
    def get_log_stats(
        self,
        service_name: str,
        namespace: str = 'default',
        duration_minutes: int = 60
    ) -> Dict[str, Any]:
        """
        获取日志统计
        
        Args:
            service_name: 服务名称
            namespace: 命名空间
            duration_minutes: 统计时长（分钟）
            
        Returns:
            统计信息
        """
        end = datetime.now()
        start = end - timedelta(minutes=duration_minutes)
        
        # 获取各级别日志数量
        error_logs = self.get_error_logs(service_name, namespace, limit=1000, duration_minutes=duration_minutes)
        warn_logs = self.get_warn_logs(service_name, namespace, limit=1000, duration_minutes=duration_minutes)
        info_logs = self.get_logs(service_name, namespace, level='info', limit=1000, duration_minutes=duration_minutes)
        
        return {
            'service': service_name,
            'duration_minutes': duration_minutes,
            'error_count': len(error_logs),
            'warn_count': len(warn_logs),
            'info_count': len(info_logs),
            'total_count': len(error_logs) + len(warn_logs) + len(info_logs),
            'error_rate': len(error_logs) / max(len(error_logs) + len(warn_logs) + len(info_logs), 1) * 100
        }
    
    def get_recent_errors(
        self,
        service_name: Optional[str] = None,
        namespace: str = 'default',
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        获取最近的错误日志（跨服务）
        
        Args:
            service_name: 服务名称（可选，不指定则查询所有服务）
            namespace: 命名空间
            limit: 返回行数限制
            
        Returns:
            错误日志列表
        """
        end = datetime.now()
        start = end - timedelta(minutes=30)
        
        if service_name:
            logql = f'{{service="{service_name}", namespace="{namespace}", level="error"}}'
        else:
            logql = f'{{namespace="{namespace}", level="error"}}'
        
        result = self.query(logql, limit=limit, start=start, end=end, direction='backward')
        
        if not result or not result.get('streams'):
            return []
        
        logs = []
        for stream in result['streams']:
            for timestamp, line in stream.get('values', []):
                logs.append({
                    'timestamp': timestamp,
                    'line': line,
                    'labels': stream.get('stream', {})
                })
        
        logs.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return logs
    
    def check_health(self) -> bool:
        """
        检查 Loki 健康状态
        
        Returns:
            是否健康
        """
        if self._mock_mode:
            return True
        
        try:
            url = f"{self.url}/loki/api/v1/labels"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return response.status == 200
        except Exception:
            return False
    
    def enable_mock(self, enabled: bool = True):
        """启用/禁用模拟模式"""
        self._mock_mode = enabled
        logger.info(f"Loki 模拟模式：{'启用' if enabled else '禁用'}")


# 全局客户端实例
_loki_client = None


def get_loki_client(url: str = 'http://localhost:3100') -> LokiClient:
    """获取全局 Loki 客户端"""
    global _loki_client
    if _loki_client is None:
        _loki_client = LokiClient(url=url)
    return _loki_client
