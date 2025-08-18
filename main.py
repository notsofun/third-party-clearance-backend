from flow import pre_chat_flow, post_chat_flow
import json
from utils.tools import load_json_files_as_variables

def run_analysis(html_path):
    """运行预处理流程"""
    shared = {"html_path": html_path}
    flow = pre_chat_flow()
    flow.run(shared)
    return shared

def run_report(shared):
    """运行报告生成流程"""
    flow = post_chat_flow()
    flow.run(shared)
    return shared

# 之后可以直接使用这些变量，例如：
# print(confirmed_licenses)  # 如果有 confirmed_licenses.json 文件

if __name__ == '__main__':
    shared = {}


    # 调用函数加载所有JSON文件
    json_data = load_json_files_as_variables()
    shared['filtered_components'] = json_data['confirmed_components']
    shared['filtered_licenses'] = json_data['confirmed_licenses']

    with open(r'parsed_original_oss.json', 'r', encoding='utf-8') as f:
        shared['parsedHtml'] = json.load(f)

    shared = run_report(shared)