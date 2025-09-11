import json
from typing import Dict, Any, Tuple, Optional
from .chat_manager import ChatManager
from back_end.items_utils.item_types import State
from back_end.items_utils.item_types import get_processing_type_from_status
from back_end.services.chat_flow import WorkflowContext, ConfirmationStatus
from back_end.items_utils.item_utils import get_item_type_from_value
from utils.tools import get_strict_json, get_processing_type_from_shared
from utils.LLM_Analyzer import RiskBot
from log_config import get_logger
from back_end.services.state_handlers.handler_factory import StateHandlerFactory
from back_end.services.chat_gen.generator import ChatGenerator
from back_end.services.state_handlers.base_handler import SubTaskStateHandler, ContentGenerationHandler
from back_end.services.state_handlers.content_handler import ChapterGeneration, SimpleChapterGeneration

logger = get_logger(__name__)  # 每个模块用自己的名称

class ChatService:
    def __init__(self):
        """
        初始化聊天服务
        这个类专注处理消息，根据传入状态不同调用不同的方法。
        状态转移和维护、处理，交由workflowContext类
        相当于这里的handle方法，都封装到chat_flow里去了
        然后instructions的方法说是只是instruction，其实可以理解为某种mode，来切换到不同的判断状态
        """
        self.handler_factory = StateHandlerFactory()
        self.chat_flow = WorkflowContext(handlers=self.handler_factory)
        self.chat_manager = ChatManager()
    
    def process_user_input(self, shared: Dict[str, Any], user_input: str, status: str) -> Tuple[bool, Dict[str, Any], str]:
        """
        处理用户输入，优先检查大状态变化，然后处理嵌套逻辑
        """
        tags = [status]
        logger.info("user_input: %s", user_input)
        response = get_strict_json(self.bot, user_input,tags=tags)
        logger.info('chat_service.process_user_input: we have this response %s', response)
        result = response.get('result')
        reply = self._extract_reply(response)
        # 保存当前用户输入，供ChapterGeneration使用
        shared['current_user_input'] = user_input
        shared['riskBot'] = self.bot

        # 处理状态特定的逻辑，其实是只有OEM
        handler = self.handler_factory.get_handler(status, self.bot)
        if handler:
            shared = handler.process_special_logic(shared, result=result)
        # 检查大状态变化
        content = {'shared': shared, 'status': result}
        result_in_flow = self.chat_flow.process(content)
        updated_status = result_in_flow['current_state'].value
        shared['event'] = result_in_flow['event']
        
        logger.info('chat_service.process_user_input: Current status: %s, Updated status: %s', status, updated_status)

        # 调用最新的handler给下方，包含了初始化能力
        handler = self.handler_factory.get_handler(updated_status, self.bot)
        
        final_status, updated_shared, reply = self._status_check(shared, updated_status, status, result,reply, handler)

        return final_status, updated_shared, reply

    def _status_check(self, shared, updated_status, status, result, reply, handler):
        """
        处理状态变化的逻辑
        返回: (最终状态, 更新后的shared, 消息列表)
        """
        # 统一日志记录
        self._log_status_info(shared, status, updated_status)
        
        # 状态发生变化
        if updated_status != status:
            return self._process_status_change(shared, status, updated_status, handler)
        
        if isinstance(handler, SimpleChapterGeneration):
            return self._handle_simple_chapter_generation(shared, status, result, reply, handler)

        # 特殊处理 ChapterGeneration 类
        if isinstance(handler, ChapterGeneration):
            return self._handle_chapter_generation(shared, status, result, reply, handler)
        
        # 状态未变化，检查是否需要嵌套处理
        if isinstance(handler, SubTaskStateHandler):
            return self._handle_nested_logic(shared, status, result, reply, handler)
        
        if isinstance(handler, ContentGenerationHandler):
            status, shared, message, content_gen_result = self._handle_content_generation(handler, shared, status, result, reply)
            if content_gen_result:
                handler.process_special_logic(shared=shared, content=content_gen_result)
                self.handler_factory.add_section(status, content_gen_result)
                return status, shared, message

        # 默认情况：返回原始回复
        return status, shared, self._ensure_list(reply)

    def _log_status_info(self, shared, current_status, new_status):
        """统一的日志记录"""
        # 什么时候初始化的processing_type?
        processing_type = get_processing_type_from_shared(shared)
        item_type = get_item_type_from_value(processing_type)
        logger.info(
            'Status check - Processing type: %s, Item type: %s, Status: %s -> %s',
            processing_type, item_type, current_status, new_status
        )

    def _process_status_change(self, shared, old_status, new_status, handler):
        """处理状态变化"""
        # 更新shared中的processing_type
        processing_type = get_processing_type_from_status(new_status)
        shared['processing_type'] = processing_type
        
        # 检查是否是从ChapterGeneration状态转出，需要聚合内容
        if isinstance(handler, ChapterGeneration) and old_status != new_status and handler.item_list_key is not None:
            self.gen = ChatGenerator(handler=handler)
            logger.info('_process_status_change: ChapterGeneration completed, aggregating content')
            
            # 构建context
            context = {
                'shared': shared,
                'status': old_status
            }
            
            # 调用ChapterGeneration的内容聚合方法
            try:
                aggregated_content = self.gen._aggregate_content(context)
                
                if aggregated_content:
                    # 使用add_section方法添加聚合后的内容
                    self.handler_factory.add_section(old_status, aggregated_content)
                    logger.info('_process_status_change: Aggregated content added to section for status: %s', old_status)
                else:
                    logger.warning('_process_status_change: No aggregated content returned from ChapterGeneration')
                    
            except Exception as e:
                logger.error('_process_status_change: Error during content aggregation: %s', str(e))
        
        # 获取基础指导语
        messages = [self.get_instructions(new_status)]
        
        # 检查是否需要添加嵌套项的指导语
        if self._needs_first_item_instruction(new_status, handler):
            logger.info('process_status_change: we need to get the instruction for the first item: %s', new_status)
            item_type = get_item_type_from_value(processing_type)
            updated_shared, instruction, _ = self.chat_manager.handle_item_action(
                shared, item_type, 'continue', self.bot
            )
            messages.append(instruction)
            return new_status, updated_shared, messages
        
        return new_status, shared, messages

    def _handle_simple_chapter_generation(self, shared: Dict[str, Any], status: str, result: str, reply: str, handler) -> Tuple[str, Dict[str, Any], str]:
        """
        处理 SimpleChapterGeneration 的逻辑
        - 使用简单的列表结构 (nested_handlers 是 list)
        - 不需要 all_completed 判断
        - 走完 nested_handlers 列表就完成
        """
        logger.info('chat_service._handle_simple_chapter_generation: Processing SimpleChapterGeneration')
        
        self.gen = ChatGenerator(handler=handler)
        event = shared.get('event', '')
        
        # 构建context
        content = {
            'shared': shared,
            'user_input': shared.get('user_input', ''),
            'status': result
        }
        
        gen_content = ""
        if event == State.GENERATION.value:
            # 生成内容
            gen_content, _ = self.gen.generate_content(content)  # 忽略all_completed
            
            # 存储到markdown（简单列表结构）
            handlers_list = handler.nested_handlers  # 直接是list
            if handlers_list and handler.current_handler_index < len(handlers_list):
                current_subhandler = handlers_list[handler.current_handler_index].handler.__class__.__name__
                self.handler_factory.md.add_section(gen_content, f'### {current_subhandler}')
            
            # 处理特殊逻辑
            shared = handler.process_special_logic(shared, content=gen_content)
        
        # 检查是否完成：走完整个列表就算完成
        if handler.current_handler_index >= len(handler.nested_handlers):
            logger.info('chat_service._handle_simple_chapter_generation: All subtitle handlers completed')
            
            # 重新检查大状态转换
            content = {'shared': shared, 'status': 'next'}
            result_in_flow = self.chat_flow.process(content)
            final_status = result_in_flow['current_state'].value
            
            # 如果状态发生变化，处理状态变化
            if final_status != status:
                return self._process_status_change(shared, status, final_status, handler)
            
            # 状态未变化，返回完成消息
            completion_message = "Simple chapter generation completed"
            if shared.get(handler.chapter_content_key):
                completion_message += f"\n\nGenerated chapter has been saved."
            
            return status, shared, self._ensure_list(completion_message)
        
        else:
            # 获取当前的指导语（简单列表结构）
            if handler.current_handler_index < len(handler.nested_handlers):
                current_handler_wrapper = handler.nested_handlers[handler.current_handler_index]
                instruction = current_handler_wrapper.handler.get_instructions()
            else:
                instruction = "Processing simple chapter generation..."
            
            messages = [instruction]
                        
            return status, shared, self._ensure_list(messages)

    def _handle_content_generation(self, handler: ContentGenerationHandler, shared: Dict[str, Any],status: str, result: str, reply: str) -> Optional[Tuple[str, Dict[str, Any], str]]:
        """
        处理内容生成逻辑
        
        参数:
        handler - 内容生成处理器
        shared - 共享上下文
        status - 当前状态
        result - 模型返回的结果
        reply - 当前回复
        
        返回:
        如果需要生成内容，返回(状态, 更新后的shared, 新回复)
        否则返回None，表示继续正常流程
        """
        content = {
            'shared': shared,
            'user_input': shared.get('user_input', ''),
            'status': result
        }
        event = shared.get('event')
        
        if event == State.GENERATION.value:
            logger.info(f"now we started generating content with this handler {handler.__class__.__name__}")
            generated_content = handler._generate_content(shared)
            shared = handler.process_special_logic(shared,content=generated_content)
            confirmation_message = f"Based on the information you proived, I have generated the following content: \n\n{generated_content}\n\n Would you mind telling me if it meets your requirements?"
            
            return status, shared, self._ensure_list(confirmation_message), generated_content
        return None

    def _needs_first_item_instruction(self, status, handler):
        """判断是否需要返回第一个item的指导语"""
        return  isinstance(handler, SubTaskStateHandler)and self._has_compulsory_logic(status)

    def _ensure_list(self, message):
        """确保返回值是列表格式"""
        return message if isinstance(message, list) else [message]
    
    def _has_compulsory_logic(self, status: str) -> bool:
        '''处理用户必须经过的节点的逻辑'''
        compulsory_states = {
            ConfirmationStatus.SPECIAL_CHECK.value, # 有license 需要确认
            ConfirmationStatus.COMPLIANCE.value,
            ConfirmationStatus.MAINLICENSE.value,
            ConfirmationStatus.INTERACTION.value,
            ConfirmationStatus.COPYLEFT.value,
        }
        return status in compulsory_states

    def _handle_chapter_generation(self, shared: Dict[str, Any], status: str, result: str, reply: str, handler: ChapterGeneration) -> Tuple[str, Dict[str, Any], str]:
        """
        处理 ChapterGeneration 的特殊逻辑
        Chat_service 进入此大状态后分为两部分：内容生成和状态流转
        """
        logger.info('chat_service._handle_chapter_generation: Processing ChapterGeneration with result: %s', result)
        self.gen = ChatGenerator(handler=handler) # 每次调用时更新
        event = shared.get('event', '')
        # 构建context
        content = {
            'shared': shared,
            'user_input': shared.get('user_input', ''),
            'status': result
        }
        
        if event == State.GENERATION.value:
            # 生成内容
            gen_content, all_completed = self.gen.generate_content(content)
            
            # 存储到markdown（嵌套字典结构）
            handlers_list = handler.nested_handlers.get(handler.current_item_index, [])
            if handlers_list and handler.current_subhandler_index < len(handlers_list):
                current_subhandler = handlers_list[handler.current_subhandler_index].handler.__class__.__name__
                self.handler_factory.md.add_section(gen_content, f'### {current_subhandler}')
            
            # 处理特殊逻辑
            shared = handler.process_special_logic(shared, content=gen_content)

        # 如果章节生成完成，状态流转往下走，为什么continue第一次调用就判断全部完成了？
        if all_completed:
            logger.info('chat_service._handle_chapter_generation: Chapter generation completed')
            
            # 重新检查大状态转换
            content = {'shared': shared, 'status': 'next'}
            result_in_flow = self.chat_flow.process(content)
            final_status = result_in_flow['current_state'].value
            
            # 如果状态发生变化，处理状态变化
            if final_status != status:
                return self._process_status_change(shared, status, final_status, handler)
            
            # 状态未变化，返回完成消息
            completion_message = "Content for current chapter has been generated"
            if shared.get(handler.chapter_content_key):
                completion_message += f"\n\nGenerated chapter has been saved."
            
            return status, shared, self._ensure_list(completion_message)
        
        else:
            # 获取当前的指导语（嵌套字典结构）
            handlers_list = handler.nested_handlers.get(handler.current_item_index, [])
            if handlers_list and handler.current_subhandler_index < len(handlers_list):
                current_handler_wrapper = handlers_list[handler.current_subhandler_index]
                instruction = current_handler_wrapper.handler.get_instructions()
            else:
                instruction = "Processing chapter generation..."
            
            messages = [instruction]
            
            # 如果有生成的内容，也加入消息
            if event == State.GENERATION.value and gen_content:
                messages.append(gen_content)
            
            return status, shared, self._ensure_list(messages)

    def _handle_nested_logic(self, shared: Dict[str, Any], status: str, result: str, reply: str, handler:SubTaskStateHandler) -> Tuple[str, Dict[str, Any], str]:
        """
        处理嵌套逻辑（组件/许可证确认）
        processing_typing只在嵌套逻辑中被读取
        """
        
        # 确定当前处理的类型
        processing_type = get_processing_type_from_shared(shared)
        logger.info('chat_service.handle_nested: now the processing type in shared is: %s', processing_type)
        item_type = get_item_type_from_value(processing_type)

        logger.info('chat_service.handle_nested: now we are handling license or component %s', item_type)

        # 将处理逻辑委托给ChatManager
        updated_shared, message, all_completed = self.chat_manager.handle_item_action(
            shared, item_type, result, self.bot
        )

        with open("currentSharedCredential.json","w", encoding="utf-8" ) as f1:
            json.dump(updated_shared["credential_required_components"],f1,ensure_ascii=False,indent=2)

        logger.warning('chat_service.handle_nested: we have found this messsage %s', message)

        # 由于组件本身在inprogress，不新返回消息
        if message == "__USE_ORIGINAL_REPLY__":
            return status, updated_shared, reply
        
        # 每次更新item的时候调用特殊逻辑
        if handler:
            handler.process_special_logic(updated_shared,content=reply)

        # 检查是否所有项目都已确认完成
        if all_completed:
            logger.info('chat_service.handle_nested: we have finished the checking for this state %s',self.chat_flow.current_state.value )
            # 重新检查大状态转换
            content = {'shared': updated_shared, 'status': 'next'}
            result_in_flow = self.chat_flow.process(content)
            final_status = result_in_flow['current_state'].value
            
            final_status, updated_shared, message = self._status_check(
                updated_shared,
                final_status,
                status,
                result,
                reply,
                handler
            )
            return final_status, updated_shared, message
        
        return status, updated_shared, message

    def get_instructions(self, status:str) -> Tuple[str,str]:
        """
        用于生成不依赖于用户输入，生成状态变化时的指导性语言
        """
        handler = self.handler_factory.get_handler(status, self.bot)
        if handler:
            return handler.get_instructions()

    def _extract_reply(self, result: Any) -> str:
        """从处理结果中提取回复消息"""
        if result is None:
            return "处理结果为空"
        
        try:
            if isinstance(result, dict) and 'talking' in result:
                return result['talking']
            return str(result)
        except Exception as e:
            logger.error(f"提取回复时出错: {e}")
            return "处理回复时出现错误"

    
    def initialize_chat(self, shared: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
        """
        初始化聊天会话，准备需要确认的组件和许可证
        
        Args:
            shared: 共享数据字典
            
        Returns:
            Tuple[更新后的共享数据, 初始消息]
        """

        # 确保风险评估机器人存在
        risk_bot = shared.get('riskBot', None)
        if not risk_bot:
            raise ValueError("共享数据中未找到RiskBot")
        
        self.bot = risk_bot
        logger.info('we have found risk bot when initializing the chat service!')

        # 这里只需要保证shared里面有一个current值就可以了，具体的在检查许可证和组件的时候再调用
        updated_shared, _ = self.chat_manager.initialize_session(shared)
        
        return updated_shared
    
if __name__ == '__main__':

    shared = {}

    chat_flow = WorkflowContext()

    state_factory = StateHandlerFactory()

    chat_service = ChatService(chat_flow)

    bot1 = RiskBot(session_id='trial')

    handler = state_factory.get_handler(ConfirmationStatus.CREDENTIAL.value, bot1)

    shared['riskBot'] = bot1

    chat_service.initialize_chat(shared)
    
    response = handler.get_instructions()

    print(response)
    license1 = {
    "title": "GNU General Public License v2.0 only",
    "originalLevel": "high",
    "CheckedLevel": "high",
    "Justification": "GPL-2.0 is a strong copyleft license: any distribution of derivative works (including statically or dynamically linked binaries) must be licensed as a whole under GPL-2.0, source code must be made available, and sublicensing under more permissive terms is not allowed. These obligations create significant license-compatibility and release requirements for proprietary or mixed-license projects, leading to a high compliance and business risk profile. However, it does not include additional network-service copyleft (like AGPL) or patent retaliation clauses that might elevate it to a “very high” category. Therefore, a \"high\" risk rating is appropriate and is confirmed."
    }

    com1= "Here is the name of the component @ngrx/store 17.2.0\n                            ⇧, and it needs credential from other cooperation. Please confirm with users whether it is credentialized."

    chatting = True

    response1 = bot1._request(com1)

    while chatting:
        user_input = input()
        currResult = bot1._request(user_input)
        if currResult is False:
            chatting = False
            break