import xml.etree.ElementTree as ET
from enum import Enum

class TYPE(Enum):
    TYPE_LICENSE = 'license'
    TYPE_XML = 'xml'

class BaseDatabase:
    """
    实例化使用时需要用load()去加载数据库，否则无法查询
    支持根据不同类型数据去处理向量并实现增量积累
    
    """

    def __init__(self, default_type = TYPE.TYPE_LICENSE.value):
        self.default_type = default_type
        

    def _process_license_data(self, data_dict):
        """处理license类型的数据字典"""
        items = []
        # 把数据从嵌套展开到平铺
        for color_category, details in data_dict.items():
            licenses = details.get("licenses", [])
            for license_name in licenses:
                item = {
                    'license': license_name,
                    'color_category': color_category,
                    'risk_level': details.get('risk_level', ''),
                    'risk_reason': details.get('risk_reason', ''),
                    'obligations': details.get('obligations', '')
                }
                items.append(item)
        return items

    def _process_xml_data(self, xml_content):
        """处理XML格式的组件许可证信息
        外界调用的化，用with打开后，将xml文件的path加一个.read()就可以传进这个函数了
        """
        items = []
        
        try:
            # 解析XML内容
            root = ET.fromstring(xml_content)
            
            fileName = root.get('component', '')

            component_info = {
                'component': fileName,
                'creator': root.get('creator', ''),
                'date': root.get('date', ''),
                'componentSHA1': root.get('componentSHA1', ''),
                'version': root.get('Version', ''),
                'licenses': [],
                'COTS': True if 'COTS' in fileName else False,
                'obligations': [],
                'copyrights': []
            }

            general_info = root.find("GeneralInformation")
            if general_info is not None:
                # 处理ComponentName
                name_elem = general_info.find("ComponentName")
                if name_elem is not None and name_elem.text:
                    component_info['component_name'] = name_elem.text.strip()
                
                # 处理ComponentVersion
                version_elem = general_info.find("ComponentVersion")
                if version_elem is not None and version_elem.text:
                    component_info['component_version'] = version_elem.text.strip()
                
                # 处理ComponentId
                comp_id = general_info.find("ComponentId")
                if comp_id is not None:
                    id_type = comp_id.find("Type")
                    id_value = comp_id.find("Id")
                    if id_type is not None and id_type.text and id_value is not None and id_value.text:
                        component_info['component_id_type'] = id_type.text.strip()
                        component_info['component_id'] = id_value.text.strip()
            
            # 提取评估摘要
            assessment_summary = root.find("AssessmentSummary")
            if assessment_summary is not None:
                assessment = assessment_summary.find("GeneralAssessment")
                if assessment is not None and assessment.text:
                    component_info['general_assessment'] = assessment.text.strip()
                
                critical_files = assessment_summary.find("CriticalFilesFound")
                if critical_files is not None and critical_files.text:
                    component_info['critical_files_found'] = critical_files.text.strip()
            
            # 处理许可证信息
            for license_elem in root.findall("License"):
                license_info = {
                    'name': license_elem.get('name', ''),
                    'type': license_elem.get('type', ''),
                    'spdxidentifier': license_elem.get('spdxidentifier', ''),
                    'content': '',
                    'files': [],
                    'file_hash': '',
                    'tags': []
                }
                
                # 提取许可证内容
                content_elem = license_elem.find("Content")
                if content_elem is not None and content_elem.text:
                    license_info['content'] = content_elem.text.strip()
                
                # 提取关联文件
                files_elem = license_elem.find("Files")
                if files_elem is not None and files_elem.text:
                    license_info['files'] = files_elem.text.strip().split("\n")
                    license_info['files_count'] = len(license_info['files'])
                
                # 提取文件哈希
                file_hash_elem = license_elem.find("FileHash")
                if file_hash_elem is not None and file_hash_elem.text:
                    license_info['file_hash'] = file_hash_elem.text.strip()
                
                # 添加到组件的licenses列表
                component_info['licenses'].append(license_info)
            
            # 处理义务信息
            for obligation in root.findall("Obligation"):
                obligation_info = {
                    'topic': '',
                    'text': '',
                    'licenses': []
                }
                
                topic_elem = obligation.find("Topic")
                if topic_elem is not None and topic_elem.text:
                    obligation_info['topic'] = topic_elem.text.strip()
                
                text_elem = obligation.find("Text")
                if text_elem is not None and text_elem.text:
                    obligation_info['text'] = text_elem.text.strip()
                
                # 获取相关许可证
                licenses_elem = obligation.find("Licenses")
                if licenses_elem is not None:
                    for lic in licenses_elem.findall("License"):
                        if lic.text:
                            obligation_info['licenses'].append(lic.text.strip())
                
                # 添加到组件的obligations列表
                component_info['obligations'].append(obligation_info)

            # 处理版权信息
            for copyright_elem in root.findall("Copyright"):
                copyright_info = {
                    'content': '',
                    'files': [],
                    'file_hash': ''
                }
                
                content_elem = copyright_elem.find("Content")
                if content_elem is not None and content_elem.text:
                    copyright_info['content'] = content_elem.text.strip()
                
                files_elem = copyright_elem.find("Files")
                if files_elem is not None and files_elem.text:
                    copyright_info['files'] = files_elem.text.strip().split("\n")
                
                file_hash_elem = copyright_elem.find("FileHash")
                if file_hash_elem is not None and file_hash_elem.text:
                    copyright_info['file_hash'] = file_hash_elem.text.strip()
                
                # 添加到组件的copyrights列表
                component_info['copyrights'].append(copyright_info)
            
            return component_info
        
        except Exception as e:
            print(f"Something wrong with processing xml data: {e}")
        
        return items

    def _serialize_item(self, item):
        """基于数据类型选择合适的序列化方法"""
        data_type = item.get('_data_type', self.TYPE_LICENSE)
        if data_type == TYPE.TYPE_LICENSE.value:
            return self._serialize_license_item(item)
        elif data_type == TYPE.TYPE_XML.value:
            return self._serialize_xml_item(item)
        else:
            # 默认序列化方法
            return "; ".join(f"{k}: {v}" for k, v in item.items() if k != '_data_type')

    def _serialize_license_item(self, item):
        """将license类型的条目序列化为文本"""
        obligations = item.get('obligations', '')
        if isinstance(obligations, list):
            obligations = "；".join(obligations)

        return (
            f"License Name: {item.get('license', '')}; "
            f"Color Category: {item.get('color_category', '')}; "
            f"Risk Level: {item.get('risk_level', '')}; "
            f"Risk Reason: {item.get('risk_reason', '')}; "
            f"Obligations: {obligations}."
        )
    
    def _serialize_xml_item(self, item):
        """将XML类型的条目序列化为文本"""
        fields = []
        
        # 组件信息
        if 'component_name' in item:
            fields.append(f"Component: {item['component_name']}")
        if 'component_version' in item:
            fields.append(f"Version: {item['component_version']}")
            
        # 许可证信息
        if 'license_name' in item:
            fields.append(f"License: {item['license_name']}")
        if 'license_spdx' in item:
            fields.append(f"SPDX: {item['license_spdx']}")
        if 'license_type' in item:
            fields.append(f"Type: {item['license_type']}")
            
        # 义务信息
        if 'obligation_topic' in item:
            fields.append(f"Obligation: {item['obligation_topic']}")
        if 'obligation_text' in item:
            # 限制义务文本长度
            text = item['obligation_text']
            if len(text) > 300:
                text = text[:300] + "..."
            fields.append(f"Details: {text}")
            
        # 其他信息
        if 'assessment' in item:
            fields.append(f"Assessment: {item['assessment']}")
        if 'files_count' in item:
            fields.append(f"Files: {item['files_count']}")
            
        return "; ".join(fields)