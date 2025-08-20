import unittest
from unittest.mock import MagicMock, patch
from typing import Dict, Any, Tuple
from log_config import configure_logging, get_logger

# 假设这些是您的导入
from back_end.items_utils.item_types import State, ItemType, ConfirmationStatus
from back_end.services.state_handlers.base_handler import StateHandler, SubTaskStateHandler
from back_end.services.state_handlers.object_handler import ContentGenerationHandler, ProductOverviewHandler

# 设置日志
configure_logging()
logger = get_logger(__name__)

class MockBot:
    """模拟Bot类"""
    def __init__(self):
        self.langfuse = MagicMock()
        # 设置模拟的提示返回
        prompt_mock = MagicMock()
        prompt_mock.prompt = "模拟提示内容"
        self.langfuse.get_prompt.return_value = prompt_mock

class MockChatFlow:
    """模拟WorkflowContext类"""
    def __init__(self, initial_state=ConfirmationStatus.OSSGENERATION):
        self.current_state = initial_state
        self.bot = None
    
    def process(self, context):
        """模拟状态处理"""
        status = context.get('status')
        if status == State.COMPLETED.value:
            if self.current_state == ConfirmationStatus.OSSGENERATION:
                self.current_state = ConfirmationStatus.PRODUCTOVERVIEW
                return MagicMock(value=ConfirmationStatus.PRODUCTOVERVIEW.value)
        return MagicMock(value=self.current_state.value)
    
    def set_bot(self, bot):
        self.bot = bot

class MockHandlerFactory:
    """模拟StateHandlerFactory类"""
    def __init__(self):
        self.handlers = {}
        self.handlers[ConfirmationStatus.PRODUCTOVERVIEW] = ProductOverviewHandler
        self.handlers[ConfirmationStatus.OSSGENERATION] = MagicMock()  # 其他处理器不需要实际功能
    
    def get_handler(self, status, bot=None):
        """获取状态处理器"""
        handler_class = self.handlers.get(status)
        if not handler_class:
            return None
        
        handler = handler_class()
        if bot:
            handler.set_bot(bot)
        return handler

class MockChatService:
    """模拟ChatService类"""
    def __init__(self):
        self.bot = MockBot()
        self.chat_flow = MockChatFlow()
        self.handler_factory = MockHandlerFactory()
        self.chat_flow.set_bot(self.bot)
        self.chat_manager = MagicMock()
    
    def get_instructions(self, status):
        """获取状态指导语"""
        handler = self.handler_factory.get_handler(status, self.bot)
        if handler:
            return handler.get_instructions()
        return "默认指导语"
    
    def _extract_reply(self, response):
        """提取回复"""
        return response.get('talking', '默认回复')
    
    def _ensure_list(self, message):
        """确保消息是列表格式"""
        if isinstance(message, list):
            return message
        return [message]
    
    def _needs_first_item_instruction(self, status):
        """检查是否需要第一个项目的指导语"""
        return False
    
    def _log_status_info(self, shared, current_status, new_status):
        """记录状态信息"""
        logger.info(f'Status check - Status: {current_status} -> {new_status}')
    
    def _process_status_change(self, shared, old_status, new_status):
        """处理状态变化"""
        messages = [self.get_instructions(new_status)]
        return new_status, shared, messages
    
    def _handle_nested_logic(self, shared, status, result, reply):
        """处理嵌套逻辑"""
        return status, shared, self._ensure_list(reply)
    
    def _handle_content_generation(self, handler, shared, status, result, reply):
        """处理内容生成逻辑"""
        context = {
            'shared': shared,
            'user_input': shared.get('user_input', ''),
            'status': result
        }
        event = handler.handle(context)
        
        if event == "GENERATE_CONTENT":
            generated_content = handler._generate_content()
            shared = handler.process_special_logic(shared, generated_content)
            confirmation_message = f"Based on the information you provided, I have generated the following content: \n\n{generated_content}\n\n Would you mind telling me if it meets your requirements?"
            
            return status, shared, self._ensure_list(confirmation_message)
        return None
    
    def _status_check(self, shared, updated_status, status, result, reply, handler):
        """处理状态变化的逻辑"""
        # 统一日志记录
        self._log_status_info(shared, status, updated_status)
        
        # 状态发生变化
        if updated_status != status:
            return self._process_status_change(shared, status, updated_status)
        
        # 状态未变化，检查是否需要嵌套处理
        if isinstance(handler, SubTaskStateHandler):
            return self._handle_nested_logic(shared, status, result, reply)
        
        if isinstance(handler, ContentGenerationHandler):
            content_gen_result = self._handle_content_generation(handler, shared, status, result, reply)
            if content_gen_result:
                return content_gen_result
        
        # 默认情况：返回原始回复
        return status, shared, self._ensure_list(reply)
    
    def process_user_input(self, shared: Dict[str, Any], user_input: str, status: str) -> Tuple[bool, Dict[str, Any], str]:
        """处理用户输入"""
        # 模拟get_strict_json的返回
        response = {'result': 'next', 'talking': f'模拟回复: {user_input}'}
        result = response.get('result')
        reply = self._extract_reply(response)
        logger.info(f"user_input: {user_input}")
        
        # 更新shared
        shared['riskBot'] = self.bot
        shared['user_input'] = user_input

        # 处理状态特定的逻辑
        handler = self.handler_factory.get_handler(status, self.bot)
        if handler:
            shared = handler.process_special_logic(shared, result)

        # 检查大状态变化
        content = {'shared': shared, 'status': result}
        updated_status = self.chat_flow.process(content).value
        
        logger.info(f'chat_service.process_user_input: Current status: {status}, Updated status: {updated_status}')
        
        final_status, updated_shared, reply = self._status_check(shared, updated_status, status, result, reply, handler)

        return final_status, updated_shared, reply

def get_strict_json(bot, prompt, tags=None):
    """模拟get_strict_json函数"""
    # 根据不同的提示返回不同的结果
    if "WriteProductOverview" in prompt:
        return {
            'talking': '这是生成的产品概览内容，包含了产品的基本信息、特点和用途。'
        }
    elif "ProductOverview" in prompt:
        return {
            'talking': '请提供产品信息，我将为您生成产品概览。'
        }
    return {
        'result': 'next',
        'talking': f'模拟回复: {prompt}'
    }
class TestProductOverviewHandler(unittest.TestCase):
    """测试ProductOverviewHandler类"""
    
    def setUp(self):
        """设置测试环境"""
        self.chat_service = MockChatService()
        # 设置初始状态为OSSGENERATION
        self.chat_service.chat_flow.current_state = ConfirmationStatus.OSSGENERATION
        self.shared = {
            'product_name': '测试产品',
            'processing_type': 'product_overview'
        }
    
    def test_ossgeneration_to_productoverview(self):
        """测试从OSSGENERATION到PRODUCTOVERVIEW的转换"""
        # 模拟用户输入，触发状态转换
        status = ConfirmationStatus.OSSGENERATION.value
        user_input = "我想生成产品概览报告"
        
        # 处理用户输入
        final_status, updated_shared, reply = self.chat_service.process_user_input(
            self.shared, user_input, status
        )
        
        # 验证状态已转换为PRODUCTOVERVIEW
        self.assertEqual(final_status, ConfirmationStatus.PRODUCTOVERVIEW.value)
        self.assertIn('请提供产品信息', reply[0])  # 应该包含ProductOverviewHandler的指导语
    
    def test_productoverview_content_generation(self):
        """测试ProductOverviewHandler的内容生成功能"""
        # 设置当前状态为PRODUCTOVERVIEW
        self.chat_service.chat_flow.current_state = ConfirmationStatus.PRODUCTOVERVIEW
        status = ConfirmationStatus.PRODUCTOVERVIEW.value
        
        # 第一次输入 - 触发内容生成
        user_input = "这是一个测试产品，用于验证功能"
        final_status, updated_shared, reply = self.chat_service.process_user_input(
            self.shared, user_input, status
        )
        
        # 验证状态未变化，但生成了内容
        self.assertEqual(final_status, status)
        self.assertIn("Based on the information you provided", reply[0])
        self.assertIn("这是生成的产品概览内容", reply[0])
        
        # 第二次输入 - 确认生成的内容
        user_input = "确认，这个内容很好"
        final_status, updated_shared, reply = self.chat_service.process_user_input(
            updated_shared, user_input, status
        )
        
        # 验证状态已完成
        self.assertEqual(final_status, ConfirmationStatus.COMPLETED.value)
    
    def test_productoverview_content_rejection(self):
        """测试拒绝生成的内容"""
        # 设置当前状态为PRODUCTOVERVIEW
        self.chat_service.chat_flow.current_state = ConfirmationStatus.PRODUCTOVERVIEW
        status = ConfirmationStatus.PRODUCTOVERVIEW.value
        
        # 第一次输入 - 触发内容生成
        user_input = "这是一个测试产品，用于验证功能"
        final_status, updated_shared, reply = self.chat_service.process_user_input(
            self.shared, user_input, status
        )
        
        # 验证生成了内容
        self.assertIn("这是生成的产品概览内容", reply[0])
        
        # 修改模拟函数，使其返回拒绝
        with patch('state_handlers.content_generation_handler.ContentGenerationHandler.is_content_confirmed',
                return_value=False), \
            patch('state_handlers.content_generation_handler.ContentGenerationHandler.is_content_rejected',
                return_value=True), \
            patch('state_handlers.content_generation_handler.ContentGenerationHandler.reset_generation_state') as mock_reset:
            
            # 第二次输入 - 拒绝生成的内容
            user_input = "不好，请重新生成"
            final_status, updated_shared, reply = self.chat_service.process_user_input(
                updated_shared, user_input, status
            )
            
            # 验证状态未变化，重置了生成状态
            self.assertEqual(final_status, status)
            mock_reset.assert_called_once()

if __name__ == '__main__':
    unittest.main()