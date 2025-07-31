import os
import json
import glob
from utils.vectorDB import VectorDatabase

def main():
    # 初始化向量数据库
    db = VectorDatabase(dimension=3072)
    
    # 尝试加载已有的数据库
    try:
        db.load("component_licenses_db")
        print("成功加载现有数据库")
    except FileNotFoundError:
        print("没有找到现有数据库，将创建新数据库")
    
#     # 处理license表格数据
#     try:
#         # with open(license_data_path, 'r', encoding='utf-8') as f:
#         #     license_data = json.load(f)
#         license_info = {
#     "Black": {
#         "licenses": [
#             "SleepyCat",
#             "Aladdin Free Public License",
#             "Berkeley DB licenses",
#             "CC-BY-NC-2.0",
#             "CC-BY-NC-SA-2.0", 
#             "CC-BY-NC-SA-3.0",
#             "CC-BY-NC-SA-4.0"
#         ],
#         "risk_level": "very high",
#         "risk_reason": "nearly unlimited copy left effect",
#         "obligations": "Before thinking about components licensed under these license, get in contact with your software clearing experts!"
#     },
#     "Blue": {
#         "licenses": [
#             "MIT",
#             "BSD (except for BSD-4-Clause)",
#             "BSL-1.0",
#             "CPOL-1.02",
#             "MsPL",
#             "zLib",
#             "Apache-1.1",
#             "Apache-2.0 (if no code changes are done)",
#             "APL-1.0",
#             "APAFML",
#             "ANTLR-PD",
#             "AML",
#             "Beerware",
#             "bzip2-1.0.6",
#             "CECILL-B",
#             "MIT-CMU",
#             "CPAL-1.0",
#             "CC-PDDC",
#             "CC0-1.0",
#             "Cryptogams",
#             "curl",
#             "WTFPL",
#             "EDL-1.0 (=BSD-3-Clause)",
#             "EFL-1.0",
#             "EFL-2.0",
#             "FSAP",
#             "FSFUL",
#             "FSFULLR",
#             "HPND",
#             "HTMLTIDY",
#             "ICU",
#             "Info-ZIP",
#             "ISC",
#             "JSON",
#             "libpng",
#             "libpng-2.0",
#             "libtiff",
#             "NPL-1.0",
#             "NTP",
#             "OLDAP-2.0.1",
#             "OLDAP-2.8",
#             "OML",
#             "PostGreSQL",
#             "Public Domain",
#             "SAX-PD",
#             "SGI-B-2.0",
#             "Spencer-94",
#             "Spencer-99",
#             "blessing",
#             "TCL",
#             "Unlicense",
#             "UPL-1.0",
#             "NCSA",
#             "W3C-20150513",
#             "X11",
#             "zLib"
#         ],
#         "risk_level": "low",
#         "risk_reason": "permissive licenses",
#         "obligations": [
#             "Display license text",
#             "Display copyrights"
#         ]
#     },
#     "Red": {
#         "licenses": [
#             "GPL-2.0",
#             "GPL-3.0", 
#             "LGPL-2.1",
#             "LGPL-3.0",
#             "AGPL",
#             "APSL-2.0",
#             "Artistic-2.0",
#             "eCos-2.0",
#             "RHeCos-1.1",
#             "SSPL-1.0"
#         ],
#         "risk_level": "high",
#         "risk_reason": "copyleft effect",
#         "obligations": [
#             "Display license text",
#             "Display copyrights",
#             "Take care about copyleft effect - get in contact with your software clearing experts",
#             "All distributions must clearly state that (L)GPL license code is used"
#         ]
#     },
#     "Yellow": {
#         "licenses": [
#             "CDDL-1.0",
#             "CDDL-1.1",
#             "CPL-1.0", 
#             "EPL-1.0",
#             "eCos License",
#             "MPL",
#             "NPL",
#             "AFL-2.0",
#             "AFL-2.1", 
#             "AFL-3.0",
#             "Artistic-1.0",
#             "Artistic1.0-Perl",
#             "CC-BY-SA-2.0",
#             "CC-BY-SA-3.0",
#             "CC-BY-SA-4.0",
#             "CECILL-2.0",
#             "CECILL-B",
#             "CC-BY-2.0",
#             "CC-BY-3.0", 
#             "CC-BY-4.0",
#             "EPL-2.0",
#             "ErlPL-1.1",
#             "FTL",
#             "gnuplot",
#             "IPL-1.0",
#             "IJG",
#             "MS-PL",
#             "MS-RL",
#             "NASA-1.3",
#             "NPL-1.1",
#             "ODbL-1.0",
#             "OSL-1.1",
#             "OpenSSL",
#             "PHP-3.0",
#             "PHP-3.01",
#             "Python-2.0",
#             "QHull",
#             "RSA-MD",
#             "SGI-B-1.1",
#             "OFL-1.0",
#             "OFL-1.1",
#             "SPL-1.0",
#             "Unicode-DFS-2015",
#             "Unicode-DFS-2016",
#             "Unicode-TOU",
#             "W3C-19980720",
#             "W3C",
#             "wxWindows",
#             "XFree86-1.1",
#             "Zend-2.0",
#             "ZPL-2.0",
#             "ZPL-2.1"
#         ],
#         "risk_level": "medium",
#         "risk_reason": "limited copyleft effect",
#         "obligations": [
#             "Display license text",
#             "Display copyrights",
#             "All changes of the component code must become OSS as well",
#             "Possible license incompatibility with red licenses"
#         ]
#     }
# }

#         print(f"处理license表格数据...")
#         db.build_index(license_info, data_type=VectorDatabase.TYPE_LICENSE)
#         print("License数据处理完成，保存数据库...")
#         db.save("component_licenses_db")
#     except Exception as e:
#         print(f"处理license数据出错: {e}")
    
#     # 批量处理XML文件
#     xml_folder_path = "../third-party-clearance/data"
#     xml_files = glob.glob(os.path.join(xml_folder_path, "*.xml"))

#     total_files = len(xml_files)
#     print(f"找到 {total_files} 个XML文件，开始批量处理...")
    
#     for i, xml_path in enumerate(xml_files, 1):
#         try:
#             with open(xml_path, 'r', encoding='utf-8') as f:
#                 xml_content = f.read()
            
#             print(f"处理XML文件 ({i}/{total_files}): {os.path.basename(xml_path)}")
#             db.build_index(xml_content, data_type=VectorDatabase.TYPE_XML)
            
#             # 每处理10个文件保存一次
#             if i % 10 == 0 or i == total_files:
#                 print(f"已处理 {i}/{total_files} 个文件，保存数据库...")
#                 db.save("component_licenses_db")
#         except Exception as e:
#             print(f"处理文件 {xml_path} 出错: {e}")
    
#     print("所有文件处理完成，数据库已保存")
    
    # 测试一个查询
    if db.index:
        query = "What are the obligations for Apache-2.0 license?"
        results = db.search(query, k=3)
        print(f"\n查询: '{query}'")
        print("=" * 50)
        for i, result in enumerate(results):
            print(f"结果 #{i+1} (距离: {result['distance']:.4f}):")
            text = result['text']
            data_type = text.get('_data_type')
            
            if data_type == VectorDatabase.TYPE_LICENSE:
                print(f"- 许可证: {text.get('license', 'N/A')}")
                print(f"- 风险等级: {text.get('risk_level', 'N/A')}")
            elif data_type == VectorDatabase.TYPE_XML:
                if 'license_name' in text:
                    print(f"- 组件: {text.get('component_name', 'N/A')}")
                    print(f"- 许可证: {text['license_name']}")
                elif 'obligation_topic' in text:
                    print(f"- 义务: {text['obligation_topic']}")
            print("-" * 30)

if __name__ == "__main__":
    main()