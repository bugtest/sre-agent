"""
集成客户端单元测试（Prometheus + Loki）
"""

import pytest
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from integrations.prometheus_client import PrometheusClient
from integrations.loki_client import LokiClient


class TestPrometheusClient:
    """Prometheus 客户端测试"""
    
    @pytest.fixture
    def client(self):
        """创建 Prometheus 客户端（模拟模式）"""
        return PrometheusClient(url='http://localhost:9090')
    
    def test_query(self, client):
        """测试即时查询"""
        result = client.query('up')
        assert result is not None
    
    def test_query_range(self, client):
        """测试范围查询"""
        end = datetime.now()
        start = end - timedelta(minutes=30)
        
        result = client.query_range(
            'container_cpu_usage_seconds_total',
            start,
            end,
            step=60
        )
        
        assert result is not None
        assert 'result' in result
    
    def test_get_metric_value(self, client):
        """测试获取指标值"""
        value = client.get_metric_value(
            metric_name='container_cpu_usage_seconds_total',
            service_name='payment-service'
        )
        
        assert value is not None
        assert isinstance(value, float)
    
    def test_get_metric_history(self, client):
        """测试获取指标历史"""
        history = client.get_metric_history(
            metric_name='container_cpu_usage_seconds_total',
            service_name='payment-service',
            duration_minutes=60
        )
        
        assert isinstance(history, list)
        assert len(history) > 0
        assert 'timestamp' in history[0]
        assert 'value' in history[0]
    
    def test_get_cpu_usage(self, client):
        """测试获取 CPU 使用率"""
        result = client.get_cpu_usage('payment-service')
        
        assert result['metric_name'] == 'cpu_usage'
        assert result['service'] == 'payment-service'
        assert 'current' in result
        assert 'history' in result
        assert 'trend' in result
        assert result['trend'] in ['increasing', 'decreasing', 'stable']
    
    def test_get_memory_usage(self, client):
        """测试获取内存使用率"""
        result = client.get_memory_usage('payment-service')
        
        assert result['metric_name'] == 'memory_usage'
        assert result['service'] == 'payment-service'
    
    def test_get_request_rate(self, client):
        """测试获取请求速率"""
        result = client.get_request_rate('payment-service')
        
        assert result['metric_name'] == 'request_rate'
        assert result['service'] == 'payment-service'
    
    def test_calculate_trend_increasing(self, client):
        """测试趋势计算 - 上升"""
        values = [
            {'timestamp': datetime.now(), 'value': 50},
            {'timestamp': datetime.now(), 'value': 55},
            {'timestamp': datetime.now(), 'value': 60},
            {'timestamp': datetime.now(), 'value': 65},
            {'timestamp': datetime.now(), 'value': 70}
        ]
        
        trend = client._calculate_trend(values)
        assert trend == 'increasing'
    
    def test_calculate_trend_decreasing(self, client):
        """测试趋势计算 - 下降"""
        values = [
            {'timestamp': datetime.now(), 'value': 70},
            {'timestamp': datetime.now(), 'value': 65},
            {'timestamp': datetime.now(), 'value': 60},
            {'timestamp': datetime.now(), 'value': 55},
            {'timestamp': datetime.now(), 'value': 50}
        ]
        
        trend = client._calculate_trend(values)
        assert trend == 'decreasing'
    
    def test_calculate_trend_stable(self, client):
        """测试趋势计算 - 稳定"""
        values = [
            {'timestamp': datetime.now(), 'value': 50},
            {'timestamp': datetime.now(), 'value': 50.5},
            {'timestamp': datetime.now(), 'value': 49.5},
            {'timestamp': datetime.now(), 'value': 50.2},
            {'timestamp': datetime.now(), 'value': 49.8}
        ]
        
        trend = client._calculate_trend(values)
        assert trend == 'stable'
    
    def test_check_health(self, client):
        """测试健康检查"""
        health = client.check_health()
        assert health is True  # 模拟模式返回 True
    
    def test_enable_mock(self, client):
        """测试启用/禁用模拟"""
        assert client._mock_mode is True
        client.enable_mock(False)
        assert client._mock_mode is False
        client.enable_mock(True)
        assert client._mock_mode is True


class TestLokiClient:
    """Loki 客户端测试"""
    
    @pytest.fixture
    def client(self):
        """创建 Loki 客户端（模拟模式）"""
        return LokiClient(url='http://localhost:3100')
    
    def test_query(self, client):
        """测试日志查询"""
        result = client.query('{service="payment-service"}')
        assert result is not None
        assert 'streams' in result
    
    def test_query_instant(self, client):
        """测试即时查询"""
        result = client.query_instant('{service="payment-service"}')
        assert result is not None
    
    def test_get_logs(self, client):
        """测试获取日志"""
        logs = client.get_logs(
            service_name='payment-service',
            namespace='production',
            limit=50
        )
        
        assert isinstance(logs, list)
        assert len(logs) > 0
        assert 'timestamp' in logs[0]
        assert 'line' in logs[0]
        assert 'labels' in logs[0]
    
    def test_get_error_logs(self, client):
        """测试获取错误日志"""
        logs = client.get_error_logs(
            service_name='payment-service',
            namespace='production',
            limit=20
        )
        
        assert isinstance(logs, list)
        # 验证都是错误日志
        for log in logs:
            assert 'ERROR' in log['line'] or 'error' in log['labels'].get('level', '')
    
    def test_get_warn_logs(self, client):
        """测试获取警告日志"""
        logs = client.get_warn_logs(
            service_name='payment-service',
            namespace='production',
            limit=20
        )
        
        assert isinstance(logs, list)
        # 验证都是警告日志
        for log in logs:
            assert 'WARN' in log['line'] or 'warn' in log['labels'].get('level', '')
    
    def test_search_logs(self, client):
        """测试搜索日志"""
        logs = client.search_logs(
            pattern='timeout',
            service_name='payment-service',
            limit=20
        )
        
        assert isinstance(logs, list)
        # 验证匹配度排序
        if len(logs) > 1:
            assert logs[0]['match_score'] >= logs[-1]['match_score']
    
    def test_get_log_stats(self, client):
        """测试获取日志统计"""
        stats = client.get_log_stats(
            service_name='payment-service',
            namespace='production',
            duration_minutes=60
        )
        
        assert stats['service'] == 'payment-service'
        assert 'error_count' in stats
        assert 'warn_count' in stats
        assert 'info_count' in stats
        assert 'total_count' in stats
        assert 'error_rate' in stats
    
    def test_get_recent_errors(self, client):
        """测试获取最近错误"""
        errors = client.get_recent_errors(
            namespace='production',
            limit=20
        )
        
        assert isinstance(errors, list)
        # 验证按时间倒序
        if len(errors) > 1:
            assert errors[0]['timestamp'] >= errors[-1]['timestamp']
    
    def test_calculate_match_score(self, client):
        """测试匹配分数计算"""
        line = "ERROR: Connection timeout to database server"
        
        # 完全匹配
        score1 = client._calculate_match_score(line, 'timeout')
        assert score1 >= 1.0
        
        # 多次出现
        line2 = "timeout timeout timeout"
        score2 = client._calculate_match_score(line2, 'timeout')
        assert score2 > score1
        
        # 出现在开头
        line3 = "timeout: connection failed"
        score3 = client._calculate_match_score(line3, 'timeout')
        assert score3 > 1.0
    
    def test_check_health(self, client):
        """测试健康检查"""
        health = client.check_health()
        assert health is True  # 模拟模式返回 True
    
    def test_enable_mock(self, client):
        """测试启用/禁用模拟"""
        assert client._mock_mode is True
        client.enable_mock(False)
        assert client._mock_mode is False
        client.enable_mock(True)
        assert client._mock_mode is True


class TestIntegration:
    """集成场景测试"""
    
    @pytest.fixture
    def prometheus_client(self):
        return PrometheusClient()
    
    @pytest.fixture
    def loki_client(self):
        return LokiClient()
    
    def test_cpu_high_investigation(self, prometheus_client, loki_client):
        """测试 CPU 高问题调查场景"""
        service = 'payment-service'
        
        # 1. 获取 CPU 指标
        cpu_data = prometheus_client.get_cpu_usage(service)
        
        assert cpu_data['current'] is not None
        assert cpu_data['trend'] in ['increasing', 'decreasing', 'stable']
        
        # 2. 如果是上升趋势，检查请求量
        if cpu_data['trend'] == 'increasing':
            request_data = prometheus_client.get_request_rate(service)
            assert request_data['current'] is not None
        
        # 3. 获取错误日志
        error_logs = loki_client.get_error_logs(service, limit=10)
        
        # 4. 综合分析
        investigation = {
            'service': service,
            'cpu_current': cpu_data['current'],
            'cpu_trend': cpu_data['trend'],
            'error_count': len(error_logs),
            'recent_errors': [log['line'] for log in error_logs[:3]]
        }
        
        assert investigation['service'] == service
        assert 'cpu_current' in investigation
        assert 'cpu_trend' in investigation


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
