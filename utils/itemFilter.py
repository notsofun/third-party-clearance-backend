import json
from log_config import get_logger

logger = get_logger(__name__)  # 每个模块用自己的名称

def filter_components_by_credential_requirement(components, parsed_html, risk_analysis):
    """
    筛选需要凭证(CredentialOrNot为true)的组件，并记录详细匹配日志
    """
    def criteria_func(release, risk_analysis):
        logger.info(f"正在检查组件: {release.get('name', '未知组件')}")
        logger.info(f"组件许可证列表: {json.dumps(release.get('license_names', []), ensure_ascii=False)}")
        
        # 创建许可证映射，处理空格问题
        license_map = {}
        for risk_item in risk_analysis:
            # 处理risk_key中的许可证名称
            if ': ' in risk_item['licenseTitle']:
                clean_key = risk_item['licenseTitle'].split(': ')[-1].rstrip('⇧').strip()
            else:
                clean_key = risk_item['licenseTitle'].rstrip('⇧').strip()
                
            license_map[clean_key] = {
                'risk_key': risk_item['licenseTitle'],
                'data': risk_item
            }
            
            # 处理LicenseName字段
            if 'credentialOrNot' in risk_item and 'LicenseName' in risk_item['credentialOrNot']:
                alt_name = risk_item['credentialOrNot']['LicenseName'].strip()
                if alt_name:
                    license_map[alt_name] = {
                        'risk_key': risk_item['licenseTitle'],
                        'data': risk_item,
                        'alt_name': True
                    }
        
        logger.info(f"风险分析中的许可证: {json.dumps(list(license_map.keys()), ensure_ascii=False)}")
        
        # 检查release中的每个许可证
        for license_name in release.get('license_names', []):
            clean_license = license_name.strip()
            
            if clean_license in license_map:
                match_info = license_map[clean_license]
                risk_data = match_info['data']
                risk_key = match_info['risk_key']
                
                credential_required = risk_data['credentialOrNot'].get('CredentialOrNot', False)
                
                if credential_required:
                    return True
        
        return False
    
    logger.info(f"开始筛选组件，共 {len(components)} 个组件待处理")
    result = filter_components_by_criteria(components, parsed_html, risk_analysis, criteria_func)
    logger.info(f"筛选完成，保留了 {len(result)} 个需要凭证的组件")

    result = convert_list_to_dict_list(result)
    
    return result

def convert_list_to_dict_list(nested_list, keys=None):
    """
    将嵌套列表转换为字典列表，带有更多健壮性处理
    
    参数:
    nested_list -- 格式为 [[value1, value2, value3], ...] 的嵌套列表
    keys -- 可选的键名列表，默认为 ["compName", "blockHtml", "sessionId"]
    
    返回:
    包含字典的列表
    """
    if keys is None:
        keys = ["compName", "blockHtml", "sessionId"]
    
    result = []
    
    for item in nested_list:
        if not isinstance(item, (list, tuple)):
            continue
            
        component_dict = {}
        for i, value in enumerate(item):
            if i < len(keys):
                component_dict[keys[i]] = value
            else:
                # 处理额外的值
                component_dict[f"extra_{i}"] = value
        
        if component_dict:  # 如果字典不为空
            result.append(component_dict)
    
    return result

def filter_components_by_criteria(components, parsed_html, risk_analysis, criteria_func, match_func=None):
    """筛选组件的通用函数"""
    if match_func is None:
        # 默认匹配函数，增加健壮性处理
        def default_match_func(comp, rel):
            try:
                if isinstance(comp, (list, tuple)) and len(comp) > 0:
                    comp_name = comp[0].strip() if isinstance(comp[0], str) else str(comp[0])
                elif isinstance(comp, dict) and 'name' in comp:
                    comp_name = comp['name'].strip()
                    return False
                
                rel_name = rel['name'].strip() if isinstance(rel['name'], str) else str(rel['name'])
                
                return comp_name == rel_name
            except Exception as e:
                logger.error(f"匹配过程出错: {str(e)}")
                return False
                
        match_func = default_match_func
    
    filtered_components = []
    
    for idx, component in enumerate(components):
        logger.info(f"处理组件 {idx+1}/{len(components)}")
        
        # 在parsed_html中找到对应的release
        try:
            release = next((rel for rel in parsed_html['releases'] if match_func(component, rel)), None)
            
            if release:
                
                if criteria_func(release, risk_analysis):
                    filtered_components.append(component)
        except Exception as e:
            logger.error(f"处理组件时出错: {str(e)}")
    
    return filtered_components

class ContentNormalizer:
    @staticmethod
    def normalize_name(name):
        """
        Normalize a name by removing whitespace, newlines, and special characters.
        
        Parameters:
        - name: The name to normalize
        
        Returns:
        - Normalized name
        """
        if not isinstance(name, str):
            return str(name)
        
        # Remove newlines and leading/trailing whitespace
        name = name.strip()
        
        # Remove trailing ⇧ character if present
        name = name.rstrip('⇧').strip()
        
        # Extract the name part before any newlines
        name = name.split('\n')[0].strip()
        
        # Handle license titles with format like "2: CC-BY-4.0⇧"
        if ":" in name:
            name = name.split(":", 1)[1].strip()  # Get the part after the first colon
        
        # For component names, we need to extract just the package name without version
        # This handles cases like "@ngrx/store 17.2.0"
        parts = name.split(' ')
        if len(parts) > 1 and any(c.isdigit() for c in parts[-1]):
            # If the last part looks like a version number, use just the package name
            package_name = ' '.join(parts[:-1])
            return package_name.strip()
        
        return name


class HtmlContentFilter:
    def __init__(self, logger):
        self.logger = logger
        self.normalizer = ContentNormalizer()
    
    def extract_component_names(self, filtered_components):
        """
        Extract normalized component names from different input formats.
        
        Parameters:
        - filtered_components: List of component names/objects
        
        Returns:
        - Set of normalized component names
        """
        component_names = set()
        if not isinstance(filtered_components, list):
            return component_names
            
        for comp in filtered_components:
            try:
                if isinstance(comp, (list, tuple)) and len(comp) > 0:
                    component_names.add(self.normalizer.normalize_name(comp[0]))
                elif isinstance(comp, dict) and 'compName' in comp:
                    component_names.add(self.normalizer.normalize_name(comp['compName']))
                elif isinstance(comp, dict) and 'name' in comp:
                    component_names.add(self.normalizer.normalize_name(comp['name']))
                elif isinstance(comp, str):
                    component_names.add(self.normalizer.normalize_name(comp))
            except Exception as e:
                self.logger.warning(f"Error processing component: {e}")
                
        return component_names
    
    def extract_license_names(self, filtered_licenses):
        """
        Extract normalized license names from different input formats.
        
        Parameters:
        - filtered_licenses: List of license names/objects
        
        Returns:
        - Set of normalized license names
        """
        license_names = set()
        if not isinstance(filtered_licenses, list):
            return license_names
            
        for lic in filtered_licenses:
            try:
                if isinstance(lic, dict) and 'title' in lic:
                    license_names.add(self.normalizer.normalize_name(lic['title']))
                elif isinstance(lic, str):
                    license_names.add(self.normalizer.normalize_name(lic))
            except Exception as e:
                self.logger.warning(f"Error processing license: {e}")
                
        return license_names
    
    def filter_release_overview(self, html_data, component_names):
        """
        Filter the release_overview section based on component names.
        
        Parameters:
        - html_data: The original HTML JSON data
        - component_names: Set of normalized component names to keep
        
        Returns:
        - Filtered release_overview list
        """
        filtered_overview = []
        
        for item in html_data.get("release_overview", []):
            item_name = self.normalizer.normalize_name(item.get("name", ""))
            if item_name in component_names:
                filtered_overview.append(item)
                self.logger.info(f"Keeping component in release_overview: {item_name}")
            else:
                self.logger.info(f"Removing component from release_overview: {item_name}")
                
        return filtered_overview
    
    def filter_releases(self, html_data, component_names, license_names):
        """
        Filter the releases section based on component and license names.
        
        Parameters:
        - html_data: The original HTML JSON data
        - component_names: Set of normalized component names to keep
        - license_names: Set of normalized license names to keep
        
        Returns:
        - Filtered releases list
        """
        filtered_releases = []
        
        for release in html_data.get("releases", []):
            release_name = self.normalizer.normalize_name(release.get("name", ""))
            
            # Check if this release's name matches any component name
            matched = False
            for comp_name in component_names:
                if release_name.startswith(comp_name):
                    matched = True
                    break
            
            if matched:
                # This component should be kept, but we need to filter its licenses
                filtered_release = release.copy()
                self.logger.info(f"Keeping component in releases: {release_name}")
                
                # Filter licenses within this release
                filtered_license_names = []
                filtered_license_texts = []
                
                for i, license_name in enumerate(release.get("license_names", [])):
                    clean_license_name = self.normalizer.normalize_name(license_name)
                    if clean_license_name in license_names:
                        filtered_license_names.append(license_name)
                        self.logger.info(f"Keeping license {clean_license_name} for component {release_name}")
                        # Also keep the corresponding license text if available
                        if i < len(release.get("license_texts", [])):
                            filtered_license_texts.append(release["license_texts"][i])
                    else:
                        self.logger.info(f"Removing license {clean_license_name} for component {release_name}")
                
                filtered_release["license_names"] = filtered_license_names
                filtered_release["license_texts"] = filtered_license_texts
                filtered_releases.append(filtered_release)
            else:
                self.logger.info(f"Removing component from releases: {release_name}")
                
        return filtered_releases
    
    def filter_license_texts(self, html_data, license_names):
        """
        Filter the license_texts section based on license names.
        
        Parameters:
        - html_data: The original HTML JSON data
        - license_names: Set of normalized license names to keep
        
        Returns:
        - Filtered license_texts list
        """
        filtered_license_texts = []
        
        for license_text in html_data.get("license_texts", []):
            title = license_text.get("title", "")
            license_name = self.normalizer.normalize_name(title)
            
            if license_name in license_names:
                filtered_license_texts.append(license_text)
                self.logger.info(f"Keeping license in license_texts: {license_name}")
            else:
                self.logger.info(f"Removing license from license_texts: {license_name}")
                
        return filtered_license_texts
    
    def filter_html_content(self, html_data, filtered_components, filtered_licenses):
        """
        Filter HTML content based on filtered components and licenses.
        
        Parameters:
        - html_data: The original HTML JSON data
        - filtered_components: List of component names/objects that should remain
        - filtered_licenses: List of license names/objects that should remain
        
        Returns:
        - Filtered HTML data
        """
        # Extract normalized names
        component_names = self.extract_component_names(filtered_components)
        license_names = self.extract_license_names(filtered_licenses)
        
        self.logger.info(f"Filtered component names: {component_names}")
        self.logger.info(f"Filtered license names: {license_names}")
        
        # Create the result structure
        result = {
            "release_overview": self.filter_release_overview(html_data, component_names),
            "releases": self.filter_releases(html_data, component_names, license_names),
            "license_texts": self.filter_license_texts(html_data, license_names)
        }
        
        return result


# Example usage:
def filter_html_content(html_data, filtered_components, filtered_licenses):
    """
    Wrapper function to maintain backward compatibility
    """
    import logging
    logger = logging.getLogger(__name__)
    
    filter_handler = HtmlContentFilter(logger)
    return filter_handler.filter_html_content(html_data, filtered_components, filtered_licenses)


if __name__ == '__main__':
    # !!! 不要直接运行该程序

    with open("dependecies.json","w", encoding="utf-8" ) as f1:
        components = f1.read()
    shared = '1'
    # 筛选需要凭证的组件
    credential_required_components = filter_components_by_credential_requirement(
        components, shared['parsedHtml'], shared["riskAnalysis"])

    # # 筛选需要源代码的组件
    # source_code_required = filter_components_by_source_code_requirement(
    #     components, shared['parsedHtml'], shared["riskAnalysis"], required=True)

    # # 筛选低风险组件
    # low_risk_components = filter_components_by_risk_level(
    #     components, shared['parsedHtml'], shared["riskAnalysis"], risk_levels=['low'])