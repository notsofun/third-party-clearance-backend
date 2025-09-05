from .base_handler import SimpleStateHandler, SubTaskStateHandler, ContentGenerationHandler
from .content_handler import ChapterGeneration, SubContentGenerationHandler
from utils.tools import get_strict_json
from log_config import get_logger
from back_end.items_utils.item_types import ItemType, TYPE_CONFIG, ItemStatus
from back_end.items_utils.item_utils import get_item_type_from_string, get_type_config
from typing import Dict, Any
from back_end.items_utils.item_utils import is_item_completed, get_items_from_context
from utils.PCR_Generation.component_overview import generate_components_markdown_table
from utils.database.hardDB import HardDB
from utils.PCR_Generation.obligations import get_license_descriptions, list_to_string
from back_end.services.state_handlers.handler_registry import HandlerStateWrapper

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
    
class ObligationsHandler(ChapterGeneration):

    def __init__(self, bot=None, item_list_key = TYPE_CONFIG[ItemType.PC]['items_key'],
                chapter_title_key = 'Obligations resulting from the use of 3rd party components',
                chapter_content_key = 'Generated Obligations resulting from the use of 3rd party components'):
        super().__init__(bot, item_list_key, chapter_title_key, chapter_content_key)
        
    def get_instructions(self):
        prompt = '''Now switch to confirming mode, you should decide to continue when user is not satisfied with the result or go on when user is satisfied'''
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', 'Please check the result for product overview')
    
    def _create_content_handlers(self):
        """创建handler包装器列表，每个包装器包含共享的handler实例"""
        handlers = []
        handler_classes = [
            LicenseHandler,
            SubObligationsHandler,
            SubRisksHandler,
            CommonRulesHandler,
            AdditionalHandler,
            ImplementationHandler,
            ObligationCombiningHandler,
        ]
        
        for handler_class in handler_classes:
            # 确保每个handler_class都继承自SubContentGenerationHandler
            if not issubclass(handler_class, SubContentGenerationHandler):
                self.logger.warning(f"{handler_class.__name__} 不是SubContentGenerationHandler的子类，可能无法正确管理状态")
            shared_handler = self.handler_registry.get_handler(handler_class)
            # 创建该实例的状态包装器
            handler_wrapper = HandlerStateWrapper(shared_handler)
            handlers.append(handler_wrapper)
        return handlers
    
class LicenseHandler(SubContentGenerationHandler):

    def __init__(self, bot=None):
        super().__init__(bot)
        self.db = HardDB()
        self.db.load()

    def process_special_logic(self, shared, result = None, content = None):
        if content == None:
            return shared
        else:
            shared['Licenses_identified'] = content
            return shared

    def _generate_content(self, shared: Dict):
        current_item_idx = shared.get('current_item_idx', 0)
        components = shared.get(TYPE_CONFIG.get(ItemType.PC)['items_key'], [])
        global_licenses = self.db.find_license_by_component(components[current_item_idx]['compName'], 'global')
        other_licenses = self.db.find_license_by_component(components[current_item_idx]['compName'], other= True)
        global_str = "*Global Licenses:*" + ', '.join(global_licenses)
        other_str = "*Other Licenses:*" + ', '.join(other_licenses)
        return global_str + '\n\n' + other_str
    
    def get_instructions(self):
        return 'Now we have imported the licenses identified from the cli xml.'

class SubObligationsHandler(SubContentGenerationHandler):
    def __init__(self, bot=None):
        super().__init__(bot)
        self.db = HardDB()
        self.db.load()

    def get_instructions(self):
        return 'Now we start importing the obligations for this component'
    
    def _generate_content(self, shared: Dict):
        current_item_idx = shared.get('current_item_idx', 0)
        components = shared.get(TYPE_CONFIG.get(ItemType.PC)['items_key'], [])
        current_comp = components[current_item_idx]
        licenses = self.db.get_unique_licenses(current_comp['compName'])
        tables = shared['ParsedPCR']['tables'][13]['data']
        obligations = get_license_descriptions(licenses, tables)
        final_str = list_to_string(obligations)
        return final_str
    
    def process_special_logic(self, shared, result = None, content = None):
        if content == None:
            return shared
        else:
            shared['SubObligations'] = content
            return shared
    
class SubRisksHandler(SubContentGenerationHandler):

    def __init__(self, bot=None):
        super().__init__(bot)
        self.db = HardDB()
        self.db.load()

    def get_instructions(self):

        return "Now we start importing the risks for this component"
    
    def _generate_content(self, shared: Dict):
        current_item_idx = shared.get('current_item_idx', 0)
        components = shared.get(TYPE_CONFIG.get(ItemType.PC)['items_key'], [])
        current_comp = components[current_item_idx]
        licenses = self.db.get_unique_licenses(current_comp['compName'])
        tables = shared['ParsedPCR']['tables'][1]['data']
        risks = get_license_descriptions(licenses, tables, 'License section reference and short Description')
        final_str = list_to_string(risks)
        return final_str
    
    def process_special_logic(self, shared, result = None, content = None):
        if content == None:
            return shared
        else:
            shared['SubRisk'] = content
            return shared
        
class CommonRulesHandler(SubContentGenerationHandler):
    def __init__(self, bot=None):
        super().__init__(bot)
        self.db = HardDB()
        self.db.load()

    def get_instructions(self):
        return "Now we are going to show you the licenses with common rules only"
    
    def _generate_content(self, shared: Dict):
        current_item_idx = shared.get('current_item_idx', 0)
        components = shared.get(TYPE_CONFIG.get(ItemType.PC)['items_key'], [])
        current_comp = components[current_item_idx]
        licenses = self.db.get_unique_licenses(current_comp['compName'])
        filtered_licenses = [license for license in licenses if license != "Apache-2.0"]
        final_str = list_to_string(filtered_licenses)

        return final_str
    
    def process_special_logic(self, shared, result = None, content = None):
        if content == None:
            return shared
        else:
            shared['CommonRulesOnlyLicenses'] = content
            return shared

class AdditionalHandler(SubContentGenerationHandler):
    def __init__(self, bot=None):
        super().__init__(bot)
        self.db = HardDB()
        self.db.load()

    def get_instructions(self):
        return "Now we are going to check whether this release contains dual licenses..."
    
    def _generate_content(self, shared: Dict):
        current_item_idx = shared.get('current_item_idx', 0)
        components = shared.get(TYPE_CONFIG.get(ItemType.PC)['items_key'], [])
        current_comp = components[current_item_idx]
        licenses = self.db.get_unique_licenses(current_comp['compName'])
        filtered_licenses = [license for license in licenses if 'dual' in license]
        if len(filtered_licenses) == 0:
            return ''
        else:
            return '- Dual/triple license: document license selection.'
        
    def process_special_logic(self, shared, result = None, content = None):
        if content == None:
            return shared
        else:
            shared['AdditionalObligations'] = content
            return shared
class ImplementationHandler(SubContentGenerationHandler):
    def __init__(self, bot=None):
        super().__init__(bot)
        self.db = HardDB()
        self.db.load()

    def get_instructions(self):
        return "Now we are going to generate details of the implementation"
    
    def _generate_content(self, shared: Dict):
        current_item_idx = shared.get('current_item_idx', 0)
        components = shared.get(TYPE_CONFIG.get(ItemType.PC)['items_key'], [])
        discarded_licenses = [lic for lic in shared.get(TYPE_CONFIG.get(ItemType.LICENSE)['items_key'], []) if lic['status'] == ItemStatus.DISCARDED.value]
        current_comp = components[current_item_idx]
        licenses = self.db.get_unique_licenses(current_comp['compName'])
        filtered_licenses = [license for license in licenses if license in discarded_licenses]
        final_str = list_to_string(filtered_licenses)
        content = f"""
            - Licenses and copyrights have been added to Readme_OSS.
            - No Apache NOTICE file available.
            - License selection has been documented in Readme_OSS.
            - Source code is ready to be shipped to the customer.
            - Licenses that do not apply:
                - {final_str}
            - Acknowledgements have been added to Readme_OSS.
            - Check for required sub-components has been done.
            - Risk: Component binary has not been built from cleared source code.
        """
        return content
    
    def process_special_logic(self, shared, result = None, content = None):
        if content == None:
            return shared
        else:
            shared['ImplementationDetails'] = content
            return shared
        
class ObligationCombiningHandler(SubContentGenerationHandler):
    def __init__(self, bot=None):
        super().__init__(bot)
        self.db = HardDB()
        self.db.load()

    def get_instructions(self):
        return "Now we have generated the combined version for this chapter"
    
    def _generate_content(self, shared: Dict):
        Licenses_identified = shared['Licenses_identified']
        SubObligations = shared['SubObligations']
        CommonRulesOnlyLicenses = shared['CommonRulesOnlyLicenses']
        SubRisk = shared['SubRisk']
        AdditionalObligations = shared['AdditionalObligations']
        ImplementationDetails = shared['ImplementationDetails']

        current_item_idx = shared.get('current_item_idx', 0)
        components = shared.get(TYPE_CONFIG.get(ItemType.PC)['items_key'], [])
        current_comp = components[current_item_idx]

        general_assessment = self.db.get_general_assessment(current_comp['compName'])
        additional_notes = self.db.get_additional_nots(current_comp['compName'])

        final_chap = f"""
        ## {current_comp['compName']} \n\n
        General Assessment: {general_assessment}\n\n
        Additional Notes: {additional_notes}\n\n
        ### Licenses Identified\n\n
        {Licenses_identified}\n\n
        ### Obligations\n\n
        {SubObligations}\n\n
        ### Risks\n\n
        {SubRisk}\n\n
        ### Licenses with Common Rules Only\n\n
        {CommonRulesOnlyLicenses}\n\n
        ### Additional Obligations\n\n
        {AdditionalObligations}
        ### Implementation of Obligations / Remarks\n\n
        {ImplementationDetails}

        """

        return final_chap
    
    def process_special_logic(self, shared, result = None, content = None):
        if content is None:
            return shared
        else:
            shared['generated_obligations'] = content
            return shared