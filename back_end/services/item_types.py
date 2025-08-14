from enum import Enum
from typing import NamedTuple, Optional, Tuple, List, Dict, Any
from log_config import get_logger

logger = get_logger(__name__)  # 每个模块用自己的名称
class ItemType(Enum):
    """项目类型枚举"""
    LICENSE = "license"
    COMPONENT = "component"
    CREDENTIAL = 'credential'
    SPECIALCHECK = 'specialcheck'

# 单独添加配置映射
TYPE_CONFIG = {
    ItemType.LICENSE: {
        "current_key": "current_license_idx",
        "items_key": "checkedRisk",
        "error_msg": "错误：没有找到要确认的许可证",
        "name_field": "title",
        "default_name": "未命名许可证",
        "instruction_template": "here is the licenseName: {title}, CheckedLevel: {CheckedLevel}, and Justification: {Justification}",
        "instruction_fields": ["title", "CheckedLevel", "Justification"]
    },
    ItemType.COMPONENT: {
        "current_key": "current_component_idx",
        "items_key": "dependency_required__components",
        "error_msg": "错误：没有找到要确认的组件",
        "name_field": "compName",
        "default_name": "未命名组件",
        "instruction_template": "Here is the name of the component {compName}, and it contains dependency of other components, please confirm with user whether add the dependent component into the checklist",
        "instruction_fields": ["compName"]
    },
    ItemType.CREDENTIAL: {
        "current_key": "current_credential_idx",
        "items_key": "credential_required_components",
        "error_msg": "错误：没有找到要确认的凭证",
        "name_field": "credentialName",
        "default_name": "未命名凭证",
        "instruction_template": "Here is the name of the component {compName}, and it needs credential from other cooperation. Please confirm with users whether it is credentialized.",
        "instruction_fields": ["compName"]
    },
    ItemType.SPECIALCHECK : {
        "current_key": "current_speicalLic_idx",
        "items_key": "specialCollections",
        "error_msg": "错误：没有找到要确认的特殊许可证",
        "name_field": "licName",
        "default_name": "未命名许可证",
        "instruction_template": "here is the license name {licName} and it is {category}",
        "instruction_fields": ["licName", "category"]
    }

    
}

# 辅助函数
def get_type_config(item_type):
    """获取类型对应的配置"""
    config = TYPE_CONFIG.get(item_type)
    if not config:
        raise ValueError(f"不支持的项目类型: {item_type}")
    return config

def get_item_type_from_value(value: str) -> ItemType:
    """根据字符串值获取对应的枚举类型"""
    for item_type in ItemType:
        if item_type.value == value:
            return item_type
    # 如果没找到匹配的类型，可以设置默认值或抛出异常
    return ItemType.COMPONENT  # 默认返回组件类型

class ItemStatus(Enum):
    """项目状态枚举"""
    PENDING = ""
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    INPROGRESS = 'Inprogress'

class ItemInfo(NamedTuple):
    """统一的项目信息结构"""
    valid: bool
    data: Optional[Tuple[int, List, Dict, Tuple]]
    error_message: str = ""

class State(Enum):
    '''确认状态枚举'''
    COMPLETED = 'completed'
    INPROGRESS = 'in_progress'
    CONTINUE = 'continue'
    NEXT = 'next'

class ConfirmationStatus(Enum):
    """确认状态的枚举类型"""
    SPECIAL_CHECK = "special_check"
    OEM = "OEMing"
    DEPENDENCY = "toDependency"
    COMPLIANCE = "toCompliance"
    CONTRACT = 'toContract'
    CREDENTIAL = 'credential'
    COMPLETED = 'completed'

# 确认状态到处理类型的映射
CONFIRMATION_STATUS_TO_TYPE_MAP = {
    ConfirmationStatus.SPECIAL_CHECK.value: ItemType.SPECIALCHECK.value,  # 特殊检查对应许可证处理
    ConfirmationStatus.DEPENDENCY.value: ItemType.COMPONENT.value,  # 依赖关系对应组件处理
    ConfirmationStatus.COMPLIANCE.value: ItemType.LICENSE.value,    # 合规性对应许可证处理
    ConfirmationStatus.CREDENTIAL.value: ItemType.CREDENTIAL.value  # 凭证处理
}

# 默认处理类型
DEFAULT_PROCESSING_TYPE = ItemType.COMPONENT.value

def get_processing_type_from_status(status: str) -> str:
    """
    根据确认状态获取对应的处理类型值
    
    Args:
        status: 当前确认状态 (ConfirmationStatus枚举)
    
    Returns:
        处理类型的值（对应 ItemType 的 value）
    """
    # 从映射中获取处理类型
    if status in CONFIRMATION_STATUS_TO_TYPE_MAP:
        return CONFIRMATION_STATUS_TO_TYPE_MAP[status]
    
    logger.warning(f"最新状态为{status}，未找到处理类型(processing_type)，使用默认值: {DEFAULT_PROCESSING_TYPE}")
    # 如果没有映射，返回默认值
    return DEFAULT_PROCESSING_TYPE