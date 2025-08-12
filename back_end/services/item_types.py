from enum import Enum
from typing import NamedTuple, Optional, Tuple, List, Dict, Any

class ItemType(Enum):
    """项目类型枚举"""
    LICENSE = "license"
    COMPONENT = "component"
    CREDENTIAL = 'credential'

from enum import Enum

class ItemType(Enum):
    """项目类型枚举 - 保持不变"""
    LICENSE = "license"
    COMPONENT = "component"
    CREDENTIAL = 'credential'
    # 未来可添加更多类型...

# 单独添加配置映射
TYPE_CONFIG = {
    ItemType.LICENSE: {
        "current_key": "current_license_idx",
        "items_key": "toBeConfirmedLicenses",
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
    data: Optional[Tuple[int, List, Dict]]
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

