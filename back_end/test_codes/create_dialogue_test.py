# 创建一个对话测试文件 dialog_tests/test_obligations.json
import json
import os
from pathlib import Path

# 确保目录存在
dialog_dir = Path(r"back_end\test_codes\test_dialogue")
dialog_dir.mkdir(exist_ok=True)

# 创建示例对话测试
test_dialog = {
    "name": "License Obligations Flow",
    "description": "To test the ability of generating obligations for a system",
    "initial_state": "obligations",
    "turns": [
        {
            "user_input": "OK, show me the first subtitle",
            "expected_status": "obligations",
            "check_keys": ["generated_obligations"],
            "verify_response_contains": ["license", "obligation"]
        },
        {
            "user_input": "ok, next, please",
            "expected_status": "obligations",
            "follow_up_if_continue": "Here's additional information about distribution"
        },
        {
            "user_input": "show me the obligation",
            "expected_status": "common_rules",
            "check_keys": ["generated_common_rules"]
        },
        {
            "user_input": "I am not satisfied with it, generate again",
            "expected_status": "common_rules",
            "verify_response_contains": ["rules", "requirements"]
        },
        {
            "user_input": "Show me the licenses",
            "expected_status": "component_overview"
        },
        {
            "user_input": "ok, next, please",
            "expected_status": "obligations",
            "follow_up_if_continue": "Here's additional information about distribution"
        },
        {
            "user_input": "ok, next, please",
            "expected_status": "obligations",
            "follow_up_if_continue": "Here's additional information about distribution"
        },
        {
            "user_input": "ok, next, please",
            "expected_status": "obligations",
            "follow_up_if_continue": "Here's additional information about distribution"
        },
        {
            "user_input": "ok, next, please",
            "expected_status": "obligations",
            "follow_up_if_continue": "Here's additional information about distribution"
        },
        {
            "user_input": "ok, next, please",
            "expected_status": "obligations",
            "follow_up_if_continue": "Here's additional information about distribution"
        },
        {
            "user_input": "ok, next, please",
            "expected_status": "obligations",
            "follow_up_if_continue": "Here's additional information about distribution"
        },
        {
            "user_input": "ok, next, please",
            "expected_status": "obligations",
            "follow_up_if_continue": "Here's additional information about distribution"
        },
    ]
}

# 保存到文件
dialog_path = dialog_dir / "test_obligations.json"
with open(dialog_path, 'w', encoding='utf-8') as f:
    json.dump(test_dialog, f, indent=2)

print(f"The file is save in the path: {dialog_path}")