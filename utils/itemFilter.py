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