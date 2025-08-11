import logging
from typing import Dict, Any, Tuple, Optional, List, Callable
from .item_types import ItemType, ItemStatus, ItemInfo, State
from utils.tools import get_strict_json


logger = logging.getLogger(__name__)

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
        # 根据类型选择对应的键
        if item_type == ItemType.LICENSE:
            current_key = "current_license_idx"
            items_key = "toBeConfirmedLicenses"
            error_msg = "错误：没有找到要确认的许可证"
        else:  # ItemType.COMPONENT
            current_key = "current_component_idx"
            items_key = "toBeConfirmedComponents"
            error_msg = "错误：没有找到要确认的组件"
        
        # 获取当前索引和项目列表
        current_idx = shared.get(current_key, 0)
        items = shared.get(items_key, [])
        
        # 安全检查：项目列表
        if not items or current_idx >= len(items):
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
            return shared, item_info.error_message, False
            
        current_idx, items, current_item = item_info.data
        current_status = current_item.get('status', ItemStatus.PENDING.value)
        
        # 处理CONTINUE操作
        if action == State.CONTINUE.value:
            return self._handle_continue_action(shared, item_type, current_idx, items, current_item, current_status, bot)
        
        # 处理NEXT操作
        elif action == State.NEXT.value:
            return self._handle_next_action(shared, item_type, current_idx, items, current_item, current_status, bot)
        
        # 处理未识别的操作
        else:
            return shared, "请明确您的选择：继续确认或进入下一项", False
    
    def _handle_continue_action(self, shared: Dict[str, Any], item_type: ItemType, current_idx: int,
                                items: List[Dict], current_item: Dict, current_status: str, bot) -> Tuple[Dict[str, Any], str, bool]:
        """处理CONTINUE操作"""
        # 如果当前项目是待确认状态，返回指导语
        if current_status == ItemStatus.PENDING.value:
            instruction = self._get_item_instruction(item_type, current_item, bot)
            
            # 更新shared中的项目状态为INPROGRESS
            if item_type == ItemType.LICENSE:
                shared['toBeConfirmedLicenses'][current_idx]['status'] = ItemStatus.INPROGRESS.value
            else:  # ItemType.COMPONENT
                shared['toBeConfirmedComponents'][current_idx]['status'] = ItemStatus.INPROGRESS.value
                
            return shared, instruction, False
        elif current_status == ItemStatus.INPROGRESS.value:
            # 确认中的项目，不多处理，在最外层直接返回模型返回内容
            return shared, "__USE_ORIGINAL_REPLY__", False
        else:
            # 已确认项目，直接返回通用消息
            item_name = self._get_item_name(item_type, current_item)
            return shared, f"项目 {item_name} 已确认，您可以继续操作或进入下一项", False
    
    def _handle_next_action(self, shared: Dict[str, Any], item_type: ItemType, current_idx: int, 
                            items: List[Dict], current_item: Dict, current_status: str, bot) -> Tuple[Dict[str, Any], str, bool]:
        """处理NEXT操作"""
        # 如果当前项目是待确认状态，则回调continue函数
        if current_status == ItemStatus.PENDING.value:
            logger.info('now we return back to handling continue function')
            return self._handle_continue_action(shared, item_type, current_idx, items, current_item,
                                                current_status, bot)
        
        # 如果当前项目是确认中状态，则将其更新为已确认状态
        elif current_status == ItemStatus.INPROGRESS.value:
            # 更新当前项目状态为已确认
            current_item['status'] = ItemStatus.CONFIRMED.value
            
            # 更新shared中的项目状态
            if item_type == ItemType.LICENSE:
                shared['toBeConfirmedLicenses'][current_idx] = current_item
            else:  # ItemType.COMPONENT
                shared['toBeConfirmedComponents'][current_idx] = current_item
            
            item_name = self._get_item_name(item_type, current_item)
            confirmation_message = f"{item_name} 已确认完成！"
        
        # 查找下一个待确认项目
        next_idx = self._find_next_unconfirmed_item(items, current_idx)
        
        if next_idx is not None:
            # 找到了下一个待确认项目，更新索引并返回指导语
            self._update_current_index(shared, item_type, next_idx)
            next_item = items[next_idx]
            instruction = self._get_item_instruction(item_type, next_item, bot)
            
            # 确保更新shared中的项目状态
            if item_type == ItemType.LICENSE:
                shared['toBeConfirmedLicenses'][next_idx] = next_item
            else:  # ItemType.COMPONENT
                shared['toBeConfirmedComponents'][next_idx] = next_item
                
            # 如果是从已确认项目转到下一个，添加确认消息
            if current_status == ItemStatus.INPROGRESS.value:
                return shared, f"{confirmation_message}\n\n{instruction}", False
            return shared, instruction, False
        else:
            # 没有找到待确认项目，检查是否需要切换项目类型
            if current_status == ItemStatus.INPROGRESS.value:
                # 先显示当前项目已确认的消息
                updated_shared, message, all_completed = self._check_switch_item_type(shared, item_type, bot)
                return updated_shared, f"{confirmation_message}\n\n{message}", all_completed
            else:
                updated_shared, message, all_completed = self._check_switch_item_type(shared, item_type, bot)
                return updated_shared, message, all_completed
    
    def _update_current_index(self, shared: Dict[str, Any], item_type: ItemType, new_idx: int) -> None:
        """更新当前索引"""
        if item_type == ItemType.LICENSE:
            shared['current_license_idx'] = new_idx
        else:
            shared['current_component_idx'] = new_idx
    
    def _check_switch_item_type(self, shared: Dict[str, Any], current_type: ItemType, bot) -> Tuple[Dict[str, Any], str, bool]:
        """检查是否需要切换项目类型"""
        if current_type == ItemType.LICENSE and "toBeConfirmedComponents" in shared:
            # 检查是否有待确认的组件
            return self._try_switch_to_components(shared, bot)
        elif current_type == ItemType.COMPONENT and "toBeConfirmedLicenses" in shared:
            # 检查是否有待确认的许可证
            return self._try_switch_to_licenses(shared, bot)
        
        # 所有项目都已确认
        return shared, f"所有{current_type.value}已确认完成", True
    
    def _try_switch_to_components(self, shared: Dict[str, Any], bot) -> Tuple[Dict[str, Any], str, bool]:
        """尝试切换到组件确认"""
        comps = shared.get("toBeConfirmedComponents", [])
        first_pending = next((i for i, c in enumerate(comps) if c.get("status", "") == ItemStatus.PENDING.value), None)
        
        if first_pending is not None:
            shared["current_component_idx"] = first_pending
            shared["processing_type"] = "component"
            instruction = self._get_item_instruction(ItemType.COMPONENT, comps[first_pending], bot)
            return shared, f"所有许可证已确认完毕，现在开始确认组件：\n{instruction}", False
        
        return shared, "所有项目已确认完毕", True
    
    def _try_switch_to_licenses(self, shared: Dict[str, Any], bot) -> Tuple[Dict[str, Any], str, bool]:
        """尝试切换到许可证确认"""
        licenses = shared.get("toBeConfirmedLicenses", [])
        first_pending = next((i for i, l in enumerate(licenses) if l.get("status", "") == ItemStatus.PENDING.value), None)
        
        if first_pending is not None:
            shared["current_license_idx"] = first_pending
            shared["processing_type"] = "license"
            instruction = self._get_item_instruction(ItemType.LICENSE, licenses[first_pending], bot)
            return shared, f"所有组件已确认完毕，现在开始确认许可证：\n{instruction}", False
        
        return shared, "所有项目已确认完毕", True
    
    def _get_item_name(self, item_type: ItemType, item: Dict) -> str:
        """获取项目名称"""
        if item_type == ItemType.LICENSE:
            return item.get('title', '未命名许可证')
        else:
            return item.get('compName', '未命名组件')
    
    def _get_item_instruction(self, item_type: ItemType, current_item: Dict, bot) -> str:
        """
        生成项目的指导文字
        
        Args:
            item_type: 项目类型（许可证或组件）
            current_item: 当前项目数据
            bot: 机器人实例
            
        Returns:
            指导文字
        """
        if item_type == ItemType.LICENSE:
            instruction_data = get_strict_json(
                bot,
                f"here is the licenseName: {current_item.get('title', '')}, "
                f"CheckedLevel: {current_item.get('CheckedLevel', '')}, and "
                f"Justification: {current_item.get('Justification', '')}"
            )
            item_name = current_item.get('title', 'unknown license')
        else:  # ItemType.COMPONENT
            instruction_data = get_strict_json(
                bot,
                f'''Here is the name of the component {current_item.get('compName', '')},
                and it contains dependency of other components, please confirm with user whether add the dependent
                component into the checklist'''
            )
            item_name = current_item.get('compName', 'unknown component')

        if isinstance(instruction_data, dict) and 'talking' in instruction_data:
            return instruction_data.get('talking', f"请确认{item_type.value}: {item_name}")
        return f"请确认{item_type.value}: {item_name}"

    def _find_next_unconfirmed_item(self, items: List[Dict], current_idx: int) -> Optional[int]:
        """
        查找下一个未确认的项目索引
        
        Args:
            items: 项目列表
            current_idx: 当前项目索引
            
        Returns:
            下一个未确认项目的索引，如果全部已确认则返回None
        """
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
        """
        初始化会话，确定第一个待处理的项目
        
        Args:
            shared: 共享数据字典
            
        Returns:
            Tuple[更新后的共享数据, 初始消息]
        """
        # 输入验证
        licenses = shared.get("toBeConfirmedLicenses", [])
        components = shared.get("toBeConfirmedComponents", [])
        components = [comp for comp in components if comp.get("dependency") == True]
        
        if not licenses and not components:
            return shared, "没有找到需要确认的项目"
        
        # 辅助函数：查找第一个待处理项的索引
        def find_first_pending(items):
            for idx, item in enumerate(items):
                if item.get("status", "") == ItemStatus.PENDING.value:
                    return idx
            return None
        
        # 查找待处理许可证和组件
        license_idx = find_first_pending(licenses) if licenses else None
        component_idx = find_first_pending(components) if components else None
        
        # 检查是否有待确认项目
        if license_idx is None and component_idx is None:
            shared["all_confirmed"] = True
            return shared, "所有项目已确认完毕"
        
        # 确定开始处理的项目类型
        if component_idx is not None:
            shared["current_component_idx"] = component_idx
            shared["processing_type"] = "component"
        elif license_idx is not None:
            shared["current_license_idx"] = license_idx
            shared["processing_type"] = "license"
        
        return shared, "检查已开始，请跟随提示完成确认流程"