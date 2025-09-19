from ..content_handler import ChapterGeneration, SubContentGenerationHandler
from back_end.items_utils.item_types import ItemType, TYPE_CONFIG, ItemStatus
from utils.PCR_Generation.obligations import get_license_descriptions, list_to_string
from utils.tools import get_strict_json
from back_end.services.state_handlers.handler_registry import HandlerStateWrapper
from utils.database.hardDB import HardDB
from typing import Dict, Tuple

class ObligationsHandler(ChapterGeneration):

    def __init__(self, bot=None, item_list_key = TYPE_CONFIG[ItemType.PC]['items_key'],
                expected_previous_chapter = 'Common Rules',
                chapter_title_key = 'Obligations resulting from the use of 3rd party components',
                chapter_content_key = 'Generated Obligations resulting from the use of 3rd party components'):
        super().__init__(bot, item_list_key, chapter_title_key, chapter_content_key)
        
    def get_instructions(self):
        prompt = '''Now switch to confirming mode, you should decide to continue when user is not satisfied with the result or go on when user is satisfied'''
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', 'Please check the result for obligations')
    
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
    
    def get_title_and_description(self) -> Tuple[str, str]:
        '''返回大章节标题和描述'''
        title = 'Obligations resulting from the use of 3rd party components'
        description = 'name - version contains the 3rd party components listed below.\n\nOnly components with obligations other than common obligations are shown. Apache-2.0 license is handled as if it has only common obligations, because no component has been modified.'
        return title, description
    
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
    
    # 现在没有处理实在为空的情况？
    def _generate_content(self, shared: Dict):
        current_item_idx = shared.get('current_item_idx', 0)
        components = shared.get(TYPE_CONFIG.get(ItemType.PC)['items_key'], [])
        current_comp = components[current_item_idx]
        licenses = self.db.get_unique_licenses(current_comp['compName'])
        filtered_licenses = [license for license in licenses if 'dual' in license]
        if len(filtered_licenses) == 0:
            return 'None'
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
        
# 这里需要注意一下怎么去拼之后对应每一个item
class ObligationCombiningHandler(SubContentGenerationHandler):
    def __init__(self, bot=None, item_subchapter = True):
        super().__init__(bot, item_subchapter)
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

        # 处理单行情况 (依然适用)
        original_string_single = current_comp['compName']
        first_line_single = original_string_single.splitlines()[0] if original_string_single else ""
        # 进一步清理第一行，去除 â§ 和末尾空格
        cleaned_first_line_single = first_line_single.replace("â§", "").strip()

        final_chap = f"""
## {cleaned_first_line_single} \n
General Assessment: {general_assessment}
Additional Notes: {additional_notes}\n
### Licenses Identified\n
{Licenses_identified}\n
### Obligations\n
{SubObligations}\n
### Risks\n
{SubRisk}\n
### Licenses with Common Rules Only\n
{CommonRulesOnlyLicenses}\n
### Additional Obligations\n
{AdditionalObligations}
### Implementation of Obligations / Remarks\n
{ImplementationDetails}
"""

        return final_chap
    
    def process_special_logic(self, shared, result = None, content = None):
        if content is None:
            return shared
        else:
            shared['generated_obligations'] = content
            return shared