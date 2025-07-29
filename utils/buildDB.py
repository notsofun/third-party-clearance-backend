import os
import json
import glob
from utils.vectorDB import VectorDatabase

def main():
    # 初始化向量数据库
    db = VectorDatabase(dimension=3072)
    
    # 尝试加载已有的数据库
    try:
        db.load("LicenseTable")
        print("成功加载现有数据库")
    except FileNotFoundError:
        print("没有找到现有数据库，将创建新数据库")
    
    # # 处理license表格数据
    # license_data_path = "path/to/license_table.json"
    # if os.path.exists(license_data_path):
    #     try:
    #         with open(license_data_path, 'r', encoding='utf-8') as f:
    #             license_data = json.load(f)
            
    #         print(f"处理license表格数据...")
    #         db.build_index(license_data, data_type=VectorDatabase.TYPE_LICENSE)
    #         print("License数据处理完成，保存数据库...")
    #         db.save("component_licenses_db")
    #     except Exception as e:
    #         print(f"处理license数据出错: {e}")
    
    # 批量处理XML文件
    xml_folder_path = "../third-party-clearance/data"
    xml_files = glob.glob(os.path.join(xml_folder_path, "*.xml"))
    print(xml_files)


    total_files = len(xml_files)
    print(f"找到 {total_files} 个XML文件，开始批量处理...")
    
    for i, xml_path in enumerate(xml_files, 1):
        try:
            with open(xml_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            print(f"处理XML文件 ({i}/{total_files}): {os.path.basename(xml_path)}")
            db.build_index(xml_content, data_type=VectorDatabase.TYPE_XML)
            
            # 每处理10个文件保存一次
            if i % 10 == 0 or i == total_files:
                print(f"已处理 {i}/{total_files} 个文件，保存数据库...")
                db.save("component_licenses_db")
        except Exception as e:
            print(f"处理文件 {xml_path} 出错: {e}")
    
    print("所有文件处理完成，数据库已保存")
    
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