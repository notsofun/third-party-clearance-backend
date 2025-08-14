from enum import Enum
from typing import Dict, Optional, Any, List, Type
from abc import ABC, abstractmethod
import os
import sys

# 获取当前文件所在目录
current_dir = os.path.dirname(os.path.abspath(__file__))
# 获取父目录（services的父目录）
parent_dir = os.path.dirname(current_dir)
# 获取项目根目录（假设是back_end的父目录）
project_root = os.path.dirname(parent_dir)

# 将项目根目录添加到Python路径
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 然后使用绝对导入
from back_end.services.item_types import ItemStatus, State, ConfirmationStatus, TYPE_CONFIG, ItemType

from log_config import get_logger

logger = get_logger(__name__)  # 每个模块用自己的名称

class StateHandler(ABC):
    """状态处理器抽象基类"""
    @abstractmethod
    def handle(self, context: Dict[str, Any]) -> str:
        """处理当前状态并返回事件标识"""
        pass
    
    def has_subtasks(self) -> bool:
        """是否包含子任务，默认为False"""
        return False

class SimpleStateHandler(StateHandler):
    """简单状态处理器基类 - 没有子任务"""
    def handle(self, context: Dict[str, Any]) -> str:
        """
        处理简单状态 - 根据条件直接判断是否完成
        子类应重写check_completion方法来定义完成条件
        """
        if self.check_completion(context):
            return State.COMPLETED.value
        return State.INPROGRESS.value
    
    @abstractmethod
    def check_completion(self, context: Dict[str, Any]) -> bool:
        """检查状态是否完成"""
        pass

class SubTaskStateHandler(StateHandler):
    """包含子任务的状态处理器基类"""
    def __init__(self):
        self.subtasks = []  # 子任务ID列表
        self.current_subtask_index = 0
    
    def has_subtasks(self) -> bool:
        return True
    
    def initialize_subtasks(self, context: Dict[str, Any]):
        """根据上下文初始化子任务列表"""
        self.subtasks = []
        self.current_subtask_index = 0
        # 子类应重写此方法
    
    def handle(self, context: Dict[str, Any]) -> str:
        """处理包含子任务的状态"""
        # 如果子任务为空，先初始化
        if not self.subtasks:
            self.initialize_subtasks(context)
            
        # 如果没有子任务，直接完成
        if not self.subtasks:
            return State.COMPLETED.value
            
        # 检查所有子任务是否完成
        if self.check_all_subtasks_completed(context):
            return State.COMPLETED.value
            
        # 获取当前子任务状态
        current_subtask = self.get_current_subtask_id()
        if not current_subtask:
            return State.COMPLETED.value
            
        # 检查当前子任务是否完成
        if self.is_subtask_completed(context, current_subtask):
            # 移动到下一个子任务
            self.current_subtask_index += 1
            if self.current_subtask_index >= len(self.subtasks):
                return State.COMPLETED.value
            
        return State.INPROGRESS.value
    
    def get_current_subtask_id(self):
        """获取当前子任务ID"""
        if not self.subtasks or self.current_subtask_index >= len(self.subtasks):
            return None
        return self.subtasks[self.current_subtask_index]
    
    def check_all_subtasks_completed(self, context: Dict[str, Any]) -> bool:
        """检查所有子任务是否已完成"""
        return all(self.is_subtask_completed(context, task_id) for task_id in self.subtasks)
    
    @abstractmethod
    def is_subtask_completed(self, context: Dict[str, Any], subtask_id: Any) -> bool:
        """检查指定子任务是否已完成"""
        pass

# 简单状态处理器示例
class OEMHandler(SimpleStateHandler):
    def check_completion(self, context: Dict[str, Any]) -> bool:
        print("执行OEM处理...")
        status = context.get('status')
        if status == State.NEXT.value:
            return State.COMPLETED
        elif status == State.CONTINUE.value:
            return State.INPROGRESS
        else:
            raise RuntimeError('Model did not determine to go on or continue')

class ComplianceHandler(SubTaskStateHandler):
    def initialize_subtasks(self, context: Dict[str, Any]):
        """初始化待确认组件子任务"""
        licenses = context.get("shared", {}).get(TYPE_CONFIG[ItemType.LICENSE]['items_key'], [])
        # 以组件ID作为子任务标识
        self.subtasks = [lic.get("title", f"lic_{idx}") for idx, lic in enumerate(licenses)]
        logger.info(f"chat_flow.LicenseCheck: 依赖处理: 初始化了 {len(self.subtasks)} 个组件子任务")
    
    def is_subtask_completed(self, context: Dict[str, Any], subtask_id: str) -> bool:
        """检查组件是否已确认"""
        licenses = context.get("shared", {}).get(TYPE_CONFIG[ItemType.LICENSE]['items_key'], [])
        for lic in licenses:
            if lic.get("title") == subtask_id:
                return lic.get("status") == ItemStatus.CONFIRMED.value
        return False



class ContractHandler(SimpleStateHandler):
    def check_completion(self, context: Dict[str, Any]) -> bool:
        print("执行合同检查...")
        status = context.get('status')
        if status == State.NEXT.value:
            return State.COMPLETED
        elif status == State.CONTINUE.value:
            return State.INPROGRESS
        else:
            raise RuntimeError('Model did not determine to go on or continue')

class SpecialCheckHandler(SubTaskStateHandler):
    def initialize_subtasks(self, context: Dict[str, Any]):
        """初始化待确认许可证子任务"""
        licenses = context.get("shared", {}).get(TYPE_CONFIG[ItemType.SPECIALCHECK]['items_key'], [])
        # 以许可证ID作为子任务标识，这里lic是一个result = {'licName': lTitle,'category': category}字典
        self.subtasks = [lic.get("licName", f"comp_{idx}") for idx, lic in enumerate(licenses)]
        logger.info(f"chat_flow.SpeicalCheck: 依赖处理: 初始化了 {len(self.subtasks)} 个组件子任务")
    
    def is_subtask_completed(self, context: Dict[str, Any], subtask_id: str) -> bool:
        """检查组件是否已确认"""
        licenses = context.get("shared", {}).get(TYPE_CONFIG[ItemType.SPECIALCHECK]['items_key'], [])
        for lic in licenses:
            if lic.get("licName") == subtask_id:
                return lic.get("status") == ItemStatus.CONFIRMED.value
        return False

# 子任务状态处理器示例
class DependencyHandler(SubTaskStateHandler):
    def initialize_subtasks(self, context: Dict[str, Any]):
        """初始化待确认组件子任务"""
        components = context.get("shared", {}).get(TYPE_CONFIG[ItemType.COMPONENT]['items_key'], [])
        # 以组件ID作为子任务标识
        self.subtasks = [comp.get("compName", f"comp_{idx}") for idx, comp in enumerate(components)]
        logger.info(f"chat_flow.DependencyCheck: 依赖处理: 初始化了 {len(self.subtasks)} 个组件子任务")
    
    def is_subtask_completed(self, context: Dict[str, Any], subtask_id: str) -> bool:
        """检查组件是否已确认"""
        components = context.get("shared", {}).get(TYPE_CONFIG[ItemType.COMPONENT]['items_key'], [])
        for comp in components:
            if comp.get("compName") == subtask_id:
                return comp.get("status") == ItemStatus.CONFIRMED.value
        return False

class CredentialHandler(SubTaskStateHandler):
    def initialize_subtasks(self, context: Dict[str, Any]):
        """初始化待确认组件子任务"""
        components = context.get("shared", {}).get(TYPE_CONFIG[ItemType.CREDENTIAL]['items_key'], [])
        # 以组件ID作为子任务标识
        self.subtasks = [comp.get("compName", f"comp_{idx}") for idx, comp in enumerate(components)]
        logger.info(f"chat_flow.CredentialCheck: 依赖处理: 初始化了 {len(self.subtasks)} 个组件子任务")
    
    def is_subtask_completed(self, context: Dict[str, Any], subtask_id: str) -> bool:
        """检查组件是否已确认"""
        components = context.get("shared", {}).get(TYPE_CONFIG[ItemType.CREDENTIAL]['items_key'], [])
        for comp in components:
            if comp.get("compName") == subtask_id:
                return comp.get("status") == ItemStatus.CONFIRMED.value
        return False
    
class WorkflowContext:
    """工作流上下文，管理状态和转换"""
    def __init__(self, curren_state=ConfirmationStatus.OEM):
        # 状态转移表
        self.transition_table = {
            ConfirmationStatus.OEM: {
                State.COMPLETED.value: ConfirmationStatus.CONTRACT,
                State.INPROGRESS.value: ConfirmationStatus.OEM
            },
            ConfirmationStatus.COMPLIANCE: {
                State.COMPLETED.value: ConfirmationStatus.COMPLETED,
                State.INPROGRESS.value: ConfirmationStatus.COMPLIANCE
            },
            ConfirmationStatus.CREDENTIAL: {
                State.COMPLETED.value: ConfirmationStatus.SPECIAL_CHECK,
                State.INPROGRESS.value: ConfirmationStatus.CREDENTIAL
            },
            ConfirmationStatus.SPECIAL_CHECK: {
                State.COMPLETED.value: ConfirmationStatus.COMPLIANCE,
                State.INPROGRESS.value: ConfirmationStatus.SPECIAL_CHECK
            },
            ConfirmationStatus.CONTRACT: {
                State.COMPLETED.value: ConfirmationStatus.DEPENDENCY,
                State.INPROGRESS.value: ConfirmationStatus.CONTRACT
            },
            ConfirmationStatus.DEPENDENCY: {
                State.COMPLETED.value: ConfirmationStatus.CREDENTIAL,
                State.INPROGRESS.value: ConfirmationStatus.DEPENDENCY
            },
        }
        
        # 注册状态处理器
        self.handlers = {
            ConfirmationStatus.OEM: OEMHandler(),
            ConfirmationStatus.COMPLIANCE: ComplianceHandler(),
            ConfirmationStatus.DEPENDENCY: DependencyHandler(),
            ConfirmationStatus.CONTRACT: ContractHandler(),
            ConfirmationStatus.CREDENTIAL: CredentialHandler(),
            ConfirmationStatus.SPECIAL_CHECK: SpecialCheckHandler(),
        }
        
        self.current_state = curren_state
        self.initialized_states = set()  # 记录已初始化的状态
    
    def get_current_subtask_info(self, context: Dict[str, Any]) -> Dict:
        """获取当前子任务信息（如果有）"""
        handler = self.handlers.get(self.current_state)
        if not handler or not handler.has_subtasks():
            return {"has_subtasks": False}
            
        # 确保子任务已初始化
        if self.current_state not in self.initialized_states:
            handler.initialize_subtasks(context)
            self.initialized_states.add(self.current_state)
            
        subtask_id = handler.get_current_subtask_id()
        return {
            "has_subtasks": True,
            "current_subtask": subtask_id,
            "subtask_index": handler.current_subtask_index,
            "total_subtasks": len(handler.subtasks)
        }
    
    def process(self, context: Dict[str, Any]) -> Dict:
        """处理当前状态并可能转移到下一个状态"""
        handler = self.handlers.get(self.current_state)
        if not handler:
            return {
                "success": False,
                "error": f"未找到状态处理器: {self.current_state}"
            }
            
        # 如果是子任务处理器，确保已初始化
        if handler.has_subtasks() and self.current_state not in self.initialized_states:
            handler.initialize_subtasks(context)
            self.initialized_states.add(self.current_state)
        
        logger.info(f'chat_flow.process: 处理状态: {self.current_state}')
        
        # 执行状态处理并获取事件
        event = handler.handle(context)
        old_state = self.current_state
        
        # 根据事件和转移表更新状态
        if event and old_state in self.transition_table:
            next_state = self.transition_table[old_state].get(event)
            if next_state and next_state != old_state:
                logger.info(f'chat_flow.process: 状态转移: {old_state} -> {next_state}')
                self.current_state = next_state
                
                # 如果转移到了新状态，重置其子任务（如果有）
                if next_state in self.initialized_states:
                    self.initialized_states.remove(next_state)
        
        # 返回处理结果
        result = {
            "success": True,
            "previous_state": old_state.value,
            "current_state": self.current_state,
            "state_changed": old_state != self.current_state,
            "event": event
        }
        
        # 如果有子任务，添加子任务信息
        subtask_info = self.get_current_subtask_info(context)
        if subtask_info["has_subtasks"]:
            result.update(subtask_info)
            
        return result["current_state"]

# 使用示例
if __name__ == "__main__":
    workflow = WorkflowContext(curren_state= ConfirmationStatus.SPECIAL_CHECK)
    context = {
        'shared': {
            "dependency_required__components": [
                {
                    "compName": "@ngrx/store 17.2.0",
                    "dependency": True,
                    "status": 'confirmed'
                }
            ],
            "credential_required_components" : [
                    {
                        "compName": "@ngrx/store 17.2.0\n                            ⇧",
                        "blockHtml": "<li class=\"release\" id=\"@ngrx/store_17.2.0\" title=\"@ngrx/store 17.2.0\">\n<div class=\"inset\">\n<h3 id=\"h3@ngrx/store_17.2.0\">@ngrx/store 17.2.0\n                            <a class=\"top\" href=\"#releaseHeader\">⇧</a>\n</h3>\n</div>\n\n\n                        Acknowledgements:<br>\n<pre class=\"acknowledgements\">\nDisclaimer of Warranties and Limitation of Liability.\n\na. Unless otherwise separately undertaken by the Licensor, to the extent possible, the Licensor offers the Licensed Material as-is and as-available, and makes no representations or warranties of any kind concerning the Licensed Material, whether express, implied, statutory, or other. This includes, without limitation, warranties of title, merchantability, fitness for a particular purpose, non-infringement, absence of latent or other defects, accuracy, or the presence or absence of errors, whether or not known or discoverable. Where disclaimers of warranties are not allowed in full or in part, this disclaimer may not apply to You.\n\nb. To the extent possible, in no event will the Licensor be liable to You on any legal theory (including, without limitation, negligence) or otherwise for any direct, special, indirect, incidental, consequential, punitive, exemplary, or other losses, costs, expenses, or damages arising out of this Public License or use of the Licensed Material, even if the Licensor has been advised of the possibility of such losses, costs, expenses, or damages. Where a limitation of liability is not allowed in full or in part, this limitation may not apply to You.\n\nc. The disclaimer of warranties and limitation of liability provided above shall be interpreted in a manner that, to the extent possible, most closely approximates an absolute disclaimer and waiver of all liability.\n    </pre>\n\n                    Licenses:<br>\n<ul class=\"licenseEntries\" style=\"list-style-type:none\">\n<li class=\"licenseEntry\" id=\"licenseEntry1\" title=\"Apache-2.0\">\n<a href=\"#licenseTextItem1\">Apache-2.0 (1)</a>\n</li>\n<li class=\"licenseEntry\" id=\"licenseEntry2\" title=\"CC-BY-4.0\">\n<a href=\"#licenseTextItem2\">CC-BY-4.0 (2)</a>\n</li>\n<li class=\"licenseEntry\" id=\"licenseEntry3\" title=\"MIT\">\n<a href=\"#licenseTextItem3\">MIT (3)</a>\n</li>\n</ul>\n<pre class=\"copyrights\">\nCopyright (c) 2017-2020 Nicholas Jamieson and contributors\nCopyright (c) 2015-2018 NgRx.\nCopyright 2009 International Color Consortium\nCopyright (c) 1998 Hewlett-Packard Company\n© Zeno Rocha\nCopyright (c) 2015-2023 Brandon Roberts, Mike Ryan, Victor Savkin, Rob Wormald\nCopyright 2006-2016 Google Inc. All Rights Reserved.\nCopyright Google Inc. All Rights Reserved.\n(c) 2007 Steven Levithan &lt;stevenlevithan.com&gt;\n<h3><a class=\"top\" href=\"#releaseHeader\">⇧</a></h3>\n    </pre>\n</br></br></li>",
                        "sessionId": 11712279331732835480,
                        "status": 'confirmed'
                    }
                ],
            'specialCollections' : [
                    {
                        "licName": "GPL",
                        "category": "GPL",
                        'status': 'confirmed'
                    }
            ]
        },
        'status': 'next'
    }
    
    state = workflow.current_state
    i = 0
    while state:
        print(f"当前状态: {state.value}")
        state = workflow.process(context)
        if state:
            print(f"this it the {i} 次")
            print(f"转移到状态: {state.value}")
        else:
            print(f"this it the {i} 次")
            print("流程结束")

        i += 1

        if i > 5:
            break