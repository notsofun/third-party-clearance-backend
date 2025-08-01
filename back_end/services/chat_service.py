import logging
from typing import Dict, Any, Tuple, Optional, Union
from utils.tools import get_strict_json, find_key_by_value
from enum import Enum

logger = logging.getLogger(__name__)

class ConfirmationStatus(Enum):
    """确认状态的枚举类型
    """
    SPECIAL_CHECK = "special_check"
    OEM = "OEMing"
    DEPENDENCY = "toDependency"
    COMPLIANCE = "toCompliance"

class ComponentStatus(Enum):
    """组件状态的枚举类型"""
    PENDING = ""
    CONFIRMED = "confirmed"

class ChatService:
    def __init__(self):
        """初始化聊天服务"""
        # 状态处理器映射表
        self.status_handlers = {
            ConfirmationStatus.SPECIAL_CHECK.value: self._handle_special_check,
            ConfirmationStatus.OEM.value: self._handle_oem,
            ConfirmationStatus.DEPENDENCY.value: self._handle_dependency,
            ConfirmationStatus.COMPLIANCE.value: self._handle_compliance
        }
    
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
        """


        # 获取当前组件信息
        component_info = self._get_component_info(shared)
        if not component_info.valid:
            return True, shared, component_info.error_message
            
        current_idx, comps, current_comp, risk_bot = component_info.data
        
        # 获取并执行对应状态的处理器
        # status_handler是一个字典，get可以用，status是一个查询键，而在status_handler这个字典内，就是通过获取confirmationStatus这个对象的属性，也就是字符串来映射状态的
        handler = self.status_handlers.get(status, self._handle_compliance)
        result = handler(current_comp, risk_bot, user_input)
        
        # 处理结果
        if result is False:
            # 组件确认完成，移至下一个
            return self._proceed_to_next_component(comps, current_idx, shared, risk_bot)
        else:
            # 继续当前组件的确认
            reply = self._extract_reply(result)
            return status, shared, reply # 这里要返回一个to哪一步的结果

    def _handle_special_check(self, comp: Dict, risk_bot: Any, user_input: str) -> Any:
        """处理预检查状态"""
        logger.info(f"执行预检查: {comp['title']}")
        # 这里实现预检查逻辑
        return False  # 实际实现中应返回适当的结果
    
    def _handle_oem(self, comp: Dict, risk_bot: Any, user_input: str, status:str) -> Any:
        """处理OEM状态"""
        logger.info(f"处理OEM组件: {comp['title']}")
        # 这个触发的时机是在用户发送消息之后诶……
        # 这里实现OEM处理逻辑
        result, status = risk_bot.OEMCheck(status,user_input)
        return result, status  # 实际实现中应返回适当的结果
    
    def _handle_dependency(self, comp: Dict, risk_bot: Any, user_input: str) -> Any:
        """处理依赖状态"""
        logger.info(f"处理依赖组件: {comp['title']}")
        # 这里实现依赖处理逻辑
        return False  # 实际实现中应返回适当的结果
    
    def _handle_compliance(self, comp: Dict, risk_bot: Any, user_input: str) -> Any:
        """处理合规性状态"""
        logger.info(f"执行合规性检查: {comp['title']}")
        return risk_bot.toConfirm(comp, user_input)

    def _get_component_info(self, shared: Dict[str, Any]) -> Any:
        """
        获取当前组件信息，包含安全检查
        
        Returns:
            ComponentInfo对象，包含组件信息或错误信息
        """
        # 创建一个简单的结果对象
        class ComponentInfo:
            def __init__(self, valid=True, data=None, error_message=""):
                self.valid = valid
                self.data = data
                self.error_message = error_message
        
        current_idx = shared.get("current_component_idx", 0)
        comps = shared.get("toBeConfirmedComps", [])
        
        # 安全检查：组件列表
        if not comps or current_idx >= len(comps):
            logger.error(f"无效的组件索引: {current_idx}, 总组件数: {len(comps)}")
            return ComponentInfo(False, None, "错误：没有找到要确认的组件")
        
        current_comp = comps[current_idx]
        risk_bot = shared.get("riskBot")
        
        # 安全检查：风险评估机器人
        if not risk_bot:
            logger.error("共享数据中未找到RiskBot")
            return ComponentInfo(False, None, "系统错误：无法找到风险评估机器人")
        
        return ComponentInfo(True, (current_idx, comps, current_comp, risk_bot), "")

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

    def _proceed_to_next_component(self, comps: list, current_idx: int, shared: Dict[str, Any], risk_bot: Any) -> Tuple[bool, Dict[str, Any], str]:
        """处理当前组件确认完成后的逻辑，准备下一个组件"""
        # 更新当前组件状态
        comps[current_idx]["status"] = ComponentStatus.CONFIRMED.value
        logger.info(f"组件 {comps[current_idx]['title']} 已确认")
        
        # 查找下一个待确认的组件
        next_idx = self._find_next_unconfirmed_component(comps, current_idx)
        
        if next_idx is None:
            # 所有组件都已确认
            logger.info("所有组件已确认完毕")
            shared["all_confirmed"] = True
            return True, shared, "所有组件已确认完毕!"
        
        # 移动到下一个组件
        shared["current_component_idx"] = next_idx
        next_comp = comps[next_idx]
        
        # 获取下一个组件的说明
        instruction = get_strict_json(
            risk_bot,
            f"here is the licenseName: {next_comp['title']}, "
            f"CheckedLevel: {next_comp['CheckedLevel']}, and "
            f"Justification: {next_comp['Justification']}"
        )
        
        return False, shared, f"前一个组件已确认，现在确认: {next_comp['title']} \n {instruction['talking']}"

    def _pre_check_with_condition(self, shared: Dict[str, Any], current_comp: str) -> Union[str, None]:
        """根据条件进行预检查，返回组件所属的类别"""
        categories = shared.get('specialCollections', {})
        return find_key_by_value(categories, current_comp)

    def confirm_input(self, shared, user_input):
        
        return 0

    def _find_next_unconfirmed_component(self, comps, current_idx):
        """查找下一个未确认的组件索引"""
        for idx in range(current_idx + 1, len(comps)):
            if comps[idx].get("status", "") == "":
                return idx
        
        # 如果后面没有，从头找
        for idx in range(0, current_idx):
            if comps[idx].get("status", "") == "":
                return idx
        
        return None  # 所有组件都已确认
    
    def initialize_chat(self, shared: Dict[str, Any], status:str) -> Tuple[Dict[str, Any], str]:
        """
        初始化聊天会话，准备第一个组件
        
        Returns:
            Tuple[updated_shared, initial_message]
        """
        comps = shared.get("toBeConfirmedComps", [])
        if not comps:
            return shared, "没有找到需要确认的组件"
        
        # 找到第一个未确认的组件
        first_idx = None
        for idx, comp in enumerate(comps):
            if comp.get("status", "") == ComponentStatus.PENDING.value:
                first_idx = idx
                break
        
        if first_idx is None:
            shared["all_confirmed"] = True
            return shared, "所有组件已经确认完毕"
        
        shared["current_component_idx"] = first_idx
        first_comp = comps[first_idx]
        risk_bot = shared.get("riskBot")
        
        if not risk_bot:
            return shared, "错误：未找到风险评估机器人"
        
        # 获取第一个组件的指导信息
        json_welcome = get_strict_json(
            risk_bot,
            f"here is the licenseName: {first_comp['title']}, "
            f"CheckedLevel: {first_comp['CheckedLevel']}, and "
            f"Justification: {first_comp['Justification']}"
        )
        
        response = risk_bot.OEMCheck(status=status,user_input='')
        message, status = response

        return shared, message, status
    
    def confirm_input(self, shared: Dict[str, Any], user_input: str) -> int:
        """确认用户输入"""
        # 根据需要实现此方法
        return 0