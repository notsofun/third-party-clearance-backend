import json
from typing import Dict, Any, Tuple, Optional
from .chat_manager import ChatManager
from back_end.items_utils.item_types import get_processing_type_from_status
from back_end.services.chat_flow import WorkflowContext, ConfirmationStatus
from back_end.items_utils.item_utils import get_item_type_from_value
from utils.tools import get_strict_json, get_processing_type_from_shared
from utils.LLM_Analyzer import RiskBot
from log_config import get_logger
from back_end.services.state_handlers.handler_factory import StateHandlerFactory
from back_end.services.state_handlers.base_handler import SubTaskStateHandler,ContentGenerationHandler
logger = get_logger(__name__)  # 每个模块用自己的名称

class ChatService:
    def __init__(self, chat_flow: WorkflowContext):
        """
        初始化聊天服务
        这个类专注处理消息，根据传入状态不同调用不同的方法。
        状态转移和维护、处理，交由workflowContext类
        相当于这里的handle方法，都封装到chat_flow里去了
        然后instructions的方法说是只是instruction，其实可以理解为某种mode，来切换到不同的判断状态
        """
        self.handler_factory = StateHandlerFactory()
        self.chat_flow = chat_flow
        self.chat_manager = ChatManager()
        self.bot = chat_flow.bot
    
    def process_user_input(self, shared: Dict[str, Any], user_input: str, status: str) -> Tuple[bool, Dict[str, Any], str]:
        """
        处理用户输入，优先检查大状态变化，然后处理嵌套逻辑
        """
        tags = [status]
        response = get_strict_json(self.bot, user_input,tags=tags)
        result = response.get('result')
        reply = self._extract_reply(response)
        logger.info("user_input: %s", user_input)
        # 更新 shared 中的 bot
        shared['riskBot'] = self.bot

        # 处理状态特定的逻辑
        handler = self.handler_factory.get_handler(status, self.bot)
        if handler:
            shared = handler.process_special_logic(shared, result)

        # 检查大状态变化
        content = {'shared': shared, 'status': result}
        updated_status = self.chat_flow.process(content).value
        
        logger.info('chat_service.process_user_input: Current status: %s, Updated status: %s', status, updated_status)
        
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
        
        # 状态未变化，检查是否需要嵌套处理
        if isinstance(handler, SubTaskStateHandler):
            return self._handle_nested_logic(shared, status, result, reply)
        
        if isinstance(handler, ContentGenerationHandler):
            content_gen_result = self._handle_content_generation(handler, shared, status, result, reply)
            if content_gen_result:
                self.handler_factory.add_section(status, content_gen_result)
                return content_gen_result
        
        # 默认情况：返回原始回复
        return status, shared, self._ensure_list(reply)

    def _log_status_info(self, shared, current_status, new_status):
        """统一的日志记录"""
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
        context = {
            'shared': shared,
            'user_input': shared.get('user_input', ''),
            'status': result
        }
        event = handler.handle(context)
        
        if event == "GENERATE_CONTENT":
            generated_content = handler._generate_content()
            shared = handler.process_special_logic(shared,content=generated_content)
            confirmation_message = f"Based on the information you proived, I have generated the following content: \n\n{generated_content}\n\n Would you mind telling me if it meets your requirements?"
            
            return status, shared, self._ensure_list(confirmation_message)
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
        }
        return status in compulsory_states

    def _handle_nested_logic(self, shared: Dict[str, Any], status: str, result: str, reply: str) -> Tuple[str, Dict[str, Any], str]:
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
                
        # 检查是否所有项目都已确认完成
        if all_completed:
            logger.info('chat_service.handle_nested: we have finished the checking for this state %s',self.chat_flow.current_state.value )
            # 重新检查大状态转换
            content = {'shared': updated_shared, 'status': 'next'}
            final_status = self.chat_flow.process(content).value
            
            final_status, updated_shared, message = self._status_check(
                updated_shared,
                final_status,
                status,
                result,
                reply
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
        risk_bot = self.chat_flow.bot
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