from .base_handler import SubTaskStateHandler, ContentGenerationHandler
from utils.tools import get_strict_json
from log_config import get_logger
from back_end.items_utils.item_types import ItemType
from back_end.items_utils.item_utils import get_item_type_from_string, get_type_config
from typing import Dict, Any
from back_end.items_utils.item_utils import is_item_completed, get_items_from_context

logger = get_logger(__name__)

class SpecialCheckHandler(SubTaskStateHandler):

    def get_instructions(self) -> str:
        """处理预检查状态"""
        prompt = self.bot.langfuse.get_prompt("bot/SpecialCheck").prompt
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', '请进行特殊检查')
    
    def initialize_subtasks(self, context: Dict[str, Any]):
        """初始化待确认许可证子任务"""
        licenses = get_items_from_context(context,ItemType.SPECIALCHECK)
        # 以许可证ID作为子任务标识，这里lic是一个result = {'licName': lTitle,'category': category}字典
        self.subtasks = [lic.get("licName", f"comp_{idx}") for idx, lic in enumerate(licenses)]
        logger.info(f"chat_flow.SpeicalCheck: 依赖处理: 初始化了 {len(self.subtasks)} 个组件子任务")
    
    def is_subtask_completed(self, context: Dict[str, Any], subtask_id: str) -> bool:
        """检查组件是否已确认"""
        licenses = get_items_from_context(context,ItemType.SPECIALCHECK)
        for lic in licenses:
            if lic.get("licName") == subtask_id:
                return is_item_completed(lic)
        return False

class MainLicenseHandler(SubTaskStateHandler):

    def get_instructions(self):
        '''处理选择主许可证'''
        prompt = self.bot.langfuse.get_prompt("bot/MainLicense").prompt
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', 'Please select one main license among them.')
    
    def process_special_logic(self, shared, result = None, content = None):
        processing_type = shared['processing_type']
        current_type = get_item_type_from_string(processing_type)
        config = get_type_config(current_type)
        shared[config['items_key']][shared[config['current_key']]][current_type.value] = content
        return shared

    def initialize_subtasks(self, context: Dict[str, Any]):
        """初始化待确认组件子任务"""
        components = get_items_from_context(context, ItemType.MAINLICENSE)
        # 以组件ID作为子任务标识
        self.subtasks = [comp.get("compName", f"comp_{idx}") for idx, comp in enumerate(components)]
        logger.info(f"chat_flow.CredentialCheck: 依赖处理: 初始化了 {len(self.subtasks)} 个组件子任务")
    
    def is_subtask_completed(self, context: Dict[str, Any], subtask_id: str) -> bool:
        """检查组件是否已确认"""
        components = get_items_from_context(context, ItemType.MAINLICENSE)
        for comp in components:
            if comp.get("compName") == subtask_id:
                return is_item_completed(comp)
        return False

class CredentialHandler(SubTaskStateHandler):
    
    def get_instructions(self) -> str:
        """处理授权许可证状态"""
        prompt = self.bot.langfuse.get_prompt("bot/Credential").prompt
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', '请确认授权信息')
    
    def initialize_subtasks(self, context: Dict[str, Any]):
        """初始化待确认组件子任务"""
        components = get_items_from_context(context, ItemType.CREDENTIAL)
        # 以组件ID作为子任务标识
        self.subtasks = [comp.get("compName", f"comp_{idx}") for idx, comp in enumerate(components)]
        logger.info(f"chat_flow.CredentialCheck: 依赖处理: 初始化了 {len(self.subtasks)} 个组件子任务")
    
    def is_subtask_completed(self, context: Dict[str, Any], subtask_id: str) -> bool:
        """检查组件是否已确认"""
        components = get_items_from_context(context, ItemType.CREDENTIAL)
        for comp in components:
            if comp.get("compName") == subtask_id:
                return is_item_completed(comp)
        return False

class DependencyHandler(SubTaskStateHandler):

    def get_instructions(self) -> str:
        """处理依赖状态"""
        prompt = self.bot.langfuse.get_prompt("bot/Dependecy").prompt
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', '请确认依赖关系')
    def initialize_subtasks(self, context: Dict[str, Any]):
        """初始化待确认组件子任务"""
        components = get_items_from_context(context, ItemType.COMPONENT)
        # 以组件ID作为子任务标识
        self.subtasks = [comp.get("compName", f"comp_{idx}") for idx, comp in enumerate(components)]
        logger.info(f"chat_flow.DependencyCheck: 依赖处理: 初始化了 {len(self.subtasks)} 个组件子任务")
    
    def is_subtask_completed(self, context: Dict[str, Any], subtask_id: str) -> bool:
        """检查组件是否已确认"""
        components = get_items_from_context(context, ItemType.COMPONENT)
        for comp in components:
            if comp.get("compName") == subtask_id:
                return is_item_completed(comp)
        return False
    
class ComplianceHandler(SubTaskStateHandler):

    def get_instructions(self) -> str:
        """处理合规性状态"""
        prompt = self.bot.langfuse.get_prompt("bot/Compliance").prompt
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', '请确认合规信息')
    
    def initialize_subtasks(self, context: Dict[str, Any]):
        """初始化待确认组件子任务"""
        licenses = get_items_from_context(context, ItemType.LICENSE)
        # 以组件ID作为子任务标识
        self.subtasks = [lic.get("title", f"lic_{idx}") for idx, lic in enumerate(licenses)]
        logger.info(f"chat_flow.LicenseCheck: 依赖处理: 初始化了 {len(self.subtasks)} 个组件子任务")
    
    def is_subtask_completed(self, context: Dict[str, Any], subtask_id: str) -> bool:
        """检查组件是否已确认"""
        licenses = get_items_from_context(context, ItemType.LICENSE)
        for lic in licenses:
            if lic.get("title") == subtask_id:
                return is_item_completed(lic)
        return False