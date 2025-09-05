from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Callable
from back_end.items_utils.item_types import State
from log_config import get_logger
from utils.string_to_markdown import MarkdownDocumentBuilder

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
        
    def process_special_logic(self, shared: Dict[str, Any], result: Dict[str, Any]=None, content:str = None) -> Dict[str, Any]:
        """处理特殊逻辑，默认不做任何处理"""
        return shared
    
    def _save_to_markdown(self, md:MarkdownDocumentBuilder, content:str) -> None:
        return None

    @abstractmethod
    def handle(self, context: Dict[str, Any]) -> str:
        """处理当前状态并返回事件标识"""
        pass
    
    def has_subtasks(self) -> bool:
        """是否包含子任务，默认为False"""
        return False
    
    def check_completion(self, context: Dict[str, Any]) -> bool:
        """检查状态是否完成"""
        self.logger.info("Now we are checking...")
        status = context.get('status')
        if status == State.NEXT.value:
            return True
        elif status == State.CONTINUE.value:
            return False
        else:
            return self.logger.error('Model did not determine to go on or continue')

    @property
    def logger(self):
        return get_logger(self.__class__.__name__)
    
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


class SubTaskStateHandler(StateHandler):
    
    """包含子任务的状态处理器基类"""
    def __init__(self, bot = None):
        self.subtasks = []  # 子任务ID列表
        self.nest_handlers = {} # 双层嵌套结构
        self.current_subtask_index = 0
        super().__init__(bot)
    
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

class ContentGenerationHandler(StateHandler):
    """
    Product Clearance Report生成状态处理器基类 - 处理需要用户确认的嵌套状态
    
    工作流程：
    1. 用户输入信息
    2. 保持在当前状态，但返回特殊标记让service层调用生成方法
    3. 展示生成内容给用户确认
    4. 用户确认后才进入下一个状态
    """
    def __init__(self, bot=None):
        super().__init__(bot)
        self.content_generated = False
        self.content_confirmed = False

    def handle(self, context):
        
        if not self.content_generated:
            self.content_generated = True
            return State.GENERATION.value
        
        # 如果已生成内容，检查用户是否确认，相当于两个next来实现这个跳过
        if self.content_generated:
            self.logger.info("we have generated content...")
            if self.check_completion(context):
                # 用户已确认，重置状态并完成
                self.set_nested_state()
                self.logger.info('we have reset the status of completion')
                return State.COMPLETED.value
            else:
                # 用户未确认，继续等待
                return State.INPROGRESS.value
    
    def set_nested_state(self):
        self.content_generated = False
        self.content_confirmed = True

    @abstractmethod
    def _generate_content(self, shared):
        pass

    def _save_to_markdown(self, md:MarkdownDocumentBuilder, content:str) -> None:
        md.add_section(content=content)