from typing import Dict, Any, Tuple, Optional, List
from ..items_utils.item_types import ItemType, ItemStatus, ItemInfo, State, TYPE_CONFIG
from utils.tools import get_strict_json
from utils.LLM_Analyzer import RiskBot
from back_end.items_utils.item_utils import is_item_completed, update_item_status
from back_end.items_utils.item_utils import get_type_config

from log_config import get_logger

logger = get_logger(__name__)  # 每个模块用自己的名称

class ChatManager:
    """
    管理项目状态的类，负责项目的导航、状态更新和信息检索
    """
    
    def __init__(self):
        """初始化 ChatManager 类"""
        pass
    
    def get_item(self, shared: Dict[str, Any], item_type: ItemType) -> ItemInfo:
        """
        获取当前项目信息（许可证或组件）
        
        Args:
            shared: 共享数据字典
            item_type: 项目类型（许可证或组件）
            
        Returns:
            ItemInfo对象，包含项目信息或错误信息
        """
        # 根据类型获取对应配置
        config = get_type_config(item_type)
        current_key = config["current_key"]
        items_key = config["items_key"]
        error_msg = config["error_msg"]
        
        # 获取当前索引和项目列表
        current_idx = shared.get(current_key, 0)
        items = shared.get(items_key, [])
        
        # 安全检查：项目列表
        if not items:
            logger.warning('当前类型中不存在数据%s',item_type.value)
            return ItemInfo(False,None,f'Shared中不存在数据{item_type.value}')
        elif current_idx >= len(items):
            logger.error(f"无效的{item_type.value}索引: {current_idx}, 总数量: {len(items)}")
            return ItemInfo(False, None, error_msg)
        
        current_item = items[current_idx]
        
        return ItemInfo(True, (current_idx, items, current_item), "")
    
    def handle_item_action(self, shared: Dict[str, Any], item_type: ItemType, action: str, bot) -> Tuple[Dict[str, Any], str, bool]:
        """
        处理项目的操作（继续确认或移至下一项）
        
        Args:
            shared: 共享数据字典
            item_type: 项目类型（LICENSE或COMPONENT）
            action: 操作类型（CONTINUE或NEXT）
            bot: 机器人实例
            
        Returns:
            Tuple[更新后的共享数据, 响应消息, 是否所有项目已完成]
        """
        # 获取当前项目信息
        item_info = self.get_item(shared, item_type)
        if not item_info.valid:
            # 适配shared无数据的情况，直接到下一个节点
            return shared, item_info.error_message, True
            
        current_idx, items, current_item = item_info.data
        current_status = current_item.get('status', ItemStatus.PENDING.value)
        
        # 处理CONTINUE操作
        if action == State.CONTINUE.value:
            return self._handle_continue_action(shared, item_type, current_idx, items, current_item, current_status, bot)
        
        # 处理NEXT操作
        elif action in [State.NEXT.value, State.DISCARDED.value]:
            return self._handle_action_with_transitions(shared, item_type, current_idx, items, current_item, current_status, bot, action)
        
        # 处理未识别的操作
        else:
            return shared, "请明确您的选择：继续确认或进入下一项", False
    
    def _handle_continue_action(self, shared: Dict[str, Any], item_type: ItemType, current_idx: int, items: List[Dict], current_item: Dict, current_status: str, bot) -> Tuple[Dict[str, Any], str, bool]:
        """处理CONTINUE操作"""
        # 获取配置
        config = get_type_config(item_type)
        items_key = config["items_key"]
        current_key = config['current_key']
        if shared.get(current_key, 0) == 0:
            shared[current_key] = current_idx

        # 如果当前项目是待确认状态，返回指导语
        if current_status == ItemStatus.PENDING.value:
            instruction = self._get_item_instruction(item_type, current_item, bot)
            
            # 更新shared中的项目状态为INPROGRESS
            shared[items_key][current_idx]['status'] = ItemStatus.INPROGRESS.value
                
            return shared, instruction, False
        elif current_status == ItemStatus.INPROGRESS.value:
            # 确认中的项目，不多处理，在最外层直接返回模型返回内容
            return shared, "__USE_ORIGINAL_REPLY__", False
        else:
            # 已确认项目，直接返回通用消息
            item_name = self._get_item_name(item_type, current_item)
            return shared, f"{item_name} has been confirmed, you could continue processing or switch to the next", False
    
    def _handle_action_with_transitions(self, shared: Dict[str, Any], item_type: ItemType, current_idx: int,items: List[Dict], current_item: Dict, current_status: str, bot: object, action: str) -> Tuple[Dict[str, Any], str, bool]:
        """处理NEXT操作"""
        # 获取配置
        confirmation_message = ""

        # 如果当前项目是待确认状态，则回调continue函数
        if current_status == ItemStatus.PENDING.value:
            logger.info('chat_manager.handle_next: now we return back to handling continue function')
            return self._handle_continue_action(shared, item_type, current_idx, items, current_item,
                                                current_status, bot)
        
        # 如果当前项目是确认中状态，则将其更新为已确认状态
        # 处理进行中状态：根据操作更新状态
        elif current_status == ItemStatus.INPROGRESS.value:
            # 根据action获取对应的终止状态
            new_status = ItemStatus.get_status_from_action(action)
            if new_status:
                shared = update_item_status(shared, item_type, current_idx, new_status)
                status_display = "confirmed" if new_status == ItemStatus.CONFIRMED.value else "discarded"
                
                item_name = self._get_item_name(item_type, current_item)
                confirmation_message = f"{item_name} has been {status_display}!"
                
                logger.info(f'chat_manager: updated item status to {new_status}')
        
        # 已经是终止状态的项目
        elif is_item_completed(current_item):
            item_name = self._get_item_name(item_type, current_item)
            confirmation_message = f"{item_name} was already processed. Moving to next item."
        
        # 查找下一个待确认项目
        next_idx = self._find_next_unconfirmed_item(items, current_idx)
        
        if next_idx is not None:
            # 找到了下一个待确认项目，更新索引并返回指导语
            self._update_current_index(shared, item_type, next_idx)
            next_item = items[next_idx]
            instruction = self._get_item_instruction(item_type, next_item, bot)

            # 确保更新shared中的项目状态
            shared = update_item_status(shared, item_type, next_idx, ItemStatus.INPROGRESS.value)
                
            # 添加确认消息（如果有）
            if confirmation_message:
                return shared, f"{confirmation_message}\n\n{instruction}", False
            return shared, instruction, False
        else:
            # 没有未处理项目，完成当前流程
            if confirmation_message:
                return shared, f"{confirmation_message}\n\nWe have finished current checking!", True
            return shared, "We have finished current checking!", True
    
    def _update_current_index(self, shared: Dict[str, Any], item_type: ItemType, new_idx: int) -> None:
        """更新当前索引"""
        # 获取配置
        config = get_type_config(item_type)
        
        # 使用配置中定义的当前索引键
        current_key = config["current_key"]
        
        # 更新shared中的索引
        shared[current_key] = new_idx

    def _get_item_name(self, item_type: ItemType, item: Dict) -> str:
        """获取项目名称"""
        # 获取配置
        config = get_type_config(item_type)
        
        # 如果配置中没有name_field，则使用默认逻辑
        if "name_field" not in config:
            if item_type == ItemType.LICENSE:
                return item.get('title', '未命名许可证')
            else:
                return item.get('compName', '未命名组件')
        
        # 使用配置中的名称字段和默认值
        name_field = config["name_field"]
        default_name = config.get("default_name", f"未命名{item_type.value}")
        
        return item.get(name_field, default_name)
    
    def _get_item_instruction(self, item_type: ItemType, current_item: Dict, bot) -> str:
        """生成项目的指导文字"""
        # 获取配置
        config = get_type_config(item_type)
        
        # 使用配置中的模板和字段信息
        instruction_template = config.get("instruction_template")
        name_field = config.get("name_field")
        default_name = config.get("default_name", f"unknown {item_type.value}")
        
        # 获取项目名称
        item_name = current_item.get(name_field, default_name)
        
        # 构建提示文本
        if instruction_template:
            # 使用模板构建提示，替换占位符
            prompt = instruction_template.format(
                **{field: current_item.get(field, "") for field in config.get("instruction_fields", [])}
            )
        else:
            logger.error(f'Sorry, please check the item_types.py file to assure you have the correct config for the item_type: {item_type.value} you specified')
            prompt = 'Please tell user that there is no prompt for the type he or she specified'
        
        # 调用bot获取指导文字
        instruction_data = get_strict_json(bot, prompt)
        
        # 处理返回结果
        if isinstance(instruction_data, dict) and 'talking' in instruction_data:
            return instruction_data.get('talking', f"请确认{item_type.value}: {item_name}")
        return f"请确认{item_type.value}: {item_name}"

    def _update_item_status(shared: Dict[str, Any], item_type: ItemType, idx: int, new_status: str) -> Dict[str, Any]:
        """更新项目状态"""
        config = TYPE_CONFIG.get(item_type, {})
        items_key = config.get("items_key", "")
        
        if items_key in shared and 0 <= idx < len(shared[items_key]):
            shared[items_key][idx]['status'] = new_status
        
        return shared

    def _find_next_unconfirmed_item(self, items: List[Dict], current_idx: int) -> Optional[int]:
        """
        查找下一个未确认的项目索引
        
        Args:
            items: 项目列表
            current_idx: 当前项目索引
            
        Returns:
            下一个未确认项目的索引，如果全部已确认则返回None
        """
        if not items:
            return None # 整个列表为空

        # 先检查当前索引之后的项目
        for idx in range(current_idx + 1, len(items)):
            if items[idx].get("status", "") == ItemStatus.PENDING.value:
                return idx
        
        # 如果后面没有，从头检查到当前索引
        for idx in range(0, current_idx):
            if items[idx].get("status", "") == ItemStatus.PENDING.value:
                return idx
        
        return None  # 所有项目都已确认
    
    def initialize_session(self, shared: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
        """初始化会话，确定第一个待处理的项目"""
        # 辅助函数：查找第一个待处理项的索引
        def find_first_pending(items):
            # 首先检查items是否为None或空
            if not items:  # 同时处理None和空列表/字典等情况
                return None
            
            # 遍历查找待处理项
            for idx, item in enumerate(items):
                # 增加对item本身是否为None的检查
                if item is not None and item.get("status", "") == ItemStatus.PENDING.value:
                    return idx
            
            # 未找到待处理项
            return None
        
        # 处理所有项目类型
        available_types = []
        pending_types = []
        
        for item_type in ItemType:

            # 获取配置
            config = get_type_config(item_type)
            items_key = config.get("items_key")
            
            # 获取项目列表
            items = shared.get(items_key, [])
            if not items:
                continue
                
            available_types.append(item_type)
            
            # 查找第一个待处理项
            idx = find_first_pending(items)
            if idx is not None:
                pending_types.append((item_type, idx))
            
            # logger.warning('we are going through item_key when initializing the chat_manager %s', item_type)
        
        # 检查是否有可用项目
        if not available_types:
            return shared, "没有找到需要确认的项目"
        
        # 检查是否有待确认项目
        if not pending_types:
            shared["all_confirmed"] = True
            return shared, "所有项目已确认完毕"
        
        # 确定开始处理的项目类型（这里可以定义优先级）
        selected_type, selected_idx = pending_types[0]  # 默认选第一个
        
        # 获取选中类型的配置
        config = get_type_config(selected_type)
        current_key = config["current_key"]
        
        # 更新shared
        shared[current_key] = selected_idx
        shared["processing_type"] = selected_type.value

        logger.warning('now we start with checking: %s', selected_type.value)
        
        return shared, "检查已开始，请跟随提示完成确认流程"
    
if __name__ == "__main__":

    item_type = ItemType.SPECIALCHECK

    current_item = {
        'licName': 'GPL',
        'category': 'GPL'
    }

    manager = ChatManager()
    bot1 = RiskBot('itemTrial')
    response = manager._get_item_instruction(
        item_type,
        current_item,
        bot1
    )

    print(response)