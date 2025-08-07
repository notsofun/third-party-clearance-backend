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

class ItemInfo(NamedTuple):
    """统一的项目信息结构"""
    valid: bool
    data: Optional[Tuple[int, List, Dict]]
    error_message: str = ""