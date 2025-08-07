import logging
from typing import Dict, Any, Tuple, Optional, Union, Callable
from enum import Enum
from .chat_manager import ChatManager
from .item_types import ItemType, ItemStatus
from back_end.services.chat_flow import WorkflowContext, ConfirmationStatus
from utils.tools import get_strict_json, find_key_by_value, get_strict_string

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
        处理用户输入，更新当前组件的确认状态
        
        注意，其实这里的component是指license
        Args:
            shared: 会话共享数据
            user_input: 用户输入
            status: 目前会话的阶段，决定要采取什么措施
            
        Returns:
            Tuple[is_complete, updated_shared_data, reply_message]
            is_complete: 所有组件是否已全部确认完毕
            updated_shared_data: 更新后的会话数据
            reply_message: 返回给用户的消息

        只负责处理用户后续的每次输入
        """
        
        # 这个处理type和状态是分开的，先处理组件
        processing_type = shared.get('processing_type', 'component')
        # 感觉也很硬编码
        item_type = ItemType.LICENSE if processing_type == 'license' else ItemType.COMPONENT

        # 获取当前物品信息
        item_info = self.chat_manager.get_item(shared, item_type)
        if not item_info.valid:
            return "completed", shared, item_info.error_message
            
        current_idx, items, current_item = item_info.data
        
        response = get_strict_json(self.bot, user_input)

        result = response.get('result')
        reply = self._extract_reply(response)
        # 把这个带有最新上下文的bot传回shared，保证上下文一致
        shared['riskBot'] = self.bot

        # 怎么设计遍历组件和许可证的状态？
        content = {'shared':shared, 'status': result}
        updated_status = self.chat_flow.process(content).value
        logger.info('the new status is:',updated_status)

        # 处理结果
        if updated_status is None:
            # 这个逻辑不对，updated_status会一直在dependency，也不能handle到下一个状态，因为这样就结束了……（
            next_item_instruction = self._get_next_item_instruction(item_type,items,current_idx,shared)
            return self.chat_manager.proceed_to_next_item(items,current_idx,shared,item_type,next_item_instruction)
        if updated_status != status:
            # 状态发生流转，调用instruction方法
            message = self.get_instructions(shared, updated_status)
            logger.info('now we switch to the next state:',updated_status)
            return updated_status, shared, message
        else:
            # 继续当前许可证的确认
            return status, shared, reply # 这里要返回一个to哪一步的结果

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

        logger.warning('Now we are in...',status)
        handler = self.status_handlers.get(status,self._handle_compliance)
        logger.warning('now we trying to handle',handler.__name__)
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
        prompt = self.bot.langfuse.get_prompt("bot/Dependency").prompt
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