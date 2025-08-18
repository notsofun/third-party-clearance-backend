from typing import Dict, Any, List
from .item_types import ItemStatus, ItemType, TYPE_CONFIG
import os, json

def is_item_completed(item: Dict[str, Any]) -> bool:
    '''检查项目是否已完成处理（包括确认或丢弃）'''

    return ItemStatus.is_terminal_status(item.get("status", ""))

def get_items_from_context(context: Dict[str, Any], item_type: ItemType) -> List[Dict[str, Any]]:
    """从上下文获取指定类型的项目列表"""
    config = TYPE_CONFIG.get(item_type, {})
    items_key = config.get("items_key", "")
    return context.get("shared", {}).get(items_key, [])

def update_item_status(shared: Dict[str, Any], item_type: ItemType, idx: int, new_status: str) -> Dict[str, Any]:
    """更新项目状态"""
    config = TYPE_CONFIG.get(item_type, {})
    items_key = config.get("items_key", "")
    
    if items_key in shared and 0 <= idx < len(shared[items_key]):
        shared[items_key][idx]['status'] = new_status
    
    return shared

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

def process_items_and_generate_finals(shared):
    """
    处理shared中的数据，根据TYPE_CONFIG中定义的配置，生成最终的结果列表
    
    参数:
    shared - 包含所有数据的共享字典
    
    返回:
    包含final_licenses, final_components, final_credentials, final_specialchecks和final_overview的字典
    """
    result = {}
    
    # 创建输出目录(如果不存在)
    output_dir = "filtered_results"
    os.makedirs(output_dir, exist_ok=True)

    # 遍历所有类型
    for type_key, config in TYPE_CONFIG.items():
        items_key = config["items_key"]
        type_name = type_key.value  # 使用枚举值作为类型名称
        
        # 初始化结果列表
        confirmed_items = []
        discarded_items = []
        
        # 检查shared中是否包含该类型的数据
        if items_key in shared:
            # 遍历该类型的所有项目
            raw_filename = os.path.join(output_dir, f"raw_{type_name}s.json")
            with open(raw_filename, "w", encoding="utf-8") as f:
                json.dump(shared[items_key], f, ensure_ascii=False, indent=2)

            for item in shared[items_key]:
                # 检查项目是否有状态字段
                if "status" in item:
                    if item["status"] == ItemStatus.CONFIRMED.value:
                        confirmed_items.append(item)
                    elif item["status"] == ItemStatus.DISCARDED.value:
                        discarded_items.append(item)

            # 保存确认的项目
            confirmed_filename = os.path.join(output_dir, f"confirmed_{type_name}s.json")
            with open(confirmed_filename, "w", encoding="utf-8") as f:
                json.dump(confirmed_items, f, ensure_ascii=False, indent=2)
        
        # 将结果添加到返回字典中
        result[f"final_{type_name}s"] = confirmed_items
        
    
    return result