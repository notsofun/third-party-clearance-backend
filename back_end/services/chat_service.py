import logging
from typing import Dict, Any, Tuple, Optional
from utils.tools import get_strict_json

logger = logging.getLogger(__name__)

class ChatService:
    def __init__(self):
        pass
    
    def process_user_input(self, shared: Dict[str, Any], user_input: str) -> Tuple[bool, Dict[str, Any], str]:
        """
        处理用户输入，更新当前组件的确认状态
        
        Args:
            shared: 会话共享数据
            user_input: 用户输入
            
        Returns:
            Tuple[is_complete, updated_shared_data, reply_message]
            is_complete: 所有组件是否已全部确认完毕
            updated_shared_data: 更新后的会话数据
            reply_message: 返回给用户的消息
        """
        # 获取当前正在处理的组件
        current_idx = shared.get("current_component_idx", 0)
        comps = shared.get("toBeConfirmedComps", [])
        
        # 安全检查
        if not comps or current_idx >= len(comps):
            logger.error(f"Invalid component index: {current_idx}, total components: {len(comps)}")
            return True, shared, "错误：没有找到要确认的组件"
        
        current_comp = comps[current_idx]
        risk_bot = shared.get("riskBot")
        
        if not risk_bot:
            logger.error("RiskBot not found in shared data")
            return True, shared, "系统错误：无法找到风险评估机器人"
        
        # 处理用户输入，获取确认结果
        # 假设toConfirm返回False表示确认未完成，需要继续对话
        # 返回"passed"或"discarded"表示确认完成，可以移到下一个组件
        result = risk_bot.toConfirm(current_comp, user_input)
        
        # 获取回复消息（假设riskbot会将最新回复存储在某处）
        # 这里需要根据您的riskbot实现进行调整
        try:
            reply = result['talking']
        except Exception:
            pass
        
        # 如果组件确认完成
        if result is False:
            # 更新当前组件状态
            comps[current_idx]["status"] = 'confirmed'
            logger.info(f"Component {current_comp['title']} confirmed.")
            
            # 查找下一个待确认的组件
            next_idx = self._find_next_unconfirmed_component(comps, current_idx)
            
            if next_idx is None:
                # 所有组件都已确认
                logger.info("All components have been confirmed")
                shared["all_confirmed"] = True
                return True, shared, "All components have been confirmed!"
            else:
                # 移动到下一个组件
                shared["current_component_idx"] = next_idx
                next_comp = comps[next_idx]
                instruction = get_strict_json(risk_bot,f"here is the licenseName: {next_comp['title']}, CheckedLevel: {next_comp['CheckedLevel']}, and Justification: {next_comp['Justification']}")
                return False, shared, f"Previous component has been confirmed, now we are confirming: {next_comp['title']} \n {instruction['talking']}"
        else:
            # 继续确认当前组件
            return False, shared, reply
    
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
    
    def initialize_chat(self, shared):
        """初始化聊天会话，准备第一个组件"""
        comps = shared.get("toBeConfirmedComps", [])
        if not comps:
            return shared, "没有找到需要确认的组件"
        
        # 找到第一个未确认的组件
        first_idx = None
        for idx, comp in enumerate(comps):
            if comp.get("status", "") == "":
                first_idx = idx
                break
        
        if first_idx is None:
            shared["all_confirmed"] = True
            return shared, "所有组件已经确认完毕"
        
        shared["current_component_idx"] = first_idx
        first_comp = comps[first_idx]

        risk_bot = shared.get("riskBot")

        json_welcome = get_strict_json(risk_bot,f"here is the licenseName: {first_comp['title']}, CheckedLevel: {first_comp['CheckedLevel']}, and Justification: {first_comp['Justification']}")

        return shared, json_welcome['talking']