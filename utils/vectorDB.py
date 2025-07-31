from utils.callAIattack import AzureOpenAIChatClient
import numpy as np
import faiss
import pickle
import os
import xml.etree.ElementTree as ET

class VectorDatabase:
    """
    实例化使用时需要用load()去加载数据库，否则无法查询
    支持根据不同类型数据去处理向量并实现增量积累
    
    """
    TYPE_LICENSE = 'license'
    TYPE_XML = 'xml'

    def __init__(self,dimension=3072):
        self.dimension = dimension
        self.client = AzureOpenAIChatClient(embedding_deployment="text-embedding-3-large")
        self.index = None
        self.texts = []
        self.embedding = []
    
    def build_index(self, data_dict, data_type = TYPE_LICENSE):
        """最终的构建索引函数（数据平展化）
        目前支持
        xml和license文本"""
        processor_method = getattr(self, f"_process_{data_type}_data", None)
        if not processor_method:
            raise ValueError(f"This type has not been supported yet: {data_type}")
        
        items = processor_method(data_dict)
        new_embeddings = []
        new_texts = []

        for item in items:
            item['_data_type'] = data_type

            serialized_text = self._serialize_item(item)
            embedding = self.client.get_embedding(serialized_text)
            new_embeddings.append(embedding)
            new_texts.append(item)

        self.texts.extend(new_texts)
        self.embedding.extend(new_embeddings)

        if new_embeddings:
            new_embeddings_array = np.vstack(new_embeddings).astype('float32')

            if self.index is None:
                # 首次创建索引
                self.index = faiss.IndexFlatL2(self.dimension)
                all_embeddings = np.vstack(self.embedding).astype('float32')
                self.index.add(all_embeddings)
            else:
                self.index.add(new_embeddings_array)

        print(f"✅ 索引构建完成，共 {len(self.texts)} 个license条目被索引。")

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
        """处理XML格式的组件许可证信息"""
        items = []
        
        try:
            # 解析XML内容
            root = ET.fromstring(xml_content)
            
            # 提取基本信息
            component_name = ""
            component_version = ""
            general_info = root.find("GeneralInformation")
            if general_info is not None:
                name_elem = general_info.find("ComponentName")
                if name_elem is not None and name_elem.text:
                    component_name = name_elem.text.strip()
                    
                version_elem = general_info.find("ComponentVersion")
                if version_elem is not None and version_elem.text:
                    component_version = version_elem.text.strip()
            
            # 提取评估摘要
            assessment_text = ""
            assessment = root.find("AssessmentSummary/GeneralAssessment")
            if assessment is not None and assessment.text:
                assessment_text = assessment.text.strip()
            
            # 处理许可证信息
            for license_elem in root.findall("License"):
                license_name = license_elem.get("name", "")
                license_type = license_elem.get("type", "")
                spdx_id = license_elem.get("spdxidentifier", "")
                
                # 提取许可证内容摘要
                content = ""
                content_elem = license_elem.find("Content")
                if content_elem is not None and content_elem.text:
                    # 只取前200个字符作为摘要
                    content = content_elem.text[:200] + "..."
                
                # 提取关联文件数量
                files_count = 0
                files_elem = license_elem.find("Files")
                if files_elem is not None and files_elem.text:
                    files_count = len(files_elem.text.strip().split("\n"))
                
                item = {
                    'component_name': component_name,
                    'component_version': component_version,
                    'license_name': license_name,
                    'license_spdx': spdx_id,
                    'license_type': license_type,
                    'content_summary': content,
                    'files_count': files_count,
                    'assessment': assessment_text
                }
                items.append(item)
            
            # 处理义务信息
            for obligation in root.findall("Obligation"):
                topic = ""
                topic_elem = obligation.find("Topic")
                if topic_elem is not None and topic_elem.text:
                    topic = topic_elem.text.strip()
                
                text = ""
                text_elem = obligation.find("Text")
                if text_elem is not None and text_elem.text:
                    text = text_elem.text.strip()
                
                # 获取相关许可证
                licenses_elem = obligation.find("Licenses")
                if licenses_elem is not None:
                    for lic in licenses_elem.findall("License"):
                        if lic.text:
                            item = {
                                'component_name': component_name,
                                'component_version': component_version,
                                'obligation_topic': topic,
                                'obligation_text': text,
                                'license_name': lic.text.strip(),
                                'assessment': assessment_text
                            }
                            items.append(item)
        
        except Exception as e:
            print(f"Something wrong with processing xml data: {e}")
        
        return items

    def _serialize_item(self, item):
        """基于数据类型选择合适的序列化方法"""
        data_type = item.get('_data_type', self.TYPE_LICENSE)
        if data_type == self.TYPE_LICENSE:
            return self._serialize_license_item(item)
        elif data_type == self.TYPE_XML:
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

    def search(self,query, k=5):
        """搜索最相近的文本"""

        if self.index is None or len(self.texts) == 0:
            raise ValueError("索引未加载或为空，请先加载或构建索引")

        query_embedding = self.client.get_embedding(query)

        # 搜索最相似的向量
        distances, indices = self.index.search(
            query_embedding.reshape(1, -1).astype('float32'),
            k
        )
        
        # 返回结果
        results = []
        for i, (dist, idx) in enumerate(zip(distances[0], indices[0])):
            results.append({
                'text': self.texts[idx],
                'distance': float(dist),
                'rank': i + 1
            })
        
        return results
    

    def save(self, path):

        """保存索引、文本数据和嵌入向量"""

        os.makedirs("./database", exist_ok=True)

        # 保存文本数据和嵌入向量
        save_data = {
            'texts': self.texts,
            'embeddings': self.embedding
        }
        with open(f"./database/{path}.pkl", 'wb') as f:
            pickle.dump(save_data, f)
        # 保存索引
        if self.index:
            faiss.write_index(self.index, f"./database/{path}.faiss")
        print(f"✅ 数据库已保存到 ./database/{path}，共 {len(self.texts)} 条记录")

    def load(self, path):
        """加载索引、文本数据和嵌入向量"""
        if not os.path.exists(f"./database/{path}.pkl"):
            raise FileNotFoundError(f"数据库文件 ./database/{path}.pkl 不存在")
        
        try:
            # 加载文本数据和嵌入向量
            with open(f"./database/{path}.pkl", 'rb') as f:
                data = pickle.load(f)
                
                # 兼容旧格式
                if isinstance(data, list):
                    self.texts = data
                    self.embeddings = []
                    print("⚠️ 加载了旧格式数据，缺少嵌入向量信息")
                else:
                    self.texts = data.get('texts', [])
                    self.embeddings = data.get('embeddings', [])
            
            # 加载索引
            if os.path.exists(f"./database/{path}.faiss"):
                self.index = faiss.read_index(f"./database/{path}.faiss")
            else:
                print("⚠️ 未找到索引文件，将在需要时重建")
                self.index = None
                
            # 如果有文本但没有对应的嵌入向量，提醒用户需要重建
            if len(self.texts) > 0 and len(self.embeddings) == 0:
                print("⚠️ 检测到文本数据但没有对应的嵌入向量，建议使用rebuild_index()重建索引")
                
            print(f"✅ 成功加载数据库，包含 {len(self.texts)} 条记录")
            
            # 如果索引和文本数量不匹配，自动重建索引
            if self.index and self.index.ntotal != len(self.texts):
                print("⚠️ 索引和文本数量不匹配，自动重建索引")
                self.rebuild_index()
                # rebuild的时候没有save
                
        except Exception as e:
            raise RuntimeError(f"加载数据库失败: {e}")
    
    def rebuild_index(self):
        """重新构建整个索引"""
        if len(self.texts) == 0:
            print("没有文本数据，无法构建索引")
            return
            
        print(f"正在为 {len(self.texts)} 条记录重建索引...")
        
        # 如果没有预先计算的嵌入向量，需要重新计算
        if len(self.embeddings) != len(self.texts):
            print("计算所有文本的嵌入向量...")
            self.embeddings = []
            for item in self.texts:
                serialized_text = self._serialize_item(item)
                embedding = self.client.get_embedding(serialized_text)
                self.embeddings.append(embedding)
        
        # 构建新索引
        all_embeddings = np.vstack(self.embeddings).astype('float32')
        self.index = faiss.IndexFlatL2(self.dimension)
        self.index.add(all_embeddings)
        
        print(f"✅ 索引重建完成，包含 {self.index.ntotal} 个向量")

def main():
    license_info = {
        "Black": {
            "licenses": [
                "SleepyCat",
                "Aladdin Free Public License",
                "Berkeley DB licenses",
                "CC-BY-NC-2.0",
                "CC-BY-NC-SA-2.0", 
                "CC-BY-NC-SA-3.0",
                "CC-BY-NC-SA-4.0"
            ],
            "risk_level": "very high",
            "risk_reason": "nearly unlimited copy left effect",
            "obligations": "Before thinking about components licensed under these license, get in contact with your software clearing experts!"
        },
        "Blue": {
            "licenses": [
                "MIT",
                "BSD (except for BSD-4-Clause)",
                "BSL-1.0",
                "CPOL-1.02",
                "MsPL",
                "zLib",
                "Apache-1.1",
                "Apache-2.0 (if no code changes are done)",
                "APL-1.0",
                "APAFML",
                "ANTLR-PD",
                "AML",
                "Beerware",
                "bzip2-1.0.6",
                "CECILL-B",
                "MIT-CMU",
                "CPAL-1.0",
                "CC-PDDC",
                "CC0-1.0",
                "Cryptogams",
                "curl",
                "WTFPL",
                "EDL-1.0 (=BSD-3-Clause)",
                "EFL-1.0",
                "EFL-2.0",
                "FSAP",
                "FSFUL",
                "FSFULLR",
                "HPND",
                "HTMLTIDY",
                "ICU",
                "Info-ZIP",
                "ISC",
                "JSON",
                "libpng",
                "libpng-2.0",
                "libtiff",
                "NPL-1.0",
                "NTP",
                "OLDAP-2.0.1",
                "OLDAP-2.8",
                "OML",
                "PostGreSQL",
                "Public Domain",
                "SAX-PD",
                "SGI-B-2.0",
                "Spencer-94",
                "Spencer-99",
                "blessing",
                "TCL",
                "Unlicense",
                "UPL-1.0",
                "NCSA",
                "W3C-20150513",
                "X11",
                "zLib"
            ],
            "risk_level": "low",
            "risk_reason": "permissive licenses",
            "obligations": [
                "Display license text",
                "Display copyrights"
            ]
        },
        "Red": {
            "licenses": [
                "GPL-2.0",
                "GPL-3.0", 
                "LGPL-2.1",
                "LGPL-3.0",
                "AGPL",
                "APSL-2.0",
                "Artistic-2.0",
                "eCos-2.0",
                "RHeCos-1.1",
                "SSPL-1.0"
            ],
            "risk_level": "high",
            "risk_reason": "copyleft effect",
            "obligations": [
                "Display license text",
                "Display copyrights",
                "Take care about copyleft effect - get in contact with your software clearing experts",
                "All distributions must clearly state that (L)GPL license code is used"
            ]
        },
        "Yellow": {
            "licenses": [
                "CDDL-1.0",
                "CDDL-1.1",
                "CPL-1.0", 
                "EPL-1.0",
                "eCos License",
                "MPL",
                "NPL",
                "AFL-2.0",
                "AFL-2.1", 
                "AFL-3.0",
                "Artistic-1.0",
                "Artistic1.0-Perl",
                "CC-BY-SA-2.0",
                "CC-BY-SA-3.0",
                "CC-BY-SA-4.0",
                "CECILL-2.0",
                "CECILL-B",
                "CC-BY-2.0",
                "CC-BY-3.0", 
                "CC-BY-4.0",
                "EPL-2.0",
                "ErlPL-1.1",
                "FTL",
                "gnuplot",
                "IPL-1.0",
                "IJG",
                "MS-PL",
                "MS-RL",
                "NASA-1.3",
                "NPL-1.1",
                "ODbL-1.0",
                "OSL-1.1",
                "OpenSSL",
                "PHP-3.0",
                "PHP-3.01",
                "Python-2.0",
                "QHull",
                "RSA-MD",
                "SGI-B-1.1",
                "OFL-1.0",
                "OFL-1.1",
                "SPL-1.0",
                "Unicode-DFS-2015",
                "Unicode-DFS-2016",
                "Unicode-TOU",
                "W3C-19980720",
                "W3C",
                "wxWindows",
                "XFree86-1.1",
                "Zend-2.0",
                "ZPL-2.0",
                "ZPL-2.1"
            ],
            "risk_level": "medium",
            "risk_reason": "limited copyleft effect",
            "obligations": [
                "Display license text",
                "Display copyrights",
                "All changes of the component code must become OSS as well",
                "Possible license incompatibility with red licenses"
            ]
        }
    }
    
    db = VectorDatabase()
    db.build_index(license_info)
    db.save(r"LicenseTable")
    result = db.search("Sleep")
    print(result)

if __name__ == "__main__":
    main()