import json
from typing import Dict, Any, Tuple
from enum import Enum
from .chat_manager import ChatManager
from .item_types import ItemType, get_item_type_from_value, get_processing_type_from_status
from back_end.services.chat_flow import WorkflowContext, ConfirmationStatus
from utils.tools import get_strict_json, get_processing_type_from_shared
from log_config import get_logger

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
        # 状态处理器映射表
        self.status_handlers = {
            ConfirmationStatus.SPECIAL_CHECK.value: self._handle_special_check,
            ConfirmationStatus.OEM.value: self._handle_oem,
            ConfirmationStatus.DEPENDENCY.value: self._handle_dependency,
            ConfirmationStatus.COMPLIANCE.value: self._handle_compliance,
            ConfirmationStatus.CONTRACT.value: self._handle_contract,
            ConfirmationStatus.CREDENTIAL.value: self._handle_credential,
        }
        self.chat_flow = chat_flow
        self.chat_manager = ChatManager()
        self.bot = None
    
    def process_user_input(self, shared: Dict[str, Any], user_input: str, status: str) -> Tuple[bool, Dict[str, Any], str]:
        """
        处理用户输入，优先检查大状态变化，然后处理嵌套逻辑
        """
        tags = [status]
        response = get_strict_json(self.bot, user_input,tags=tags)
        result = response.get('result')
        reply = self._extract_reply(response)
        
        # 更新 shared 中的 bot
        shared['riskBot'] = self.bot

        # 1. 优先检查大状态变化
        content = {'shared': shared, 'status': result}
        updated_status = self.chat_flow.process(content).value
        
        logger.info('chat_service.process_user_input: Current status: %s, Updated status: %s', status, updated_status)
        
        final_status, updated_shared, reply = self._status_check(shared, updated_status, status, result,reply)

        return final_status, updated_shared, reply

    def _status_check(self, shared, updated_status, status, result, reply):
        """
        处理状态变化的逻辑
        返回: (最终状态, 更新后的shared, 消息列表)
        """
        # 统一日志记录
        self._log_status_info(shared, status, updated_status)
        
        # 状态发生变化
        if updated_status != status:
            return self._process_status_change(shared, status, updated_status)
        
        # 状态未变化，检查是否需要嵌套处理
        if self._has_nested_logic(status):
            return self._handle_nested_logic(shared, status, result, reply)
        
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

    def _process_status_change(self, shared, old_status, new_status):
        """处理状态变化"""
        # 更新shared中的processing_type
        processing_type = get_processing_type_from_status(new_status)
        shared['processing_type'] = processing_type
        
        # 获取基础指导语
        messages = [self.get_instructions(new_status)]
        
        # 检查是否需要添加嵌套项的指导语
        if self._needs_first_item_instruction(new_status):
            logger.info('process_status_change: we need to get the instruction for the first item: %s', new_status)
            item_type = get_item_type_from_value(processing_type)
            updated_shared, instruction, _ = self.chat_manager.handle_item_action(
                shared, item_type, 'next', self.bot
            )
            messages.append(instruction)
            return new_status, updated_shared, messages
        
        return new_status, shared, messages

    def _needs_first_item_instruction(self, status):
        """判断是否需要返回第一个item的指导语"""
        return self._has_nested_logic(status) and self._has_compulsory_logic(status)

    def _ensure_list(self, message):
        """确保返回值是列表格式"""
        return message if isinstance(message, list) else [message]

    def _has_nested_logic(self, status: str) -> bool:
        """判断当前状态是否有嵌套逻辑"""
        nested_states = {
            ConfirmationStatus.DEPENDENCY.value,  # 有 components 需要确认
            ConfirmationStatus.COMPLIANCE.value,  # 有 licenses 需要确认
            ConfirmationStatus.CREDENTIAL.value,  # 有 components 需要确认
            ConfirmationStatus.SPECIAL_CHECK.value, # 有license 需要确认
            # 根据需要添加其他有嵌套逻辑的状态
        }
        return status in nested_states
    
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

        handler = self.status_handlers.get(status,self._handle_compliance)
        message = handler()

        return message

    def _handle_contract(self) -> str:
        """处理合同状态"""
        prompt = self.bot.langfuse.get_prompt("bot/Contract").prompt
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', '请提供合同信息')
    
    def _handle_special_check(self) -> str:
        """处理预检查状态"""
        prompt = self.bot.langfuse.get_prompt("bot/SpecialCheck").prompt
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', '请进行特殊检查')
    
    def _handle_oem(self) -> str:
        """处理OEM状态"""
        prompt = self.bot.langfuse.get_prompt("bot/OEM").prompt
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', '请确认OEM信息')
    
    def _handle_credential(self) -> str:
        """处理授权许可证状态"""
        prompt = self.bot.langfuse.get_prompt("bot/Credential").prompt
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', '请确认授权信息')

    def _handle_dependency(self) -> str:
        """处理依赖状态"""
        prompt = self.bot.langfuse.get_prompt("bot/Dependecy").prompt
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', '请确认依赖关系')
    
    def _handle_compliance(self) -> str:
        """处理合规性状态"""
        prompt = self.bot.langfuse.get_prompt("bot/Compliance").prompt
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', '请确认合规信息')

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
        risk_bot = shared.get("riskBot")
        if not risk_bot:
            raise ValueError("共享数据中未找到RiskBot")
        
        self.bot = risk_bot
        logger.info('we have found risk bot when initializing the chat service!')

        # 这里只需要保证shared里面有一个current值就可以了，具体的在检查许可证和组件的时候再调用
        updated_shared, _ = self.chat_manager.initialize_session(shared)
        
        return updated_shared