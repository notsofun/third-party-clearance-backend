from .content_handler import ChapterGeneration, SubContentGenerationHandler
from back_end.items_utils.item_types import ItemType, TYPE_CONFIG, ItemStatus
from utils.PCR_Generation.obligations import generate_component_license_markdown
from utils.tools import get_strict_json
from back_end.services.state_handlers.handler_registry import HandlerStateWrapper
from utils.database.hardDB import HardDB
from typing import Dict, Any

class SpecialConsiderationHandler(ChapterGeneration):

    def __init__(self, bot=None, item_list_key = None, subtask_factory = None, subcontent_factory = None, chapter_title_key = "Special Considerations", chapter_content_key = "generated_special_consideration"):
        super().__init__(bot, item_list_key, subtask_factory, subcontent_factory, chapter_title_key, chapter_content_key)

    def get_instructions(self):
        prompt = '''Now switch to confirming mode, you should decide to continue when user is not satisfied with the result or go on when user is satisfied'''
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', 'Please check the result for special considerations')
    
    def _create_content_handlers(self):
        """创建handler包装器列表，每个包装器包含共享的handler实例"""
        handlers = []
        handler_classes = [
            InteractionObligationHandler,
            CopyLeftHandler,
            AdditionalObligationHandler,
            OtherObligations,
            ReadmeOSS,
            SourceCodeHandler,
            RemainingHandler,
            SpecialCombiningHandler
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
    
class InteractionObligationHandler(SubContentGenerationHandler):

    def __init__(self, bot=None):
        super().__init__(bot)

    def process_special_logic(self, shared, result = None, content = None):
        if content == None:
            return shared
        else:
            shared['Obligations_resulting_from_interaction'] = content
            return shared
        
    def _generate_content(self, shared):
        return 'None'
    
    def get_instructions(self):
        return 'Now we have generated the content for obligations resulting from interactions between components.'
    
class CopyLeftHandler(SubContentGenerationHandler):

    def __init__(self, bot=None):
        super().__init__(bot)

    def process_special_logic(self, shared, result = None, content = None):
        if content == None:
            return shared
        else:
            shared['Copyleft_effect'] = content
            return shared
        
    def _generate_content(self, shared):
        return 'None'
    
    def get_instructions(self):
        return 'Now we have generated the content for copyleft.'
    
class AdditionalObligationHandler(SubContentGenerationHandler):
    def __init__(self, bot=None):
        super().__init__(bot)

    def process_special_logic(self, shared, result = None, content = None):
        if content == None:
            return shared
        else:
            shared['Additional_obligations_resulting_from_special_licenses'] = content
            return shared
        
    def _generate_content(self, shared: Dict):

        parsedHtml = shared["parsedHtml"]
        special_list = ['GPL-2.0', 'GPL-3.0', 'LGPL-2.1', 'LGPL-3.0']
        licenseTexts = [(item['id'], item['title'], item['text'])
                        for item in parsedHtml['license_texts']]
        special = False
        # 带了later、with exception的也会算进来
        for s_lic in special_list:
            for lic in licenseTexts:
                _, title, _ = lic
                if s_lic in title:
                    special = True
                    break

        if special:
            download_url = shared.get('download_url', 'Not found')
            return f'''
            OSS Software Declaration
            
            Embedded in this product are free software files that you may copy, distribute and/or modify under the terms of their respective licenses, such as the GNU General Public License, the GNU Lesser General Public License. In the event of conflicts between Siemens license conditions and the Open Source Software license conditions, the Open Source Software conditions shall prevail with respect to the Open Source Software portions of the software.
            
            On written request within three years from the date of product purchase and against payment of our expenses we will supply source code in line with the terms of the applicable license. For this, please contact us at:
            Siemens AG, Otto-Hahn-Ring 6, 81739 Muenchen, Germany
            Keyword: Open Source Request

            Generally, these embedded free software files are distributed in the hope that they will be useful, but WITHOUT ANY WARRANTY, without even implied warranty such as for MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE, and without liability for any Siemens entity other than as explicitly documented in your purchase contract.

            All open source software components used within the product (including their copyright holders and the license conditions) are contained on the web server, path ➞ [Standard Asset Portal]({download_url}).
            '''
        
        else:
            return 'None'
        
class OtherObligations(SubContentGenerationHandler):
    def __init__(self, bot=None):
        super().__init__(bot)

    def process_special_logic(self, shared, result = None, content = None):
        if content == None:
            return shared
        else:
            shared['Other_obligations'] = content
            return shared
        
    def _generate_content(self, shared):
        return 'None'
    
    def get_instructions(self):
        return 'Now we have generated the content for other obligations, which should be none if you have fulfilled all the requirements.'
    
class ReadmeOSS(SubContentGenerationHandler):
    def __init__(self, bot=None):
        super().__init__(bot)

    def process_special_logic(self, shared, result = None, content = None):
        if content == None:
            return shared
        else:
            shared['ReadmeOSS'] = content
            return shared
        
    def _generate_content(self, shared:Dict):
        html_data = shared.get('parsedHtml',None)
        if html_data:
            project_title = html_data['meta']['project_title']
            return f'Check of Readme_OSS for {project_title} has been done.'
        else:
            return 'Check of Readme_OSS for Unknown project has been done.'
    
    def get_instructions(self):
        return 'Now we have generated the content for description of oss readme.'
    
class SourceCodeHandler(SubContentGenerationHandler):

    def __init__(self, bot=None):
        super().__init__(bot)
        self.db = HardDB()
        self.db.load()

    def get_instructions(self):
        return 'Now we are generating content for components needing source codes.'
    
    def process_special_logic(self, shared, result = None, content = None):
        if content == None:
            return shared
        else:
            shared['Source_Codes'] = content
            return shared
        
    def _generate_content(self, shared):
        source_code_required_licenses = [item['licenseTitle'] for item in shared['riskAnalysis'] if item['sourceCodeRequired'] == True]
        lic_comp_map = {}
        for lic in source_code_required_licenses:
            components = self.db.find_components_by_license(lic)
            if lic not in lic_comp_map:
                lic_comp_map[lic] = components
            else:
                lic_comp_map[lic].extend(components)
        content = generate_component_license_markdown(lic_comp_map)
        final = 'Source code for the following components must be delivered on written request:\n\n' + content + '\n\n' + 'Recommendation is that all sources that might need to get shipped to the customer are stored in one single location.'

        return final
    
class RemainingHandler(SubContentGenerationHandler):

    def __init__(self, bot=None):
        super().__init__(bot)

    def get_instructions(self):
        return 'Now we are generating the rest part for the sixth chapter'
    
    def process_special_logic(self, shared, result = None, content = None):
        if content == None:
            return shared
        else:
            shared['Remaining_special'] = content
            return shared
        
    def _generate_content(self, shared):
        return '''
        ### EULA
        N/A – Embedded SW in device.

        ### Files not to be used
        Is ensured that files marked as 'do not use' or 'irrelevant' are really not getting used by the product?

        ### Export Control
        Export control is not part of software clearing. If export control information is found it is listed in the clearing report.

        All further evaluation, especially the product specific evaluation of all OSS components that contain encryption functionality needs to be done by the R&D team.

        ### Intellectual Property Rights
        IPR research is not part of software clearing. If IPR related information is found it is listed in the clearing report.

        All further evaluation needs to be done by the R&D team.

        ### Security Vulnerabilities
        Security vulnerability research is not part of software clearing.

        Security vulnerabilities are tracked in SVM-Portal. All further evaluation is to be done by the R&D team in cooperation with the product security team.
        '''
    
class SpecialCombiningHandler(SubContentGenerationHandler):

    def __init__(self, bot=None):
        super().__init__(bot)