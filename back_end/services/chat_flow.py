from enum import Enum
from typing import Dict, Optional, Any, List, Type
from abc import ABC, abstractmethod
import logging
from .item_types import ItemStatus

logger = logging.getLogger(__name__)

class ConfirmationStatus(Enum):
    """确认状态的枚举类型"""
    SPECIAL_CHECK = "special_check"
    OEM = "OEMing"
    DEPENDENCY = "toDependency"
    COMPLIANCE = "toCompliance"
    CONTRACT = 'toContract'
    CREDENTIAL = 'credential'

class StateHandler(ABC):
    """状态处理器抽象基类"""
    def __init__(self):
        self.subtasks = []  # 子任务处理器列表
        self.completed_subtasks = set()  # 已完成子任务集合
        self.CONTINUE = 'continue'
        self.NEXT = 'next'
        self.COMPLETED = 'completed'

    def add_subtask(self, handler: 'StateHandler'):
        """添加子任务处理器"""
        self.subtasks.append(handler)
    
    @abstractmethod
    def handle(self, status: str) -> Optional[str]:
        """处理当前状态并返回事件标识"""
        pass
    
    def is_completed(self) -> bool:
        """检查所有子任务是否完成"""
        return len(self.completed_subtasks) == len(self.subtasks)

class CompositeStateHandler(StateHandler):
    """复合状态处理器基类"""
    def __init__(self, next_state: ConfirmationStatus):
        super().__init__()
        self.next_state = next_state  # 所有子任务完成后的转移状态
    
    def handle(self, context: Dict[str, Any]) -> Optional[str]:
        """
        处理复合状态的核心逻辑
        这里的复合状态，context应该包含:{
            'status': 这个表示当前的状态,
            'shared': 这个表示要处理的数据
        }
        """
        # 1. 处理子任务
        for handler in self.subtasks:
            if handler not in self.completed_subtasks:
                event = handler.handle(context)
                if event == self.COMPLETED:
                    self.completed_subtasks.add(handler)
        
        # 2. 检查完成状态
        if self.is_completed():
            return "all_completed"
        return "in_progress"

# 具体状态处理器实现
class LicenseHandler(StateHandler):
    def handle(self, context: Dict[str, Any]) -> Optional[str]:
        license_data = context.get("shared", {}).get('toBeConfirmedLicenses',[])
        if all(lic.get("status") == ItemStatus.CONFIRMED.value for lic in license_data):
            return "completed"
        return "in_progress"

class ComponentHandler(StateHandler):
    def handle(self, context: Dict[str, Any]) -> Optional[str]:
        components = context.get("shared", {}).get('toBeConfirmedComponents',[])
        if all(comp.get("status") == ItemStatus.CONFIRMED.value for comp in components):
            return "completed"
        return "in_progress"

class ComplianceHandler(CompositeStateHandler):
    """合规检查复合状态"""
    def __init__(self):
        super().__init__(ConfirmationStatus.COMPLIANCE)
        # 添加子任务
        self.add_subtask(LicenseHandler())

class DependencyHandler(CompositeStateHandler):
    """依赖检查复合状态"""
    def __init__(self):
        super().__init__(ConfirmationStatus.DEPENDENCY)
        # 添加子任务
        self.add_subtask(ComponentHandler())

class CredentialHandler(CompositeStateHandler):
    """授权检查复合状态"""
    def __init__(self):
        super().__init__(ConfirmationStatus.CREDENTIAL)
        # 添加子任务
        self.add_subtask(LicenseHandler())

# 其他状态处理器（保持原有设计）
class SpecialCheckHandler(StateHandler):
    """
    这里就是和component、license一样的，从shared里面拿出来special的那个字典
    然后再细分成GPL之类的子节点
    """

    def handle(self, context: Dict[str, Any]) -> Optional[ConfirmationStatus]:
        print("执行特殊检查...")
        if context.get("special_check_passed", True):
            return ConfirmationStatus.OEM
        return None

class OEMHandler(StateHandler):
    def handle(self,context: Dict[str, Any]) -> Optional[ConfirmationStatus]:
        print("执行OEM处理...")
        status = context.get('status')
        if status == self.NEXT:
            return ConfirmationStatus.CONTRACT
        elif status == self.CONTINUE:
            return ConfirmationStatus.OEM
        else:
            raise RuntimeError('Model did not determine to go on or continue')

class ContractHandler(StateHandler):
    def handle(self, context: Dict[str, Any]) -> Optional[ConfirmationStatus]:
        print("执行合同检查...")
        status = context.get('status')
        if status == self.NEXT:
            return ConfirmationStatus.DEPENDENCY
        elif status == self.CONTINUE:
            return ConfirmationStatus.CONTRACT
        else:
            raise RuntimeError('Model did not determine to go on or continue')


class WorkflowContext:
    """工作流上下文，管理状态和转换"""
    def __init__(self):
        # 状态转移表（核心改进）
        self.transition_table = {
            ConfirmationStatus.OEM: {
                "completed": ConfirmationStatus.CONTRACT,
                "in_progress": ConfirmationStatus.OEM
            },
            ConfirmationStatus.COMPLIANCE: {
                "all_completed": ConfirmationStatus.CREDENTIAL,
                "in_progress": ConfirmationStatus.COMPLIANCE
            },
            ConfirmationStatus.CREDENTIAL: {
                "all_completed": ConfirmationStatus.SPECIAL_CHECK,
                "in_progress": ConfirmationStatus.CREDENTIAL
            },
            ConfirmationStatus.SPECIAL_CHECK: {
                "all_completed": ConfirmationStatus.COMPLIANCE,
                "in_progress": ConfirmationStatus.SPECIAL_CHECK
            },
            ConfirmationStatus.CONTRACT: {
                "all_completed": ConfirmationStatus.DEPENDENCY,
                "in_progress": ConfirmationStatus.CONTRACT
            },
            ConfirmationStatus.DEPENDENCY: {
                "all_completed": ConfirmationStatus.CREDENTIAL,
                "in_progress": ConfirmationStatus.DEPENDENCY
            },
        }
        
        # 注册状态处理器
        self.handlers: Dict[ConfirmationStatus, StateHandler] = {
            ConfirmationStatus.OEM: OEMHandler(),
            ConfirmationStatus.COMPLIANCE: ComplianceHandler(),
            ConfirmationStatus.DEPENDENCY: DependencyHandler(),
            ConfirmationStatus.CONTRACT:ContractHandler(),
            ConfirmationStatus.CREDENTIAL: CredentialHandler(),
            ConfirmationStatus.SPECIAL_CHECK: SpecialCheckHandler(),
        }
        
        self.current_state = ConfirmationStatus.OEM

    def process(self, context: Dict[str, Any]) -> Optional[ConfirmationStatus]:
        """处理当前状态并转移到下一个状态"""
        handler = self.handlers.get(self.current_state)
        if not handler:
            return None
        
        # 执行状态处理并获取事件
        event = handler.handle(context)
        
        # 根据状态转移表确定下一个状态
        if event and self.current_state in self.transition_table:
            next_state = self.transition_table[self.current_state].get(event)
            if next_state:
                self.current_state = next_state
        
        return self.current_state


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