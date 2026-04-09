"""内容源基类"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List


class ContentSource(ABC):
    """内容源基类

    职责：将外部数据源转换为内容生成系统的输入格式
    """

    @abstractmethod
    def fetch(self, **kwargs) -> str:
        """获取原始内容

        Args:
            **kwargs: 数据源特定参数

        Returns:
            原始内容文本
        """
        pass

    @abstractmethod
    def get_metadata(self) -> Dict[str, Any]:
        """获取元数据

        Returns:
            元数据字典
        """
        pass
