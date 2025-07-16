import json
from utils.requestAIattack import AzureOpenAIChatClient

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


    def _evaluate_api(self, title, text):
        """
        示例：支持你自己的API接口调用
        输出：
        {
            "Apache License 2.0": {
                "level": "low",
                "reason": "Permissive license without copyleft obligations"
            }
        }
        """
        # code here, eg requests.post/...
        llmReviewer = AzureOpenAIChatClient(deployment=self.depoyment)
        query = [
            {"role": "system", "content": """ 
            Role: Software License Risk Classifier  
            Input: Process `execRes.LicenseTexts` array containing license entries  
            Output: Pure JSON dictionary where keys are cleaned license titles (remove IDs/symbols like "↩", keep versions)  

            For each license:  
            1. Analyze copyleft effects from text  
            2. Assign risk level:  
            - `"low"` (no copyleft)  
            - `"medium"` (limited copyleft)  
            - `"high"` (strong copyleft)  
            - `"very high - do not use -"` (network copyleft)  
            3. Add 1-sentence `reason` justifying risk level  
            4. Output ONLY valid JSON - no explanations  

            Example output format:  
            {"level":"low","reason":"Permissive license without copyleft obligations"}
            """},
            {"role": "user", "content": f"here is title: {title}, and here is the text: {text}"}
        ]
        result = llmReviewer.chat(query)
        response = json.loads(result.choices[0].message.content)
        return response


    def review(self, license_texts):
        """
        参数 license_texts: 形如 [{'id': ..., 'title': ..., 'text': ...}, ...]
        输出结构: {license_title: {"level":..., "reason":...}, ...}
        """
        results = {}
        for item in license_texts:
            title = item.get("title", "").strip()
            text = item.get("text", "")
            if self.model == "rule":
                risk = self._evaluate_rule_based(title, text)
            elif self.model == "api":
                risk = self._evaluate_api(title, text)
            else:
                risk = {"level": "medium", "reason": "Unknown model, fallback review."}
            results[title] = risk

        return results

    def review_and_save(self, license_texts, output_json_path):
        risk_result = self.review(license_texts)
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(risk_result, f, ensure_ascii=False, indent=2)
        return risk_result


# ------ 用法示例 ------
if __name__ == "__main__":
    # 假设 license_texts 从你的oss结构读取/分块提取
    license_texts = [
        {
            "id": "licenseTextItem1",
            "title": "1: Apache License 2.0↩",
            "text": "Apache License\n\nVersion 2.0, January 2004\n..."
        },
        {
            "id": "licenseTextItem20",
            "title": "20: GNU General Public License v2.0 only",
            "text": "GNU General Public License, version 2\n\n..."
        },
        {
            "id": "licenseTextItem14",
            "title": "14: BSD-3-Clause",
            "text": "Redistribution and use in source and binary forms, ..."
        }
    ]

    # 实例化，并选择你要的评审方式
    reviewer = RiskReviewer(model="api")  # "rule", "gpt", "api"
    risk_json = reviewer.review_and_save(license_texts, "all_license_risk_result.json")

    print(json.dumps(risk_json, ensure_ascii=False, indent=2))