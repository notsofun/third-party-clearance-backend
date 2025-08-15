# state_handlers/handler_factory.py
from typing import Dict
from .base_handler import StateHandler
from .object_handler import OEMStateHandler, CompletedHandler, ComplianceHandler, ContractHandler, CredentialHandler, SpecialCheckHandler,DependencyHandler

class StateHandlerFactory:
    """状态处理器工厂，负责创建和缓存各状态的处理器"""
    
    def __init__(self):
        self._handlers: Dict[str, StateHandler] = {}
        self._register_handlers()
    
    def _register_handlers(self):
        """注册所有状态处理器"""
        from back_end.services.chat_flow import ConfirmationStatus
        
        # 状态处理器映射表
        self._handlers = {
            ConfirmationStatus.SPECIAL_CHECK.value: SpecialCheckHandler(),
            ConfirmationStatus.OEM.value: OEMStateHandler(),
            ConfirmationStatus.DEPENDENCY.value: DependencyHandler(),
            ConfirmationStatus.COMPLIANCE.value: ComplianceHandler(),
            ConfirmationStatus.CONTRACT.value: ContractHandler(),
            ConfirmationStatus.CREDENTIAL.value: CredentialHandler(),
            ConfirmationStatus.COMPLETED.value: CompletedHandler(),
        }
    
    def get_handler(self, status: str, bot=None) -> StateHandler:
        """获取指定状态的处理器"""
        handler = self._handlers.get(status)
        if handler:
            handler.set_bot(bot)
        return handler