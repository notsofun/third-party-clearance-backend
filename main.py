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


def run_conversation(shared, user_reply=None):
    """
    驱动 GetUserConfirming 节点，支持外部传入 user_reply。
    返回 (是否全部确认完成, shared)
    """
    from nodes import GetUserConfirming

    confirming_node = GetUserConfirming()
    # 1. 准备待确认项
    prep_res = confirming_node.prep(shared)
    if prep_res is None:
        # 全部确认完毕
        return True, shared

    # 2. 执行确认（如果有用户输入则处理，否则返回待确认项）
    exec_res = confirming_node.exec(prep_res, user_input=user_reply)
    # exec_res 可能是 {"need_user_input": True, ...} 或 {"result": ..., "idx": ...}
    post_res = confirming_node.post(shared, prep_res, exec_res)

    # 3. 判断是否结束
    is_complete = post_res == "over"
    # 记录本次回复
    shared["last_reply"] = exec_res

    return is_complete, shared

if __name__ == '__main__':
    shared = run_analysis(r"C:\Users\z0054unn\Downloads\LicenseInfo-Siemens Connected Home V4.0-RCR111ZB-2025-07-30_05_55_03.html")
    # user_reply = "trial"
    # run_conversation(shared, user_reply)
