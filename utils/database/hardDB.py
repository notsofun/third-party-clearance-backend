
# 如果导入路径有问题，您可以添加以下代码
import sys
sys.path.append(r'C:\Users\z0054unn\Documents\Siemens-GitLab\Third-party\third-party-clearance')
from utils.database.baseDB import TYPE, BaseDatabase
from utils.LLM_Analyzer import RelevanceChecker, LicRelevanceChecker
from log_config import configure_logging, get_logger
from utils.itemFilter import ContentNormalizer

configure_logging()
logger = get_logger(__name__)

import json
import os
from pathlib import Path
class HardDB(BaseDatabase):

    def __init__(self, default_type=TYPE.TYPE_LICENSE.value, db_path="database/hardDB/hard_database.json"):
        super().__init__(default_type)
        self.db_path = db_path
        self.data = []  # 存储所有数据项
        self.rel = RelevanceChecker(session_id='relevancyChecker')
        self.lic_rel = LicRelevanceChecker(session_id='lic_relevancyChecker')

    def build_index(self, data_dict, data_type=None):
        """构建索引并存储为JSON文件
        
        Args:
            data_dict: 数据字典或XML内容
            data_type: 数据类型，默认使用类初始化时设置的类型
        
        Returns:
            新添加的数据项数量
        """
        if data_type is None:
            data_type = self.default_type
        
        processor_method = getattr(self, f"_process_{data_type}_data", None)
        if not processor_method:
            raise ValueError(f"不支持此数据类型: {data_type}")
        
        # 处理数据
        items = processor_method(data_dict)
        
        # 如果是单个字典（XML处理返回），将其包装为列表
        if isinstance(items, dict):
            items = [items]
        
        # 添加数据类型标记
        for item in items:
            item['_data_type'] = data_type
        
        # 将新数据添加到现有数据中
        self.data.extend(items)
        
        # 将数据保存为JSON
        self._save_data()
        
        return len(items)
    
    def _save_data(self):
        """将数据保存到JSON文件"""
        # 确保目录存在
        os.makedirs(os.path.dirname(self.db_path) or '.', exist_ok=True)
        
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def load(self):
        """加载JSON数据库文件
        
        Returns:
            bool: 加载是否成功
        """
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
                # print(f"成功加载数据库，包含 {len(self.data)} 个项目")
                return True
            except Exception as e:
                print(f"加载数据库出错: {e}")
                return False
        else:
            print(f"数据库文件不存在: {self.db_path}")
            return False
    
    def batch_process_xml_files(self, folder_path, save_interval=10):
        """批量处理文件夹中的XML文件并构建索引
        
        Args:
            folder_path: 包含XML文件的文件夹路径
            save_interval: 每处理多少个文件保存一次数据库，默认为10
        
        Returns:
            处理成功的文件数量
        """
        import glob
        import os
        
        # 查找所有XML文件
        xml_files = glob.glob(os.path.join(folder_path, "*.xml"))
        
        total_files = len(xml_files)
        print(f"找到 {total_files} 个XML文件，开始批量处理...")
        
        success_count = 0
        
        for i, xml_path in enumerate(xml_files, 1):
            try:
                with open(xml_path, 'r', encoding='utf-8') as f:
                    xml_content = f.read()
                
                print(f"处理XML文件 ({i}/{total_files}): {os.path.basename(xml_path)}")
                self.build_index(xml_content, data_type=TYPE.TYPE_XML.value)
                success_count += 1
                
                # 每处理指定数量的文件保存一次
                if i % save_interval == 0 or i == total_files:
                    print(f"已处理 {i}/{total_files} 个文件，保存数据库...")
                    self._save_data()
                    
            except Exception as e:
                print(f"处理文件 {xml_path} 出错: {e}")
        
        print(f"批量处理完成: 成功 {success_count}/{total_files} 个文件")
        return success_count

    def _base_query(self, query_func):
        """基础查询方法，使用提供的函数过滤数据项
        
        Args:
            query_func: 一个接受数据项并返回布尔值的函数
        
        Returns:
            符合条件的数据项列表
        """
        return [item for item in self.data if query_func(item)]

    def find_by_component_name(self, comp_name):
        """根据组件名称模糊查找项目
        
        实现模糊匹配，处理以下情况：
        1. 组件名称包含搜索词
        2. 搜索词包含组件名称
        
        Args:
            comp_name: 要查找的组件名称或关键词
        
        Returns:
            符合模糊匹配条件的数据项列表
        """
        def query(item):
            if item.get('_data_type') == TYPE.TYPE_XML.value:
                # 获取组件名称
                item_comp_name = item.get('component_name', item.get('component', '')).lower()
                search_term = comp_name.lower()
                
                # 方法1: 使用rel.check方法判断
                rel_result = self.rel.check(search_term, item_comp_name)
                if rel_result == 'true':
                    return True
                    
                # 方法2: 硬编码方法判断
                def hard_coded_check(search, target):
                    # 简单包含关系判断
                    if search in target or target in search:
                        return True
                    
                    norm_search = ContentNormalizer.normalize_name(search)
                    norm_target = ContentNormalizer.normalize_name(target)
                    
                    # 检查标准化后的名称是否有包含关系
                    return (norm_search in norm_target or
                        norm_target in norm_search or
                        (("freertos" in norm_search and "freertos" in norm_target)))
                
                # 执行硬编码检查
                hard_coded_result = hard_coded_check(search_term, item_comp_name)
                
                # 只要任一方法返回True，整体就返回True
                return hard_coded_result
                
            return False
        
        return self._base_query(query)
    
    def find_license_by_component(self, comp_name, license_type="global", other = False):
        """查找指定组件的特定类型的许可证
        
        Args:
            comp_name: 组件名称
            license_type: 许可证类型，默认为 "global"
        
        Returns:
            符合条件的许可证名称列表
        """
        components = self.find_by_component_name(comp_name)
        
        unique_licenses = self.get_unique_licenses(comp_name)
        
        if other:
            filtered_licenses = self.filter_other_licenses(unique_licenses)
            return [lic.get('name') for lic in filtered_licenses if lic.get('name')]
        else:
            filtered_licenses = self.filter_licenses_by_type(unique_licenses, license_type)
            return [lic.get('name') for lic in filtered_licenses if lic.get('name')]

    def get_unique_licenses(self, comp_name:str):
        """提取组件列表中的所有许可证并按照name和content去重
        Args:
            components: 组件名称
        Returns:
            去重后的许可证列表
        """
        licenses = []
        unique_pairs = set()
        components = self.find_by_component_name(comp_name)
        logger.info('this is the found components')

        for comp in components:
            if 'licenses' in comp and isinstance(comp['licenses'], list):
                for lic in comp['licenses']:
                    name = lic.get('name')
                    # content = lic.get('content')
                    
                    if (name) not in unique_pairs:
                        unique_pairs.add((name))
                        licenses.append(lic)
        
        return licenses

    def filter_licenses_by_type(self, licenses, license_type):
        """从许可证列表中筛选特定类型的许可证
        Args:
            licenses: 许可证列表
            license_type: 许可证类型
        Returns:
            符合条件的许可证列表
        """
        return [lic for lic in licenses if lic.get('type') == license_type]
    
    def filter_other_licenses(self, licenses):
        """从许可证列表中筛选特定类型的许可证
        Args:
            licenses: 许可证列表
            license_type: 许可证类型
        Returns:
            符合条件的许可证列表
        """
        return [lic for lic in licenses if lic.get('type') != 'global']
    
    def is_COTS(self, comp_name):
        """查找指定组件的特定类型的许可证
        
        Args:
            comp_name: 组件名称
        
        Returns:
            是否为商业组件
        """
        components = self.find_by_component_name(comp_name)
        
        for comp in components:
            if comp.get('COTS') == True:
                return True
            else:
                return False
    
    def get_general_assessment(self, comp_name):
        '''获得对应组件的通用描述'''
        components = self.find_by_component_name(comp_name)
        
        for comp in components:
            if comp.get('general_assessment', '') != '':
                return comp['general_assessment']
        
        logger.info(f'We have not found the general assessment for {comp_name}')

    def get_additional_nots(self, comp_name):
        '''获得对应组件的通用描述'''
        components = self.find_by_component_name(comp_name)
        
        for comp in components:
            if comp.get('additional_notes', '') != '':
                return comp['additional_notes']
        
        logger.info(f'We have not found the additional notes for {comp_name}')

    def find_obligations_by_license(self, license_name):
        """查找与指定许可证相关的所有义务
        
        Args:
            license_name: 许可证名称
        
        Returns:
            义务主题列表
        """
        obligations = []
        
        for item in self.data:
            if item.get('_data_type') != TYPE.TYPE_XML.value:
                continue
                
            for obligation in item.get('obligations', []):
                if license_name in obligation.get('licenses', []):
                    obligations.append(obligation.get('topic'))
        
        return list(set(obligations))  # 去重
    
    def find_components_by_license(self, license_name):
        """查找使用指定许可证的所有组件
        
        Args:
            license_name: 许可证名称
        
        Returns:
            组件名称列表
        """
        components = []
        
        for item in self.data:
            if item.get('_data_type') != TYPE.TYPE_XML.value:
                continue
                
            has_license = False
            for lic in item.get('licenses', []):
                mat = self.lic_rel.check(license_name, lic.get('name'))
                if mat == 'true':
                    has_license = True
                    break
            
            if has_license and 'component_name' in item:
                components.append(item['component_name'])
        
        return list(set(components))  # 去重
    
    def get_license_content(self, license_name):
        """获取指定许可证的内容
        
        Args:
            license_name: 许可证名称
        
        Returns:
            许可证内容或None（如果未找到）
        """
        for item in self.data:
            if item.get('_data_type') != TYPE.TYPE_XML.value:
                continue
                
            for lic in item.get('licenses', []):
                if lic.get('name') == license_name and 'content' in lic:
                    return lic['content']
        
        return None
    
    def search_text(self, text_query):
        """在所有字段中搜索文本
        
        Args:
            text_query: 要搜索的文本
        
        Returns:
            匹配的数据项列表
        """
        results = []
        
        def search_in_dict(d, query):
            """递归搜索字典中的文本"""
            for k, v in d.items():
                if isinstance(v, str) and query.lower() in v.lower():
                    return True
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict) and search_in_dict(item, query):
                            return True
                        elif isinstance(item, str) and query.lower() in item.lower():
                            return True
                elif isinstance(v, dict) and search_in_dict(v, query):
                    return True
            return False
        
        for item in self.data:
            if search_in_dict(item, text_query):
                results.append(item)
        
        return results
    
    def get_stats(self):
        """获取数据库统计信息"""
        stats = {
            "total_items": len(self.data),
            "license_items": 0,
            "xml_items": 0,
            "unique_components": set(),
            "unique_licenses": set()
        }
        
        for item in self.data:
            if item.get('_data_type') == TYPE.TYPE_LICENSE.value:
                stats["license_items"] += 1
                if "license" in item:
                    stats["unique_licenses"].add(item["license"])
            elif item.get('_data_type') == TYPE.TYPE_XML.value:
                stats["xml_items"] += 1
                if "component_name" in item:
                    stats["unique_components"].add(item["component_name"])
                for lic in item.get('licenses', []):
                    if "name" in lic:
                        stats["unique_licenses"].add(lic["name"])
        
        # 转换集合为计数
        stats["unique_components"] = len(stats["unique_components"])
        stats["unique_licenses"] = len(stats["unique_licenses"])
        
        return stats
    
if __name__ == '__main__':

    # 创建实例
    db = HardDB(default_type=TYPE.TYPE_XML.value)

    # 批量处理XML文件
    xml_folder_path = "../third-party-clearance/data"
    db.batch_process_xml_files(xml_folder_path, save_interval=5)

    # 加载已有的数据库
    # db.load()

    # 查询特定组件的全局许可证
    # uniqueList = db.get_unique_licenses('GNU GNU Arm Embedded Toolchain Runtime Library   Partial for EmbeddedV')
    # # print(f'complete list is {uniqueList}')
    # true_list = [lic['name'] for lic in uniqueList]
    # print(f'查询到的单一许可证列表是{true_list}')
    # global_licenses = db.find_license_by_component("Amazon FreeRTOS-Kernel", "global")
    # print(f"查询组件的全局许可证: {global_licenses}")

    # is_STM = db.is_COTS('STM32Cube G0xx HAL Driver')
    # print(f'是否为商业组件？{is_STM}')

    # # 查找使用特定许可证的所有组件
    # components = db.find_components_by_license("Apache-2.0")
    # print(f"使用 Apache-2.0 许可证的组件: {components}")

    # # 获取数据库统计信息
    # stats = db.get_stats()
    # print(f"数据库统计: {stats}")