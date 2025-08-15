# state_handlers/base_handler.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple

class StateHandler(ABC):
    """状态处理器基类"""
    
    def __init__(self, bot=None):
        self.bot = bot
    
    def set_bot(self, bot):
        self.bot = bot
        
    @abstractmethod
    def get_instructions(self) -> str:
        """获取状态指导语"""
        pass
        
    def process_special_logic(self, shared: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
        """处理特殊逻辑，默认不做任何处理"""
        return shared