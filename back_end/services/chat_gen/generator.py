from back_end.items_utils.item_types import State
from back_end.services.state_handlers.base_handler import ChapterGeneration
from typing import Tuple, Dict, Any
from utils.string_to_markdown import MarkdownDocumentBuilder
from log_config import get_logger

class ChatGenerator:

    def __init__(self, handler: ChapterGeneration):
        self.handler = handler
        self.logger = get_logger(__name__)

    def generate_content(self, content:Dict) -> Tuple[str, bool]:
        result = self._content_generation(content)
        if result:
            return "All subtitles have been finished", True
        else:
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
        subtitle_handlers = self.handler.nested_handlers.get(item_key, [])
        
        # 找到当前需要处理的子标题
        for handler in subtitle_handlers:
            if not getattr(handler, 'content_confirmed', False):
                # 调用子标题的内容生成
                context['current_item_idx'] = self.handler.current_item_index
                content = handler._generate_content(context)
                
                # 存储内容到shared
                subtitle_key = f"content_{item_key}_{handler.__class__.__name__}"
                shared[subtitle_key] = content
                
                self.logger.info(f"Generated content for {item_key} - {handler.__class__.__name__}")
                return content
        
        return True

    def _aggregate_content(self, context: Dict[str, Any]) -> str:
        """
        内容合成方法 - 把每个项目的子章节内容组合起来并返回markdown字符串
        返回: 聚合后的markdown内容字符串
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