from utils.database.hardDB import HardDB
from utils.itemFilter import ContentNormalizer
from log_config import get_logger

logger = get_logger(__name__)

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
    
    # 定义一个辅助函数进行严格的字符串规范化
    def strict_normalize(text):
        if not isinstance(text, str):
            return ""
        # 移除所有空白字符，并转为小写
        import re
        return re.sub(r'\s+', '', text.lower())
    
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
                if 'license_names' in release and isinstance(release['license_names'], list):
                    component_licenses = release['license_names']
                    break  # 找到匹配组件后退出循环
        
        # 获取全局许可证以便加粗显示
        global_licenses = harddb.find_license_by_component(name, "global")
        logger.info(f'we have found the global_licenses for {name}, which are {global_licenses}')
        
        # 规范化全局许可证
        normalized_global_licenses = [strict_normalize(lic) for lic in global_licenses]
        logger.info(f'Normalized global licenses: {normalized_global_licenses}')
        
        # 格式化许可证，全局许可证加粗
        formatted_licenses = []
        for lic in component_licenses:
            logger.info(f'Now We are reviewing this component_license {lic}')
            normalized_lic = strict_normalize(lic)
            
            # 详细记录比较过程
            logger.info(f'Normalized "{lic}" to "{normalized_lic}"')
            is_global = normalized_lic in normalized_global_licenses
            logger.info(f'Is in global licenses: {is_global}')
            if is_global:
                logger.info(f'MATCH FOUND - Adding as bold: **{lic}**')
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