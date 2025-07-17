import json
from utils.requestAIattack import AzureOpenAIChatClient
import time

class RiskReviewer:
    """
    License风险评审类
    支持不同模型引擎：如'rule', 'gpt', 'api'
    """

    def __init__(self, model='rule',deployment = None, **kwargs):
        """
        model: str, 指定模型类别，可以是'openai', 'rule', 'your_api'等
        kwargs: 其他init参数，如token等
        """
        self.model = model
        self.depoyment = deployment
        # 若模型需要API key/URL，可通过kwargs传入
        self.model_kwargs = kwargs

    def _evaluate_rule_based(self, title, text):
        """
        简单规则引擎（可更换成任意模型调用）
        """
        t = f"{title}\n\n{text}".lower()

        if 'agpl' in t or 'gpl v3' in t or 'gnu general public license version 3' in t:
            return {
                "level": "very high",
                "reason": "AGPL/GPLv3 nearly unlimited copyleft; not recommended for proprietary/commercial use."
            }
        elif 'gpl' in t:
            return {
                "level": "high",
                "reason": "GPL is strong copyleft, triggers copyleft clauses; not recommended unless compliance confirmed."
            }
        elif 'lgpl' in t or 'cddl' in t or 'mpl' in t or 'eclipse public license' in t:
            return {
                "level": "medium",
                "reason": "Limited copyleft (LGPL/MPL/CDDL/EPL); may require dynamic linking/certain compliance."
            }
        elif 'bsd' in t or 'mit' in t or 'apache' in t or 'public-domain' in t or 'cc0' in t:
            return {
                "level": "low",
                "reason": "Permissive license; minor restrictions (notice, attribution)."
            }
        elif 'dual-license' in t:
            return {
                "level": "medium",
                "reason": "Dual-license; need to check which applies in your context."
            }
        else:
            return {
                "level": "medium",
                "reason": "Unclassified or custom license, manual review required."
            }


    def _call_api(self, title, text):
        """
        纯调用API函数
        """
        llmReviewer = AzureOpenAIChatClient(deployment=self.depoyment)
        query = [
            {"role": "system", "content": """
                You are a License Risk Classifier that MUST output in strict JSON format.
                
                STRICT OUTPUT FORMAT:
                {
                    "level": <risk_level>,
                    "reason": <one_sentence_explanation>
                }
                
                RULES:
                1. ONLY use these risk levels:
                - "low" (for no copyleft)
                - "medium" (for limited copyleft)
                - "high" (for strong copyleft)
                - "very high - do not use -" (for network copyleft)
                
                2. 'reason' must be a single sentence explaining the risk level
                
                3. DO NOT include any other fields in the JSON
                4. DO NOT include any explanations outside the JSON
                5. DO NOT include the license name in the output
                6. ENSURE the output is valid JSON with ONLY 'level' and 'reason' fields
                
                Example correct output:
                {"level":"low","reason":"Permissive license without copyleft obligations"}
                """}, 
            {"role": "user", "content": f"Analyze this license:\nTitle: {title}\nText: {text}"}
        ]
        
        result = llmReviewer.chat(query)
        return result.choices[0].message.content

    def _evaluate_api(self, title, text):
        """
        验证并重试的函数
        """
        max_retries = 3
        attempt = 0
        
        while attempt < max_retries:
            try:
                content = self._call_api(title, text)
                response = json.loads(content)
                
                # 验证响应格式
                if not isinstance(response, dict):
                    raise ValueError("Response is not a dictionary")
                if set(response.keys()) != {"level", "reason"}:
                    raise ValueError("Response does not contain exactly 'level' and 'reason' keys")
                if not isinstance(response["level"], str) or not isinstance(response["reason"], str):
                    raise ValueError("Level or reason is not string")
                    
                valid_levels = {"low", "medium", "high", "very high - do not use -"}
                if response["level"].lower() not in valid_levels:
                    raise ValueError(f"Invalid level value: {response['level']}")
                    
                return response
                    
            except (json.JSONDecodeError, ValueError) as e:
                attempt += 1
                if attempt < max_retries:
                    print(f"验证失败，第{attempt}次重试... 错误: {e}")
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    print(f"达到最大重试次数，最后错误: {e}")
                    raise
                    
            except Exception as e:
                print(f"发生其他错误: {e}")
                raise

    def review(self, title, text):
        """
        主流程处理函数
        输出结构: {"level":..., "reason":...}
        """
        title = title.strip()
        
        try:
            if self.model == "rule":
                risk = self._evaluate_rule_based(title, text)
            elif self.model == "api":
                risk = self._evaluate_api(title, text)
            else:
                risk = {"level": "medium", "reason": "Unknown model, fallback review."}
                
            # 最后验证输出格式
            if not isinstance(risk, dict) or set(risk.keys()) != {"level", "reason"}:
                raise ValueError("Invalid risk assessment format")
                
            return risk
            
        except Exception as e:
            print(f"Review failed for {title}: {e}")
            # 可以选择返回默认值或继续抛出异常
            return {"level": "medium", "reason": f"Review failed: {str(e)}"}

    # def review_and_save(self, license_texts, output_json_path):
    #     risk_result = self.review(license_texts)

    #     return risk_result


# ------ 用法示例 ------
if __name__ == "__main__":
    # 假设 license_texts 从你的oss结构读取/分块提取
    license_texts = [
        {
            "id": "licenseTextItem1",
            "title": "1: Apache License 2.0↩",
            "text": "Apache License\n\nVersion 2.0, January 2004\n..."
        },
        # {
        #     "id": "licenseTextItem20",
        #     "title": "20: GNU General Public License v2.0 only",
        #     "text": "GNU General Public License, version 2\n\n..."
        # },
        # {
        #     "id": "licenseTextItem14",
        #     "title": "14: BSD-3-Clause",
        #     "text": "Redistribution and use in source and binary forms, ..."
        # }
    ]

    title1 = "1: Apache License 2.0↩"
    text1 = "Apache License\n\nVersion 2.0, January 2004\n..."
    # 实例化，并选择你要的评审方式
    reviewer = RiskReviewer(model="api")  # "rule", "gpt", "api"
    risk_json = reviewer.review(title=title1,text=text1)
    print(risk_json)
    print(json.dumps(risk_json, ensure_ascii=False, indent=2))