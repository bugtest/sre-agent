"""
Kubernetes 客户端封装
提供常用的 K8s 操作接口
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class K8sOperationResult:
    """K8s 操作结果"""
    success: bool
    message: str
    resource_type: str
    resource_name: str
    namespace: str
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'message': self.message,
            'resource_type': self.resource_type,
            'resource_name': self.resource_name,
            'namespace': self.namespace,
            'details': self.details,
            'error': self.error
        }


class KubernetesClient:
    """
    Kubernetes 客户端
    
    注意：这是模拟实现，实际使用需要安装 kubernetes 库
    pip install kubernetes
    """
    
    def __init__(self, kubeconfig_path: Optional[str] = None, in_cluster: bool = False):
        """
        初始化 K8s 客户端
        
        Args:
            kubeconfig_path: kubeconfig 文件路径（默认 ~/.kube/config）
            in_cluster: 是否在集群内运行（使用 ServiceAccount）
        """
        self.kubeconfig_path = kubeconfig_path
        self.in_cluster = in_cluster
        self._client = None
        self._apps_v1 = None
        self._core_v1 = None
        self._initialized = False
        
        # 模拟模式（用于测试）
        self._mock_mode = True
        self._mock_resources = {
            'pods': {},
            'deployments': {}
        }
    
    def initialize(self):
        """初始化 K8s 客户端连接"""
        if self._initialized:
            return
        
        if self._mock_mode:
            logger.info("K8s 客户端：模拟模式")
            self._initialized = True
            return
        
        try:
            from kubernetes import client, config
            
            if self.in_cluster:
                # 集群内运行
                config.load_incluster_config()
            else:
                # 使用 kubeconfig
                config.load_kube_config(config_file=self.kubeconfig_path)
            
            self._apps_v1 = client.AppsV1Api()
            self._core_v1 = client.CoreV1Api()
            self._initialized = True
            
            logger.info("K8s 客户端初始化成功")
            
        except ImportError:
            logger.warning("kubernetes 库未安装，使用模拟模式")
            self._mock_mode = True
            self._initialized = True
        except Exception as e:
            logger.error(f"K8s 客户端初始化失败：{e}")
            raise
    
    def get_pod(self, name: str, namespace: str = 'default') -> Optional[Dict[str, Any]]:
        """
        获取 Pod 信息
        
        Args:
            name: Pod 名称
            namespace: 命名空间
            
        Returns:
            Pod 信息字典
        """
        self.initialize()
        
        if self._mock_mode:
            return self._mock_resources['pods'].get(f"{namespace}/{name}")
        
        try:
            pod = self._core_v1.read_namespaced_pod(name=name, namespace=namespace)
            return {
                'name': pod.metadata.name,
                'namespace': pod.metadata.namespace,
                'status': pod.status.phase,
                'containers': [c.name for c in pod.spec.containers],
                'resources': {
                    c.name: {
                        'requests': c.resources.requests,
                        'limits': c.resources.limits
                    } for c in pod.spec.containers
                }
            }
        except Exception as e:
            logger.error(f"获取 Pod 失败：{e}")
            return None
    
    def restart_pod(self, name: str, namespace: str = 'default') -> K8sOperationResult:
        """
        重启 Pod（通过删除让 Deployment 重建）
        
        Args:
            name: Pod 名称
            namespace: 命名空间
            
        Returns:
            K8sOperationResult
        """
        self.initialize()
        
        try:
            if self._mock_mode:
                logger.info(f"[MOCK] 删除 Pod: {namespace}/{name}")
                if f"{namespace}/{name}" in self._mock_resources['pods']:
                    del self._mock_resources['pods'][f"{namespace}/{name}"]
                
                return K8sOperationResult(
                    success=True,
                    message=f"Pod {name} 已删除，Deployment 将自动重建",
                    resource_type='Pod',
                    resource_name=name,
                    namespace=namespace,
                    details={'action': 'deleted'}
                )
            
            # 实际删除 Pod
            self._core_v1.delete_namespaced_pod(
                name=name,
                namespace=namespace,
                grace_period_seconds=0
            )
            
            logger.info(f"Pod 已删除：{namespace}/{name}")
            
            return K8sOperationResult(
                success=True,
                message=f"Pod {name} 已删除，Deployment 将自动重建",
                resource_type='Pod',
                resource_name=name,
                namespace=namespace,
                details={'action': 'deleted'}
            )
            
        except Exception as e:
            logger.error(f"重启 Pod 失败：{e}")
            return K8sOperationResult(
                success=False,
                message=f"重启 Pod 失败：{str(e)}",
                resource_type='Pod',
                resource_name=name,
                namespace=namespace,
                error=str(e)
            )
    
    def scale_deployment(
        self,
        name: str,
        replicas: int,
        namespace: str = 'default'
    ) -> K8sOperationResult:
        """
        扩容/缩容 Deployment
        
        Args:
            name: Deployment 名称
            replicas: 副本数
            namespace: 命名空间
            
        Returns:
            K8sOperationResult
        """
        self.initialize()
        
        try:
            if self._mock_mode:
                logger.info(f"[MOCK] 扩容 Deployment: {namespace}/{name} -> {replicas} replicas")
                self._mock_resources['deployments'][f"{namespace}/{name}"] = {
                    'replicas': replicas
                }
                
                return K8sOperationResult(
                    success=True,
                    message=f"Deployment {name} 已扩容到 {replicas} 副本",
                    resource_type='Deployment',
                    resource_name=name,
                    namespace=namespace,
                    details={'replicas': replicas, 'action': 'scaled'}
                )
            
            # 实际扩容
            deployment = self._apps_v1.read_namespaced_deployment(name=name, namespace=namespace)
            deployment.spec.replicas = replicas
            
            self._apps_v1.patch_namespaced_deployment(
                name=name,
                namespace=namespace,
                body=deployment
            )
            
            logger.info(f"Deployment 已扩容：{namespace}/{name} -> {replicas} replicas")
            
            return K8sOperationResult(
                success=True,
                message=f"Deployment {name} 已扩容到 {replicas} 副本",
                resource_type='Deployment',
                resource_name=name,
                namespace=namespace,
                details={'replicas': replicas, 'action': 'scaled'}
            )
            
        except Exception as e:
            logger.error(f"扩容 Deployment 失败：{e}")
            return K8sOperationResult(
                success=False,
                message=f"扩容失败：{str(e)}",
                resource_type='Deployment',
                resource_name=name,
                namespace=namespace,
                error=str(e)
            )
    
    def update_pod_resources(
        self,
        name: str,
        cpu_limit: Optional[str] = None,
        memory_limit: Optional[str] = None,
        namespace: str = 'default'
    ) -> K8sOperationResult:
        """
        更新 Pod 资源限制
        
        Args:
            name: Pod 名称
            cpu_limit: CPU 限制（如 "2000m"）
            memory_limit: 内存限制（如 "4Gi"）
            namespace: 命名空间
            
        Returns:
            K8sOperationResult
        """
        self.initialize()
        
        try:
            if self._mock_mode:
                logger.info(f"[MOCK] 更新 Pod 资源：{namespace}/{name}")
                
                updates = {}
                if cpu_limit:
                    updates['cpu_limit'] = cpu_limit
                if memory_limit:
                    updates['memory_limit'] = memory_limit
                
                pod_key = f"{namespace}/{name}"
                if pod_key in self._mock_resources['pods']:
                    self._mock_resources['pods'][pod_key]['resources'] = updates
                else:
                    self._mock_resources['pods'][pod_key] = {'resources': updates}
                
                return K8sOperationResult(
                    success=True,
                    message=f"Pod {name} 资源限制已更新",
                    resource_type='Pod',
                    resource_name=name,
                    namespace=namespace,
                    details=updates
                )
            
            # 实际更新（需要更新 Deployment）
            # 注意：直接更新 Pod 资源限制比较复杂，通常通过更新 Deployment 实现
            logger.warning("更新 Pod 资源限制需要通过 Deployment 实现")
            
            return K8sOperationResult(
                success=False,
                message="更新 Pod 资源限制需要通过 Deployment 实现",
                resource_type='Pod',
                resource_name=name,
                namespace=namespace,
                error='Not implemented for direct Pod update'
            )
            
        except Exception as e:
            logger.error(f"更新 Pod 资源失败：{e}")
            return K8sOperationResult(
                success=False,
                message=f"更新失败：{str(e)}",
                resource_type='Pod',
                resource_name=name,
                namespace=namespace,
                error=str(e)
            )
    
    def get_deployment(self, name: str, namespace: str = 'default') -> Optional[Dict[str, Any]]:
        """
        获取 Deployment 信息
        
        Args:
            name: Deployment 名称
            namespace: 命名空间
            
        Returns:
            Deployment 信息字典
        """
        self.initialize()
        
        if self._mock_mode:
            return self._mock_resources['deployments'].get(f"{namespace}/{name}")
        
        try:
            deployment = self._apps_v1.read_namespaced_deployment(name=name, namespace=namespace)
            return {
                'name': deployment.metadata.name,
                'namespace': deployment.metadata.namespace,
                'replicas': deployment.spec.replicas,
                'ready_replicas': deployment.status.ready_replicas,
                'available_replicas': deployment.status.available_replicas
            }
        except Exception as e:
            logger.error(f"获取 Deployment 失败：{e}")
            return None
    
    def list_pods(
        self,
        namespace: str = 'default',
        label_selector: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        列出 Pod
        
        Args:
            namespace: 命名空间
            label_selector: 标签选择器
            
        Returns:
            Pod 列表
        """
        self.initialize()
        
        if self._mock_mode:
            pods = []
            for key, pod in self._mock_resources['pods'].items():
                if key.startswith(f"{namespace}/"):
                    pods.append({**pod, 'name': key.split('/')[-1], 'namespace': namespace})
            return pods
        
        try:
            kwargs = {'namespace': namespace}
            if label_selector:
                kwargs['label_selector'] = label_selector
            
            pod_list = self._core_v1.list_namespaced_pod(**kwargs)
            return [
                {
                    'name': pod.metadata.name,
                    'namespace': pod.metadata.namespace,
                    'status': pod.status.phase,
                    'labels': pod.metadata.labels or {}
                }
                for pod in pod_list.items
            ]
        except Exception as e:
            logger.error(f"列出 Pod 失败：{e}")
            return []


# 全局客户端实例
_k8s_client = None


def get_k8s_client(kubeconfig_path: Optional[str] = None, in_cluster: bool = False) -> KubernetesClient:
    """获取全局 K8s 客户端"""
    global _k8s_client
    if _k8s_client is None:
        _k8s_client = KubernetesClient(kubeconfig_path=kubeconfig_path, in_cluster=in_cluster)
    return _k8s_client
