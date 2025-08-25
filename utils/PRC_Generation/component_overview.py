from utils.database.hardDB import HardDB
from utils.itemFilter import ContentNormalizer

def generate_components_markdown_table(shared_data, harddb:HardDB):
    """
    生成组件许可证信息的Markdown表格
    
    Args:
        shared_data: 包含组件基本信息的字典，包含parsedHtml/release_overview和releases键
        harddb: HardDB实例，用于查询组件类型和许可证
    
    Returns:
        字符串，包含Markdown格式的表格
    """
    # 检查数据完整性
    if (not shared_data or 'parsedHtml' not in shared_data or
            'release_overview' not in shared_data['parsedHtml'] or
            'releases' not in shared_data['parsedHtml']):
        return "No component data available."
    
    # 获取组件列表
    components = shared_data['parsedHtml']['release_overview']
    releases = shared_data['parsedHtml']['releases']
    
    # 创建表头
    markdown = "| Component Name | Component Version | Type | Licenses |\n"
    markdown += "|---------------|------------------|------|----------|\n"
    
    # 添加每个组件的行
    for component in components:
        name = component.get('name', 'Unknown')
        version = component.get('version', 'N/A')
        
        # 确定组件类型
        comp_type = "COTS" if harddb.is_COTS(name) else "OSS"
        
        # 从releases中获取许可证信息
        component_licenses = []
        for release in releases:
            release_name = release.get('name', '')
            normalized_release_name = ContentNormalizer.normalize_name(release_name)
            
            if normalized_release_name == name:  # 找到匹配项
                if 'licenses' in release and isinstance(release['licenses'], list):
                    component_licenses = release['licenses']
                    break  # 找到匹配组件后退出循环
        
        # 获取全局许可证以便加粗显示
        global_licenses = harddb.find_license_by_component(name, "global")
        
        # 格式化许可证，全局许可证加粗
        formatted_licenses = []
        for lic in component_licenses:
            if lic in global_licenses:
                formatted_licenses.append(f"**{lic}**")
            else:
                formatted_licenses.append(lic)
        
        # 如果没有找到许可证，使用默认值
        if not formatted_licenses:
            formatted_licenses = ["N/A"]
        
        # 格式化许可证字符串
        licenses_str = ", ".join(formatted_licenses)
        
        # 添加行到表格中
        markdown += f"| {name} | {version} | {comp_type} | {licenses_str} |\n"
    
    return markdown