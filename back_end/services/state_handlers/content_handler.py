from back_end.services.state_handlers.base_handler import SubTaskStateHandler, ContentGenerationHandler
from back_end.items_utils.item_types import State
from typing import Dict, Any, Tuple, Callable
from abc import ABC, abstractmethod
from utils.string_to_markdown import MarkdownDocumentBuilder
from back_end.services.state_handlers.handler_registry import HandlerRegistry, HandlerStateWrapper

class SubContentGenerationHandler(ContentGenerationHandler):
    '''
    基本基于subtask这个处理器来实现，需要重新实现初始化+判断完成的方法，这一部分基于content来实现
    '''
    def __init__(self, bot = None):
        '''通过索引实现转移，subtask列表包含的每一个元素是一个statehandler'''
        super().__init__(bot)
        self.subtasks = []

    def set_bot(self, bot):
        self.bot = bot
        for subtask in self.subtasks:
            if hasattr(subtask,'set_bot'):
                subtask.set_bot(bot)

    def handle(self, context, wrapper: HandlerStateWrapper):
        '''调用wrapper去修改属性'''
        if self.check_completion(context):
            wrapper.content_confirmed = True
            return True, wrapper
        else:
            return False, wrapper


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
        self.handler_registry = HandlerRegistry()
        super().__init__(bot)

    def initialize_subtasks(self, context: Dict[str, Any]):
        """
        初始化嵌套字典结构，遍历shared中的item_key获取项目数量，
        为每个项目创建对应的子标题生成实例列表
        """
        shared = context.get('shared', {})
        self.items = shared.get(self.item_list_key, [])
        
        self.nested_handlers = {}
        self.current_item_index = 0
        self.current_subhandler_index = 0
        idx = 0
        
        for _ in self.items:
            subtitle_handlers = self._create_content_handlers()
            self.nested_handlers[idx] = subtitle_handlers
            self.logger.info(f"Initialized {len(subtitle_handlers)} subtitle handlers for item: {idx}")
            idx += 1

        if not self.nested_handlers:
            self.logger.warning(f"No items found for key '{self.item_list_key}'. Chapter will be empty.")

    @abstractmethod
    def _create_content_handlers(self):
        pass

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
        subtitle_handlers = self.nested_handlers.get(self.current_item_index, [])
        
        # 子标题是按顺序的，所以找到第一个未确认的子标题就是当前子标题的方法是对的，但是得加上check_completion的逻辑
        for handler_wrapper in subtitle_handlers:
            if not handler_wrapper.content_confirmed:  # 使用包装器的状态
                go, handler_wrapper = handler_wrapper.handler.handle(context, handler_wrapper)
                if go:
                    self.current_subhandler_index += 1
                    handler_class_name = handler_wrapper.handler.__class__.__name__  # 通过handler属性访问实际handler
                    self.logger.info(f"Marked content_confirmed for {item_key} - {handler_class_name}")
                    break
                else:
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

    def is_subtask_completed(self, context, subtask_id):
        return super().is_subtask_completed(context, subtask_id)

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
        
        return state_result

    # 待会改一下，现在这里是不会有subtitle_handlers的列表的
    def process_special_logic(self, shared: Dict[str, Any], result: Dict[str, Any] = None, content: str = None) -> Dict[str, Any]:
        """
        处理特殊逻辑，传递给当前处理的子标题处理器
        """
        if self.current_item_index < len(self.items):
            current_item = self.items[self.current_item_index]
            item_key = current_item.get('id', current_item.get('title', f'item_{self.current_item_index}'))
            subtitle_handlers = self.nested_handlers.get(self.current_item_index, [])
            
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