# state_handlers/oem_handler.py
from .base_handler import ContentGenerationHandler, SimpleStateHandler, SubTaskStateHandler
from utils.tools import get_strict_json
from log_config import get_logger
from back_end.items_utils.item_types import State, ItemType
from back_end.items_utils.item_utils import get_item_type_from_string, get_type_config
from typing import Dict, Any
from back_end.items_utils.item_utils import is_item_completed, get_items_from_context
from utils.PCR_Generation.component_overview import generate_components_markdown_table
from utils.database.hardDB import HardDB

logger = get_logger(__name__)

class OEMStateHandler(SimpleStateHandler):
    def get_instructions(self) -> str:
        """处理OEM状态"""
        prompt = self.bot.langfuse.get_prompt("bot/OEM").prompt
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', '请确认OEM信息')
    
    def process_special_logic(self, shared, result):
        """OEM状态的特殊处理逻辑"""
        try:
            # 输入验证
            if not isinstance(result, dict):
                logger.warning("OEM handler received invalid result type: %s", type(result))
                return shared
                
            # 使用 get 方法安全地获取值，并记录详细日志
            is_approved = result.get('is_oem_approved')
            logger.info("OEM approval status in result: %s", is_approved)
            
            if is_approved is True:  # 显式检查是否为True
                logger.info("OEM approved, updating shared data")
                shared['is_oem_approved'] = 'approved'
            elif is_approved is False:  # 显式拒绝
                logger.info("OEM explicitly rejected")
                shared['is_oem_approved'] = 'rejected'
            else:
                logger.warning("OEM approval status unclear or missing: %s", is_approved)
                # 可能需要设置一个默认值或特殊状态
                shared['is_oem_approved'] = 'pending'
                
        except Exception as e:
            # 捕获所有异常，确保处理逻辑不会中断整个流程
            logger.error("Error in OEM special logic processing: %s", str(e), exc_info=True)
            
        return shared
class ContractHandler(SimpleStateHandler):

    def get_instructions(self) -> str:
        """处理合同状态"""
        prompt = self.bot.langfuse.get_prompt("bot/Contract").prompt
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', '请提供合同信息')
    
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

class FinalListHandler(SimpleStateHandler):

    def get_instructions(self):
        return 'Now we are going to show you the list of confirmed licenses and components.'
        
class OSSGeneratingHandler(SimpleStateHandler):

    def get_instructions(self):
        return 'Checking for OSS has been finished, now we started generating readme file. Please let me know if you would like to proceed with generating the product clearance report.'
    
class ProductOverviewHandler(ContentGenerationHandler):

    def process_special_logic(self, shared, content = None, result=None):
        if content == None:
            return shared
        else:
            shared['generated_product_overview'] = content
            return shared

    def _generate_content(self, shared):
        prompt = self.bot.langfuse.get_prompt("bot/WriteProductOverview").prompt
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', 'Please check the result for product overview')

    def get_instructions(self):
        prompt = self.bot.langfuse.get_prompt("bot/ProductOverview").prompt
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', 'Please check the result for product overview')
        
class ComponenetOverviewHandler(ContentGenerationHandler):

    def process_special_logic(self, shared, result = None, content = None):
        if content == None:
            return shared
        else:
            shared['generated_component_overview'] = content
            return shared
    
    def _generate_content(self, shared):
        db = HardDB()
        db.load()
        result = generate_components_markdown_table(shared,db)
        return result
    
    def get_instructions(self):
        return 'Now we are generating component overview'

class CommonRulesHandler(ContentGenerationHandler):
    def process_special_logic(self, shared, result = None, content = None):
        if content == None:
            return shared
        else:
            shared['generated_common_rules'] = content
            return shared
    
    
    def _generate_content(self, shared):
        with open('src/doc/common_rules.md','r',encoding='utf-8') as f:
            result = f.read()
        return result
    
    def get_instructions(self):
        return 'Now we are importing common rules.'

class CompletedHandler(SimpleStateHandler):

    def get_instructions(self) -> str:

        return 'We have finished all checking in current session, please reupload a new license info file to start a new session.'