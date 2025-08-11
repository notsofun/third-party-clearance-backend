from enum import Enum
from typing import NamedTuple, Optional, Tuple, List, Dict, Any

class ItemType(Enum):
    """项目类型枚举"""
    LICENSE = "license"
    COMPONENT = "component"

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
    INPPROGRESS = 'in_progress'
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

