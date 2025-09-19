from back_end.services.state_handlers.content_handler import ChapterGeneration, SimpleChapterGeneration
from typing import Tuple, Dict, Any
from utils.string_to_markdown import MarkdownDocumentBuilder
from log_config import get_logger

class ChatGenerator:

    def __init__(self, handler: ChapterGeneration):
        self.handler = handler
        self.logger = get_logger(__name__)

    def load_new_handler(self, handler: ChapterGeneration):
        """
        更新当前使用的章节生成处理器
        
        Args:
            handler: 新的ChapterGeneration处理器实例
        """
        if handler is None:
            self.logger.warning("尝试加载None处理器，操作被忽略")
            return
            
        if not isinstance(handler, ChapterGeneration):
            self.logger.warning(f"处理器类型不匹配，期望ChapterGeneration，得到{handler.__class__.__name__}")
            return
            
        self.logger.info(f"更新处理器: {self.handler.__class__.__name__} -> {handler.__class__.__name__}")
        self.handler = handler

    def generate_content(self, content:Dict) -> Tuple[str, bool]:

        if isinstance(self.handler, SimpleChapterGeneration):
            result = self._simple_content_generation(content)
        else:
            result = self._content_generation(content)

        # 根据_content_generation的返回值类型判断情况
        if result is True:  # 所有子标题都已完成
            return "All subtitles have been finished", True
        elif result is False:  # 没有找到处理器
            return "No handlers found for current item", False
        else:  # 正常生成了内容
            return result, False
        
    def _content_generation(self, context: Dict[str, Any]) -> str:
        """
        内容生成方法 - Chat_service只通过handler._content_generation调用
        通过shared里维护的当前item序号和子章节标题确定调用哪个子标题的状态生成器
        """
        shared = context.get('shared', {})
        
        if self.handler.current_item_index >= len(self.handler.items):
            return True
        
        current_item = self.handler.items[self.handler.current_item_index]
        item_key = current_item.get('id', current_item.get('title', f'item_{self.handler.current_item_index}'))
        
        # 获取当前项目的子标题处理器列表
        subtitle_handlers = self.handler.nested_handlers.get(self.handler.current_item_index, [])
        
        # 找到当前需要处理的子标题
        for handler in subtitle_handlers:
            if not getattr(handler, 'content_confirmed', False):
                # 调用子标题的内容生成
                shared['current_item_idx'] = self.handler.current_item_index
                content = handler._generate_content(shared)
                if content:
                    handler.content_generated = True
                
                # 存储内容到shared
                subtitle_key = f"content_{item_key}_{handler.handler.__class__.__name__}"
                shared[subtitle_key] = content
                
                self.logger.info(f"Generated content for {item_key} - {handler.handler.__class__.__name__}")
                return content
        
        return False
    
    def _simple_content_generation(self, context: Dict[str, Any]) -> str:

        '''内容生成方法，但不使用遍历项目的逻辑'''

        shared = context.get('shared', {})
        
        for handler in self.handler.nested_handlers:
            if not getattr(handler, 'content_confirmed', False):
                content = handler._generate_content(shared)
                if content:
                    handler.content_generated = True

                # 存储内容到shared
                subtitle_key = f"content_{handler.handler.__class__.__name__}"
                shared[subtitle_key] = content
                
                self.logger.info(f"Generated content for {handler.__class__.__name__}")
                return content
        
        return False


    def _aggregate_content(self, context: Dict[str, Any]) -> str:
        """
        内容合成方法 - 把每个项目的子章节内容组合起来并返回markdown字符串
        返回: 聚合后的markdown内容字符串
        应该simple的不会调这个方法
        """
        shared = context.get('shared', {})
        full_chapter_content_builder = MarkdownDocumentBuilder()
        
        for item in self.handler.items:
            item_key = item.get('id', item.get('title', ''))
            item_title = item.get('title', item_key)
            
            # 添加项目标题
            full_chapter_content_builder.add_section(f"## {item_title}")
            
            # 获取该项目的所有子标题内容
            subtitle_handlers = self.handler.nested_handlers.get(item_key, [])
            for handler in subtitle_handlers:
                subtitle_key = f"content_{item_key}_{handler.__class__.__name__}"
                subtitle_content = shared.get(subtitle_key, "")
                
                if subtitle_content:
                    subtitle_title = getattr(handler, 'subtitle_title', handler.__class__.__name__)
                    full_chapter_content_builder.add_section(f"### {subtitle_title}\n\n{subtitle_content}")
        
        # 构建最终内容
        final_content = full_chapter_content_builder.build_document()
        
        # 存储到shared（保留原有逻辑）
        shared[self.handler.chapter_content_key] = final_content
        shared[self.handler.chapter_title_key] = "Generated Chapter"
        
        self.logger.info("Content aggregation completed and stored in markdown format")
        
        # 返回markdown字符串
        return final_content