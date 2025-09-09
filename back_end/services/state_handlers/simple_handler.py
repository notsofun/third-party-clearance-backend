from .base_handler import SimpleStateHandler, ContentGenerationHandler
from utils.tools import get_strict_json
from log_config import get_logger
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
    
class InteractionHandler(SimpleStateHandler):

    def get_instructions(self):
        prompt = self.bot.langfuse.get_prompt("bot/Interaction").prompt
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', 'Please check whether the obligations resulting from interaction between components is handled correctly.')
    
class CopyLeftHandler(SimpleStateHandler):

    def get_instructions(self):
        prompt = self.bot.langfuse.get_prompt("bot/Copyleft").prompt
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', 'Please check whether the your codes meet the requirements for copyleft.')

class CompletedHandler(SimpleStateHandler):

    def get_instructions(self) -> str:

        return 'We have finished all checking in current session, please reupload a new license info file to start a new session.'