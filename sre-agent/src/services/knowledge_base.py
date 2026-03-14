"""
知识库服务层
负责 Runbook 的存储、检索和相似度匹配
"""

from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import List, Dict, Any, Optional
import logging
import re

from models.database import Runbook, Alert, Investigation

logger = logging.getLogger(__name__)


class KnowledgeBaseService:
    """知识库服务"""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create_runbook(self, runbook_data: Dict[str, Any]) -> Runbook:
        """
        创建 Runbook
        
        Args:
            runbook_data: Runbook 数据
            
        Returns:
            Runbook: 创建的 Runbook 对象
        """
        runbook = Runbook(
            title=runbook_data['title'],
            alert_pattern=runbook_data.get('alert_pattern'),
            description=runbook_data.get('description'),
            steps=runbook_data.get('steps', []),
            success_rate=runbook_data.get('success_rate', 0.0),
            risk_level=runbook_data.get('risk_level', 'medium'),
            requires_approval=runbook_data.get('requires_approval', True),
            estimated_duration_seconds=runbook_data.get('estimated_duration_seconds', 60)
        )
        
        self.session.add(runbook)
        self.session.commit()
        self.session.refresh(runbook)
        
        logger.info(f"创建 Runbook: id={runbook.id}, title={runbook.title}")
        
        return runbook
    
    def get_runbook(self, runbook_id: int) -> Optional[Runbook]:
        """获取 Runbook 详情"""
        return self.session.query(Runbook).filter(Runbook.id == runbook_id).first()
    
    def list_runbooks(
        self,
        alert_pattern: Optional[str] = None,
        risk_level: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Runbook]:
        """
        获取 Runbook 列表
        
        Args:
            alert_pattern: 告警模式过滤
            risk_level: 风险等级过滤
            limit: 返回数量限制
            offset: 偏移量
            
        Returns:
            Runbook 列表
        """
        query = self.session.query(Runbook)
        
        if alert_pattern:
            query = query.filter(
                or_(
                    Runbook.alert_pattern == alert_pattern,
                    Runbook.alert_pattern.like(f'%{alert_pattern}%')
                )
            )
        
        if risk_level:
            query = query.filter(Runbook.risk_level == risk_level)
        
        runbooks = query.order_by(
            Runbook.success_rate.desc(),
            Runbook.risk_level.asc()
        ).offset(offset).limit(limit).all()
        
        return runbooks
    
    def search_runbooks_by_alert(self, alert_name: str, limit: int = 3) -> List[Runbook]:
        """
        根据告警名称搜索推荐 Runbook
        
        使用多种匹配策略：
        1. 精确匹配告警模式
        2. 正则表达式匹配
        3. 关键词匹配
        4. 基于成功率的排序
        
        Args:
            alert_name: 告警名称
            limit: 返回数量限制
            
        Returns:
            推荐的 Runbook 列表
        """
        logger.info(f"搜索 Runbook: alert_name={alert_name}")
        
        # 策略 1: 精确匹配
        exact_matches = self.session.query(Runbook).filter(
            Runbook.alert_pattern == alert_name
        ).all()
        
        if exact_matches:
            logger.info(f"精确匹配到 {len(exact_matches)} 个 Runbook")
            return sorted(exact_matches, key=lambda x: x.success_rate or 0, reverse=True)[:limit]
        
        # 策略 2: 正则匹配
        regex_matches = []
        all_runbooks = self.session.query(Runbook).filter(
            Runbook.alert_pattern.isnot(None)
        ).all()
        
        for runbook in all_runbooks:
            try:
                if runbook.alert_pattern and re.search(runbook.alert_pattern, alert_name, re.IGNORECASE):
                    regex_matches.append(runbook)
            except re.error:
                # 不是有效正则，跳过
                pass
        
        if regex_matches:
            logger.info(f"正则匹配到 {len(regex_matches)} 个 Runbook")
            return sorted(regex_matches, key=lambda x: x.success_rate or 0, reverse=True)[:limit]
        
        # 策略 3: 关键词匹配
        keywords = self._extract_keywords(alert_name)
        keyword_matches = []
        
        for runbook in all_runbooks:
            score = 0
            if runbook.alert_pattern:
                for keyword in keywords:
                    if keyword.lower() in runbook.alert_pattern.lower():
                        score += 1
                    if keyword.lower() in runbook.title.lower():
                        score += 1
            
            if score > 0:
                keyword_matches.append((runbook, score))
        
        if keyword_matches:
            logger.info(f"关键词匹配到 {len(keyword_matches)} 个 Runbook")
            keyword_matches.sort(key=lambda x: x[1], reverse=True)
            return [rb for rb, score in keyword_matches[:limit]]
        
        # 策略 4: 返回所有（按成功率排序）
        logger.info("无匹配，返回全部 Runbook")
        return self.session.query(Runbook).order_by(
            Runbook.success_rate.desc()
        ).limit(limit).all()
    
    def _extract_keywords(self, alert_name: str) -> List[str]:
        """
        从告警名称提取关键词
        
        例如：
        - "HighCPUUsage" -> ["High", "CPU", "Usage"]
        - "PodCrashLoopBackOff" -> ["Pod", "Crash", "Loop", "Back", "Off"]
        """
        # 驼峰命名拆分
        import re
        words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', alert_name)
        
        # 转小写，过滤常见词
        common_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were'}
        keywords = [w.lower() for w in words if w.lower() not in common_words]
        
        return keywords
    
    def update_runbook_success_rate(self, runbook_id: int, success: bool):
        """
        更新 Runbook 成功率
        
        使用移动平均：
        new_rate = old_rate * 0.9 + (1.0 if success else 0.0) * 0.1
        
        Args:
            runbook_id: Runbook ID
            success: 是否成功
        """
        runbook = self.get_runbook(runbook_id)
        if not runbook:
            return
        
        current_rate = float(runbook.success_rate) if runbook.success_rate else 0.0
        new_rate = current_rate * 0.9 + (1.0 if success else 0.0) * 0.1
        
        runbook.success_rate = round(new_rate, 2)
        self.session.commit()
        
        logger.info(f"更新 Runbook 成功率：id={runbook_id}, new_rate={new_rate}")
    
    def get_similar_investigations(
        self,
        alert_name: str,
        service_name: str,
        limit: int = 5
    ) -> List[Investigation]:
        """
        获取相似的历史问题分析
        
        Args:
            alert_name: 告警名称
            service_name: 服务名称
            limit: 返回数量限制
            
        Returns:
            相似的历史分析记录
        """
        # 查询相同告警的历史分析
        investigations = self.session.query(Investigation).join(Alert).filter(
            and_(
                Alert.alert_name == alert_name,
                Alert.service_name == service_name,
                Investigation.root_cause.isnot(None)
            )
        ).order_by(
            Investigation.created_at.desc()
        ).limit(limit).all()
        
        if investigations:
            return investigations
        
        # 如果没有相同服务的，查询相同告警的
        investigations = self.session.query(Investigation).join(Alert).filter(
            and_(
                Alert.alert_name == alert_name,
                Investigation.root_cause.isnot(None)
            )
        ).order_by(
            Investigation.created_at.desc()
        ).limit(limit).all()
        
        return investigations
    
    def get_runbook_stats(self) -> Dict[str, Any]:
        """
        获取知识库统计信息
        
        Returns:
            统计信息字典
        """
        total = self.session.query(Runbook).count()
        
        by_risk = self.session.query(
            Runbook.risk_level,
            self.session.query(Runbook).count()
        ).group_by(Runbook.risk_level).all()
        
        avg_success = self.session.query(
            self.session.query(Runbook.success_rate).filter(
                Runbook.success_rate.isnot(None)
            )
        ).scalar() or 0.0
        
        return {
            'total_runbooks': total,
            'by_risk_level': dict(by_risk),
            'avg_success_rate': round(float(avg_success), 2)
        }
