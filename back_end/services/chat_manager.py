import logging
from typing import Dict, Any, Tuple, Optional, List, Callable
from .item_types import ItemType, ItemStatus, ItemInfo
from utils.decorator import deprecated

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
    
    @deprecated(reason='This method has not been used in any class')
    def proceed_to_next_item(self,
                            items: List[Dict],
                            current_idx: int,
                            shared: Dict[str, Any],
                            item_type: ItemType,
                            next_item_instruction: str) -> Tuple[bool, Dict[str, Any], str]:
        """
        处理当前项目确认完成后的逻辑，准备下一个项目
        
        Args:
            items: 项目列表
            current_idx: 当前项目索引
            shared: 共享数据
            item_type: 项目类型（许可证或组件）
            next_item_instruction: 下一个项目的指导文本
            
        Returns:
            (是否全部确认完毕, 更新后的共享数据, 提示消息)
        """
        # 更新当前项目状态
        items[current_idx]["status"] = ItemStatus.CONFIRMED.value
        
        # 记录项目名称（根据类型选择不同的字段）
        item_name = items[current_idx].get('title' if item_type == ItemType.LICENSE else 'compName', '未命名')
        logger.info(f"{item_type.value} {item_name} 已确认")
        
        # 查找下一个待确认的项目
        next_idx = self._find_next_unconfirmed_item(items, current_idx)
        
        # 更新索引键名
        idx_key = "current_license_idx" if item_type == ItemType.LICENSE else "current_component_idx"
        
        if next_idx is None:
            # 检查是否还有另一种类型的项目需要处理
            all_done = True
            if item_type == ItemType.LICENSE and "toBeConfirmedComponents" in shared:
                comps = shared.get("toBeConfirmedComponents", [])
                if any(comp.get("status", "") == ItemStatus.PENDING.value for comp in comps):
                    all_done = False
                    shared["current_component_idx"] = 0
                    shared["processing_type"] = "component"
                    return False, shared, f"所有{item_type.value}已确认完毕，现在开始确认组件"
            elif item_type == ItemType.COMPONENT and "toBeConfirmedLicenses" in shared:
                licenses = shared.get("toBeConfirmedLicenses", [])
                if any(lic.get("status", "") == ItemStatus.PENDING.value for lic in licenses):
                    all_done = False
                    shared["current_license_idx"] = 0
                    shared["processing_type"] = "license"
                    return False, shared, f"所有{item_type.value}已确认完毕，现在开始确认许可证"
            
            if all_done:
                logger.info("所有项目已确认完毕")
                shared["all_confirmed"] = True
                return True, shared, "所有项目已确认完毕!"
        
        # 移动到下一个项目
        shared[idx_key] = next_idx
        next_item = items[next_idx]
        
        item_display_name = next_item.get('title' if item_type == ItemType.LICENSE else 'compName', '未命名')
        return False, shared, f"Previous {item_type.value} has been confirmed, now confirming {item_display_name}\n{next_item_instruction}"
    
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