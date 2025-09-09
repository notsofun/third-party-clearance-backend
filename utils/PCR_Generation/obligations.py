from utils.itemFilter import ContentNormalizer

def get_license_descriptions(licenses, data_list, desc_type:str = 'description'):
    """
    Extract license descriptions from a nested dictionary list based on license names.
    
    Args:
        licenses (list): List of license names to search for
        data_list (list): List of dictionaries containing license information
    
    Returns:
        list: List of descriptions corresponding to the input licenses
    """
    # Create a mapping of license names to their descriptions
    license_map = {}
    
    for item in data_list:
        if not isinstance(item, dict):
            continue
            
        # Check if this dictionary has license information
        if "License" in item and desc_type in item:
            license_name = item["License"]
            description = item[desc_type]
            
            # Add the description to our map (handle multiple descriptions per license)
            if license_name in license_map:
                if description not in license_map[license_name]:  # Avoid duplicates
                    license_map[license_name].append(description)
            else:
                license_map[license_name] = [description]
    
    # Retrieve descriptions for each requested license
    result = []
    seen_descriptions = set()
    
    for license_name in licenses:
        if isinstance(license_name, dict):
            license_name = license_name['name']

        for key in license_map.keys():
            lic_list = ContentNormalizer.remove_n(key)
            if license_name in lic_list:
                # Join all descriptions for this license with a separator
                descriptions = license_map[key]
                joined_desc = "\n\n".join(descriptions)
                
                # 去重检查
                if joined_desc not in seen_descriptions:
                    result.append(joined_desc)
                    seen_descriptions.add(joined_desc)
    
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