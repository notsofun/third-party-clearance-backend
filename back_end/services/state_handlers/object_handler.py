# state_handlers/oem_handler.py
from .base_handler import StateHandler
from utils.tools import get_strict_json
from log_config import get_logger

logger = get_logger(__name__)

class OEMStateHandler(StateHandler):
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
    
class ContractHandler(StateHandler):

    def get_instructions(self) -> str:
        """处理合同状态"""
        prompt = self.bot.langfuse.get_prompt("bot/Contract").prompt
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', '请提供合同信息')
    
class SpecialCheckHandler(StateHandler):

    def get_instructions(self) -> str:
        """处理预检查状态"""
        prompt = self.bot.langfuse.get_prompt("bot/SpecialCheck").prompt
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', '请进行特殊检查')

class CredentialHandler(StateHandler):
    
    def get_instructions(self) -> str:
        """处理授权许可证状态"""
        prompt = self.bot.langfuse.get_prompt("bot/Credential").prompt
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', '请确认授权信息')

class DependencyHandler(StateHandler):

    def get_instructions(self) -> str:
        """处理依赖状态"""
        prompt = self.bot.langfuse.get_prompt("bot/Dependecy").prompt
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', '请确认依赖关系')
    
class ComplianceHandler(StateHandler):

    def get_instructions(self) -> str:
        """处理合规性状态"""
        prompt = self.bot.langfuse.get_prompt("bot/Compliance").prompt
        response = get_strict_json(self.bot, prompt)
        return response.get('talking', '请确认合规信息')
    
class FinalListHandler(StateHandler):

    def get_instructions(self):
        return super().get_instructions()
    
class CompletedHandler(StateHandler):

    def get_instructions(self) -> str:

        return 'We have finished all checking in current session, please reupload a new license info file to start a new session.'