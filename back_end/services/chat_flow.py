from enum import Enum
from typing import Dict, Optional, Any, Type
from abc import ABC, abstractmethod

class ConfirmationStatus(Enum):
    """确认状态的枚举类型
    """
    SPECIAL_CHECK = "special_check"
    OEM = "OEMing"
    DEPENDENCY = "toDependency"
    COMPLIANCE = "toCompliance"


class StateHandler(ABC):

    def __init__(self):
        super().__init__()

        self.CONTINUE = 'continue'
        self.NEXT = 'next'

    """状态处理器抽象基类"""
    @abstractmethod
    def handle(self, context: Dict[str, Any]) -> Optional[ConfirmationStatus]:
        """处理当前状态并返回下一个状态"""
        pass

class SpecialCheckHandler(StateHandler):

    """
    可以简单处理context，变成一个start，cotinue, end三类
    """

    def handle(self, context: Dict[str, Any]) -> Optional[ConfirmationStatus]:
        print("执行特殊检查...")
        if context.get("special_check_passed", True):
            return ConfirmationStatus.OEM
        return None

class OEMHandler(StateHandler):
    def handle(self,status:str) -> Optional[ConfirmationStatus]:
        print("执行OEM处理...")
        if status == self.NEXT:
            return ConfirmationStatus.DEPENDENCY
        elif status == self.CONTINUE:
            return ConfirmationStatus.OEM
        else:
            raise RuntimeError('Model did not determine to go on or continue')

class DependencyHandler(StateHandler):
    def handle(self, context: Dict[str, Any]) -> Optional[ConfirmationStatus]:
        print("执行依赖检查...")
        if context.get("dependency_passed", True):
            return ConfirmationStatus.COMPLIANCE
        return ConfirmationStatus.OEM

class ComplianceHandler(StateHandler):
    def handle(self, context: Dict[str, Any]) -> Optional[ConfirmationStatus]:
        print("执行合规检查...")
        if context.get("compliance_passed", True):
            print("流程完成")
            return None  # 流程结束
        return ConfirmationStatus.DEPENDENCY

class WorkflowContext:
    """工作流上下文，管理状态和转换"""
    def __init__(self):
        # 注册状态处理器
        self.handlers: Dict[ConfirmationStatus, StateHandler] = {
            ConfirmationStatus.SPECIAL_CHECK: SpecialCheckHandler(),
            ConfirmationStatus.OEM: OEMHandler(),
            ConfirmationStatus.DEPENDENCY: DependencyHandler(),
            ConfirmationStatus.COMPLIANCE: ComplianceHandler()
        }
        # 这里是初始状态
        self.current_state = ConfirmationStatus.OEM
    
    def process(self,status:str) -> Optional[ConfirmationStatus]:
        """处理当前状态并转移到下一个状态"""
        if not self.current_state or self.current_state not in self.handlers:
            return None
        
        # 获取当前状态的处理器并执行
        handler = self.handlers[self.current_state]
        next_state = handler.handle(status)
        
        # 更新当前状态
        self.current_state = next_state
        return next_state

# 使用示例
if __name__ == "__main__":
    workflow = WorkflowContext()
    context = {"special_check_passed": True, "oem_passed": True, "dependency_passed": True, "compliance_passed": True}
    
    state = workflow.current_state
    while state:
        print(f"当前状态: {state.value}")
        state = workflow.process(context)
        if state:
            print(f"转移到状态: {state.value}")
        else:
            print("流程结束")