# state_handlers/base_handler.py
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
            return "GENERATE_CONTENT"
        
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

class SubContentGenerationHandler(SubTaskStateHandler):
    '''
    基本基于subtask这个处理器来实现，需要重新实现初始化+判断完成的方法，这一部分基于content来实现
    '''
    def __init__(self, bot = None):
        '''通过索引实现转移，subtask列表包含的每一个元素是一个statehandler'''
        super.__init__(self)

    def set_bot(self, bot):
        self.bot = bot
        for subtask in self.subtasks:
            if hasattr(subtask,'set_bot'):
                subtask.set_bot(bot)

    def initialize_subtasks(self, context):
        """初始化内容生成子任务"""
        self.subtasks = []
        self.current_subtask_index = 0
        
        # 创建内容生成子任务
        # 示例：添加几个ContentGenerationHandler子类的实例
        content_handlers = self._create_content_handlers()
        for handler in content_handlers:
            if self.bot and hasattr(handler, 'set_bot'):
                handler.set_bot(self.bot)
            self.subtasks.append(handler)

    @abstractmethod
    def _create_content_handlers(self):
        pass

    def is_subtask_completed(self, context: Dict[str, Any], subtask_handler) -> bool:
        """检查指定子任务是否已完成"""
        # 直接使用子任务对象的handle方法
        result = subtask_handler.handle(context)
        return result == State.COMPLETED.value
    
    def get_sub_instructions(self) -> str:
        """获取当前子任务的指导语"""
        current_subtask = self.get_current_subtask_id()
        if current_subtask and hasattr(current_subtask, 'get_instructions'):
            return current_subtask.get_instructions()
        return "请完成当前子任务"
    
    def process_special_logic(self, shared: Dict[str, Any], result: Dict[str, Any]=None, content:str = None) -> Dict[str, Any]:
        """处理当前子任务的特殊逻辑"""
        current_subtask = self.get_current_subtask_id()
        if current_subtask and hasattr(current_subtask, 'process_special_logic'):
            return current_subtask.process_special_logic(shared, result, content)
        return shared

    def _save_to_markdown(self, md:MarkdownDocumentBuilder, content:str) -> None:
        """Propagate save to markdown to current subtask if it supports it."""
        current_subtask = self.get_current_subtask_id()
        if current_subtask and hasattr(current_subtask, '_save_to_markdown'):
            current_subtask._save_to_markdown(md, content)
        else:
            pass

class ChapterGeneration(SubTaskStateHandler):
    """
    章节生成处理器 - 双层嵌套（大状态嵌套组件嵌套子标题）
    
    Chat_service 进入此大状态后分为两部分：
    1. 调用内容生成函数
    2. 调用状态流转方法
    
    参数:
    - item_list_key: str, shared字典中存储组件列表的键名
    - subtask_factory: Callable[[Any, Any], Any], 工厂函数，为每个组件创建子任务处理器
    - subcontent_factory: Callable[[Any, Any, Any], Any], 工厂函数，为每个子标题创建内容生成器
    - chapter_title_key: str, 最终章节标题的键名
    - chapter_content_key: str, 最终章节内容的键名
    """

    def __init__(self, bot = None, item_list_key : str = None,
                subtask_factory: Callable[[Any,Any], Any] = None,
                subcontent_factory: Callable[[Any, Any, Any], Any] = None,
                chapter_title_key: str = "generated_chapter_title",
                chapter_content_key: str = "generated_chapter_content"):
        super().__init__(bot)
        if item_list_key is None:
            self.logger.error("item_list_key must be provided for ChapterGenerationHandler")
        if subtask_factory is None:
            self.logger.error("content_handler_factory must be provided for ChapterGenerationHandler")
        if subcontent_factory is None:
            self.logger.error("subcontent_factory must be provided for ChapterGeneration")

        self.item_list_key = item_list_key
        self.subtask_factory = subtask_factory
        self.subcontent_factory = subcontent_factory
        self.chapter_title_key = chapter_title_key
        self.chapter_content_key = chapter_content_key
        
        # 嵌套字典：{item_key: [子标题生成实例列表]}
        self.nested_handlers = {}
        # 当前处理的项目索引
        self.current_item_index = 0
        # 项目列表
        self.items = []

    def initialize_subtasks(self, context: Dict[str, Any]):
        """
        初始化嵌套字典结构，遍历shared中的item_key获取项目数量，
        为每个项目创建对应的子标题生成实例列表
        """
        shared = context.get('shared', {})
        self.items = shared.get(self.item_list_key, [])
        
        self.nested_handlers = {}
        self.current_item_index = 0
        
        for item_data in self.items:
            item_key = item_data.get('id', item_data.get('title', f'item_{len(self.nested_handlers)}'))
            
            subtitle_handlers = self._create_content_handlers()
            
            self.nested_handlers[item_key] = subtitle_handlers
            self.logger.info(f"Initialized {len(subtitle_handlers)} subtitle handlers for item: {item_key}")

        if not self.nested_handlers:
            self.logger.warning(f"No items found for key '{self.item_list_key}'. Chapter will be empty.")

    @abstractmethod
    def _create_content_handlers(self):
        pass

    def _content_generation(self, context: Dict[str, Any]) -> str:
        """
        内容生成方法 - Chat_service只通过handler._content_generation调用
        通过shared里维护的当前item序号和子章节标题确定调用哪个子标题的状态生成器
        """
        shared = context.get('shared', {})
        
        if self.current_item_index >= len(self.items):
            return "所有内容已生成完成"
        
        current_item = self.items[self.current_item_index]
        item_key = current_item.get('id', current_item.get('title', f'item_{self.current_item_index}'))
        
        # 获取当前项目的子标题处理器列表
        subtitle_handlers = self.nested_handlers.get(item_key, [])
        
        # 找到当前需要处理的子标题
        for handler in subtitle_handlers:
            if not getattr(handler, 'content_confirmed', False):
                # 调用子标题的内容生成
                content = handler._generate_content(context)
                
                # 存储内容到shared
                subtitle_key = f"content_{item_key}_{handler.__class__.__name__}"
                shared[subtitle_key] = content
                
                self.logger.info(f"Generated content for {item_key} - {handler.__class__.__name__}")
                return content
        
        return "当前项目所有子标题已完成"

    def _state_transition(self, context: Dict[str, Any]) -> str:
        """
        状态流转方法 - 基于subtask和subcontent维护嵌套字典
        每传一个next进来，就把当前处理项目的对应子章节标为content_confirmed
        """
        if self.current_item_index >= len(self.items):
            return State.COMPLETED.value
        
        current_item = self.items[self.current_item_index]
        item_key = current_item.get('id', current_item.get('title', f'item_{self.current_item_index}'))
        
        # 获取当前项目的子标题处理器列表
        subtitle_handlers = self.nested_handlers.get(item_key, [])
        
        # 标记当前处理的子章节为已确认
        for handler in subtitle_handlers:
            if not getattr(handler, 'content_confirmed', False):
                handler.content_confirmed = True
                self.logger.info(f"Marked content_confirmed for {item_key} - {handler.__class__.__name__}")
                break
        
        # 检查当前项目的所有子项目是否都已确认完成
        all_confirmed = all(getattr(handler, 'content_confirmed', False) for handler in subtitle_handlers)
        
        if all_confirmed:
            self.logger.info(f"All subtitles completed for item: {item_key}")
            self.current_item_index += 1
            
            # 检查是否所有项目都已完成
            if self.current_item_index >= len(self.items):
                self.logger.info("All items completed")
                return State.COMPLETED.value
        
        return State.INPROGRESS.value

    def _aggregate_content(self, context: Dict[str, Any]) -> str:
        """
        内容合成方法 - 把每个项目的子章节内容组合起来并返回markdown字符串
        返回: 聚合后的markdown内容字符串
        """
        shared = context.get('shared', {})
        full_chapter_content_builder = MarkdownDocumentBuilder()
        
        for item in self.items:
            item_key = item.get('id', item.get('title', ''))
            item_title = item.get('title', item_key)
            
            # 添加项目标题
            full_chapter_content_builder.add_section(f"## {item_title}")
            
            # 获取该项目的所有子标题内容
            subtitle_handlers = self.nested_handlers.get(item_key, [])
            for handler in subtitle_handlers:
                subtitle_key = f"content_{item_key}_{handler.__class__.__name__}"
                subtitle_content = shared.get(subtitle_key, "")
                
                if subtitle_content:
                    subtitle_title = getattr(handler, 'subtitle_title', handler.__class__.__name__)
                    full_chapter_content_builder.add_section(f"### {subtitle_title}\n\n{subtitle_content}")
        
        # 构建最终内容
        final_content = full_chapter_content_builder.build_document()
        
        # 存储到shared（保留原有逻辑）
        shared[self.chapter_content_key] = final_content
        shared[self.chapter_title_key] = "Generated Chapter"
        
        self.logger.info("Content aggregation completed and stored in markdown format")
        
        # 返回markdown字符串
        return final_content

    def get_aggregated_content(self, context: Dict[str, Any]) -> str:
        """
        公共方法：获取聚合后的内容
        供外部调用，返回最终的markdown内容
        """
        return self._aggregate_content(context)

    def handle(self, context: Dict[str, Any]) -> str:
        """
        处理章节生成状态
        Chat_service进入此大状态后，分为内容生成和状态流转两部分
        """
        # 如果还未初始化，先初始化
        if not hasattr(self, 'nested_handlers') or not self.nested_handlers:
            self.initialize_subtasks(context)
        
        # 执行状态流转
        state_result = self._state_transition(context)
        
        # 如果状态流转返回完成，则执行内容合成
        if state_result == State.COMPLETED.value:
            self._aggregate_content(context)
            return State.COMPLETED.value
        
        return State.INPROGRESS.value

    def process_special_logic(self, shared: Dict[str, Any], result: Dict[str, Any] = None, content: str = None) -> Dict[str, Any]:
        """
        处理特殊逻辑，传递给当前处理的子标题处理器
        """
        if self.current_item_index < len(self.items):
            current_item = self.items[self.current_item_index]
            item_key = current_item.get('id', current_item.get('title', f'item_{self.current_item_index}'))
            subtitle_handlers = self.nested_handlers.get(item_key, [])
            
            # 找到当前正在处理的子标题处理器
            for handler in subtitle_handlers:
                if not getattr(handler, 'content_confirmed', False):
                    if hasattr(handler, 'process_special_logic'):
                        shared = handler.process_special_logic(shared, result, content)
                    break
        
        return shared

    def get_instructions(self) -> str:
        """
        获取当前状态的指导语
        """
        if self.current_item_index < len(self.items):
            current_item = self.items[self.current_item_index]
            item_key = current_item.get('id', current_item.get('title', f'item_{self.current_item_index}'))
            subtitle_handlers = self.nested_handlers.get(item_key, [])
            
            # 获取当前子标题处理器的指导语
            for handler in subtitle_handlers:
                if not getattr(handler, 'content_confirmed', False):
                    if hasattr(handler, 'get_instructions'):
                        return handler.get_instructions()
                    break
            
            return f"正在处理项目: {current_item.get('title', item_key)}"
        
        return "正在生成章节内容，请稍候。"
