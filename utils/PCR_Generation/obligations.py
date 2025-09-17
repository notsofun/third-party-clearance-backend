from utils.itemFilter import ContentNormalizer

def get_license_descriptions(licenses, data_list, desc_type:str = 'description'):
    """
    Extract license descriptions from a nested dictionary list based on license names.
    
    Args:
        licenses (list): List of license dictionaries with 'name' field
        data_list (list): List of dictionaries containing license information with comma and newline separated licenses
    
    Returns:
        list: List of unique descriptions corresponding to the input licenses
    """
    result = []
    seen_descriptions = set()  # 用于去重
    
    # 从licenses列表中提取名称
    license_names = []
    for license_item in licenses:
        if isinstance(license_item, dict) and 'name' in license_item:
            license_names.append(license_item['name'])
        elif isinstance(license_item, str):
            license_names.append(license_item)
    
    # 遍历data_list中的每个项目
    for data_item in data_list:
        if not isinstance(data_item, dict) or "License" not in data_item or desc_type not in data_item:
            continue
        
        # 获取并分割许可证字符串
        license_string = data_item["License"]
        license_names_in_data = [name.strip() for name in license_string.split(", \n")]
        
        # 获取描述
        description = data_item[desc_type]
        
        # 检查是否有匹配的许可证
        match_found = False
        for license_name in license_names:
            for data_license in license_names_in_data:
                if license_name == data_license:
                    match_found = True
                    break
            
            if match_found:
                break
        
        # 如果找到匹配且描述未添加过，则添加到结果中
        if match_found and description not in seen_descriptions:
            result.append(description)
            seen_descriptions.add(description)
    
    return result

def list_to_string(desc_list:list) -> str:

    final_str = ''
    for i in desc_list:
        if isinstance(i, dict):
            i = i['content']

        mid = '- ' + i + '\n\n'
        final_str += mid

    return final_str

def generate_component_license_markdown(lic_comp_map):
    """
    生成组件与其许可证关系的Markdown格式列表
    
    参数:
    lic_comp_map -- 许可证到组件的映射字典，格式为 {许可证: [组件列表]}
    
    返回:
    Markdown格式的字符串，列出每个组件及其关联的许可证
    """
    # 步骤1: 创建反向映射 (组件 -> 许可证列表)
    comp_lic_map = {}
    
    for license_name, components in lic_comp_map.items():
        for component in components:
            if component not in comp_lic_map:
                comp_lic_map[component] = []
            comp_lic_map[component].append(license_name)
    
    # 步骤2: 生成Markdown格式的输出
    markdown_lines = []
    
    for component, licenses in comp_lic_map.items():
        # 构建组件项，格式: "组件名 (许可证1) (许可证2) ..."
        license_parts = " ".join([f"({lic})" for lic in licenses])
        markdown_line = f"• {component} {license_parts}"
        markdown_lines.append(markdown_line)
    
    # 步骤3: 将所有行连接为一个字符串
    return "\n".join(markdown_lines)