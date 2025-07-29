from flow import pre_chat_flow, chat_flow, post_chat_flow

def run_analysis(html_path):
    """运行预处理流程"""
    shared = {"html_path": html_path}
    flow = pre_chat_flow()
    flow.run(shared)
    return shared

def run_chat(shared):
    """运行对话流程"""
    flow = chat_flow()
    result = flow.run(shared)
    return result == "over", shared

def run_report(shared):
    """运行报告生成流程"""
    flow = post_chat_flow() 
    flow.run(shared)
    return shared

if __name__ == '__main__':
    run_analysis(r"C:\Users\z0054unn\Downloads\LicenseInfo-Core Backend-v1.0.0-2025-07-17_03_23_03.html")