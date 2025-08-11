import logging
from typing import Dict, Any, Tuple, Optional, Union, Callable
from enum import Enum
from .chat_manager import ChatManager
from .item_types import ItemType, ItemStatus, State
from back_end.services.chat_flow import WorkflowContext, ConfirmationStatus, StateHandler
from utils.tools import get_strict_json, find_key_by_value, get_strict_string

logging.getLogger('langchain').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

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
        # 第一个说yes，要检查，会给到next，当前大状态在toDependency
        content = {'shared': shared, 'status': result}
        # updated也是toDependency
        updated_status = self.chat_flow.process(content).value
        
        logger.info('Current status: %s, Updated status: %s', status, updated_status)
        
        final_status, updated_shared, reply = self._status_check(shared, updated_status, status, result,reply, user_input)

        return final_status, updated_shared, reply

    def _status_check(self, shared, updated_status, status, result, reply, user_input):

        '''
        封装这里处理状态变化的逻辑，方便server在处理合同分析时调用
        shared: 统一流转传递数据的字典,
        updated_status: 根据result生成的流转后的状态,
        status: 传入service时的状态,
        result: 模型对于是否继续的判断,
        reply: 模型生成的说明,
        user_input: 用户输入,
        '''

        # 2. 如果大状态发生变化，直接转换到新状态
        if updated_status != status:
            message = self.get_instructions(shared, updated_status)
            logger.info('State transition: %s -> %s', status, updated_status)
            return updated_status, shared, message
        
        # 3. 大状态没有变化，检查当前状态是否需要嵌套处理
        if self._has_nested_logic(status):
            # 处理嵌套逻辑（组件/许可证确认）
            logger.info('now we are handling nested logic...')
            updated_status, updated_shared, message = self._handle_nested_logic(shared, user_input, status, result, reply)
            # 检查特殊标记
            if not message:
                return updated_status, updated_shared, reply
            else:
                # 添加这一行，确保有返回值
                return updated_status, updated_shared, message
        else:
            # 没有嵌套逻辑的状态，直接返回回复
            return status, shared, reply

    def _has_nested_logic(self, status: str) -> bool:
        """判断当前状态是否有嵌套逻辑"""
        nested_states = {
            ConfirmationStatus.DEPENDENCY.value,  # 有 components 需要确认
            ConfirmationStatus.COMPLIANCE.value,  # 有 licenses 需要确认
            ConfirmationStatus.CREDENTIAL.value,  # 有 licenses 需要确认
            # 根据需要添加其他有嵌套逻辑的状态
        }
        return status in nested_states

    def _handle_nested_logic(self, shared: Dict[str, Any], user_input: str, status: str, result: str, reply: str) -> Tuple[str, Dict[str, Any], str]:
        """处理嵌套逻辑（组件/许可证确认）"""
        
        # 确定当前处理的类型
        processing_type = shared.get('processing_type', 'component')
        item_type = ItemType.LICENSE if processing_type == 'license' else ItemType.COMPONENT

        logger.info('now we are handling license or component %s', item_type)

        # 将处理逻辑委托给ChatManager
        updated_shared, message, all_completed = self.chat_manager.handle_item_action(
            shared, item_type, result, self.bot
        )

        logger.warning('we have found this messsage %s', message)

        # 由于组件本身在inprogress，不新返回消息
        if message == "__USE_ORIGINAL_REPLY__":
            return status, updated_shared, reply
                
        # 检查是否所有项目都已确认完成
        if all_completed:
            # 重新检查大状态转换
            content = {'shared': updated_shared, 'status': result}
            final_status = self.chat_flow.process(content).value
            
            if final_status != status:
                message = self.get_instructions(updated_shared, final_status)
                return final_status, updated_shared, message
        
        return status, updated_shared, message

    def _get_next_item_instruction(self, item_type: ItemType, items: list, current_idx: int, shared: Dict[str, Any]) -> str:
        """
        获取下一个项目的指导文字
        
        Args:
            item_type: 项目类型
            items: 项目列表
            current_idx: 当前项目索引
            shared: 共享数据
            
        Returns:
            下一个项目的指导文字
        """
        next_idx = self.chat_manager._find_next_unconfirmed_item(items, current_idx)
        if next_idx is None:
            return "所有项目已确认完毕"
            
        next_item = items[next_idx]

        instruction_data, _ = self._get_item_instuction(item_type, next_item)
        return instruction_data.get('talking', '请确认此项目')

    def _get_item_instuction(self, item_type: ItemType, next_item) -> dict:
        '''
        获取项目指导文字
        '''
        if item_type == ItemType.LICENSE:
            instruction_data = get_strict_json(
                self.bot,
                f"here is the licenseName: {next_item.get('title', '')}, "
                f"CheckedLevel: {next_item.get('CheckedLevel', '')}, and "
                f"Justification: {next_item.get('Justification', '')}"
            )
            item_name = next_item.get('title', 'unknown license')
        else:  # ItemType.COMPONENT
            instruction_data = get_strict_json(
                self.bot,
                f"""Here is the name of the component {next_item.get('compName', '')},
                and it contains dependency of other components, please confirm with user whether add the dependent
                component into the checklist"""
            )
            item_name = next_item.get('compName', 'unknown component')

        return instruction_data, item_name

    def get_instructions(self,shared:Dict[str,Any], status:str) -> Tuple[str,str]:
        """
        用于生成不依赖于用户输入，生成状态变化时的指导性语言
        """

        logger.warning('Now we are in...%s',status)
        handler = self.status_handlers.get(status,self._handle_compliance)
        logger.warning('now we trying to handle %s',handler.__name__)
        message = handler(shared)

        return message

    def _handle_contract(self, shared: Dict[str, Any]) -> str:
        """处理合同状态"""
        prompt = self.bot.langfuse.get_prompt("bot/Contract").prompt
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', '请提供合同信息')
    
    def _handle_special_check(self, shared: Dict[str, Any]) -> str:
        """处理预检查状态"""
        prompt = self.bot.langfuse.get_prompt("bot/SpecialCheck").prompt
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', '请进行特殊检查')
    
    def _handle_oem(self, shared: Dict[str, Any]) -> str:
        """处理OEM状态"""
        prompt = self.bot.langfuse.get_prompt("bot/OEM").prompt
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', '请确认OEM信息')
    
    def _handle_dependency(self, shared: Dict[str, Any]) -> str:
        """处理依赖状态"""
        prompt = self.bot.langfuse.get_prompt("bot/Dependecy").prompt
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', '请确认依赖关系')
    
    def _handle_compliance(self, shared: Dict[str, Any]) -> str:
        """处理合规性状态"""
        processing_type = shared.get("processing_type", "license")
        item_type = ItemType.LICENSE if processing_type == "license" else ItemType.COMPONENT
        
        item_info = self.chat_manager.get_item(shared, item_type)
        if not item_info.valid:
            return item_info.error_message
            
        _, _, current_item = item_info.data
        
        prompt = self.bot.langfuse.get_prompt("bot/Compliance").prompt
        response = get_strict_json(self.bot, prompt + f" For {current_item.get('title', current_item.get('compName', '未命名项目'))}")
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

        # 这里只需要保证shared里面有一个current值就可以了，具体的在检查许可证和组件的时候再调用
        updated_shared, _ = self.chat_manager.initialize_session(shared)
        
        return updated_shared