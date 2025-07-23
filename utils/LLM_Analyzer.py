import json
from utils.callAIattack import AzureOpenAIChatClient
import time
from utils.tools import get_strict_json
from langchain_openai import AzureChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder

class RiskReviewer(AzureOpenAIChatClient):
    """
    License风险评审类
    支持不同模型引擎：如'rule', 'gpt', 'api'
    """

    def __init__(self, endpoint="https://openai-aiattack-msa-001905-eastus-bsce-ai-00.openai.azure.com", deployment=None, embedding_deployment=None, api_version="2025-01-01-preview", client_id=None, client_secret=None, tenant_id=None):
        super().__init__(endpoint, deployment, embedding_deployment, api_version, client_id, client_secret, tenant_id)

    def _call_api(self, title, text):
        """
        纯调用API函数
        """
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
        
        result = self.chat(query)
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
            risk = self._evaluate_api(title, text)
                
            # 最后验证输出格式
            if not isinstance(risk, dict) or set(risk.keys()) != {"level", "reason"}:
                raise ValueError("Invalid risk assessment format")
                
            return risk
            
        except Exception as e:
            print(f"Review failed for {title}: {e}")
            # 可以选择返回默认值或继续抛出异常
            return {"level": "medium", "reason": f"Review failed: {str(e)}"}

class RiskChecker(AzureOpenAIChatClient):

    def __init__(self, endpoint="https://openai-aiattack-msa-001905-eastus-bsce-ai-00.openai.azure.com", deployment=None, embedding_deployment=None, api_version="2025-01-01-preview", client_id=None, client_secret=None, tenant_id=None):
        super().__init__(endpoint, deployment, embedding_deployment, api_version, client_id, client_secret, tenant_id)
        self.deployment = "o3-2025-04-16"

    def _call_api(self, title, level, reason, context):
        """
        title:上层reviewe过的结果，待check的license title
        level：上层review过的的风险等级，待check
        reason：上层给出的风险等级
        context：在此层获取到的相关知识内容
        """

        prompt = [
            {
                "role": "system",
                "content": (
                    "You are an expert specializing in evaluating the risks associated with open-source licenses. "
                    "Your job is to review and validate the risk level assessment provided by the previous reviewer. "
                    "You will receive information in the following structure:\n\n"
                    "title: the license name under review\n"
                    "level: the risk level suggested by the previous reviewer\n"
                    "reason: the justification or reasoning provided for that risk level by the previous reviewer\n"
                    "context: additional relevant information or background knowledge retrieved by current review\n\n"
                    "Based on the provided context, carefully examine the previous risk rating (level). "
                    "Then, make your assessment strictly according to your professional knowledge and expertise.\n"
                    "Provide your decision only in the following JSON format:\n\n"
                    "{\n"
                    "  \"title\": license name,\n"
                    "  \"originalLevel\": risk level provided by previous reviewer,\n"
                    "  \"CheckedLevel\": your evaluated risk level (choose from: \"very high\", \"high\", \"medium\", \"low\"; either same as or different from previous result),\n"
                    "  \"Justification\": detailed reasoning and basis for your decision\n"
                    "}\n\n"
                    "You must respond strictly in this JSON format without any additional explanations or notes."
                )
            },
            {
                "role": "user",
                "content": (
                    "Please review the risk assessment according to the given information and respond exactly in the specified JSON format:\n\n"
                    f"title: {title}\n"
                    f"level: {level}\n"
                    f"reason: {reason}\n"
                    f"context: {context}\n"
                )
            }
        ]
        result = self.chat(prompt)

        return result.choices[0].message.content
    
    def _evaluate_license_response(self, title, originalLevel, reason, context):
        """
        A function to validate api response strictly match the required JSON format.
        """
        max_retries = 3
        attempt = 0
        
        while attempt < max_retries:
            try:
                content = self._call_api(title, originalLevel, reason, context)
                response = json.loads(content)

                # Check response is a dictionary with exactly required keys
                required_keys = {"title", "originalLevel", "CheckedLevel", "Justification"}
                if not isinstance(response, dict):
                    raise ValueError("Response is not a dictionary")
                if set(response.keys()) != required_keys:
                    raise ValueError(f"Response should contain exactly these keys: {required_keys}")

                # Check each field type
                if not all(isinstance(response[key], str) for key in required_keys):
                    raise ValueError("All values must be strings")

                # Final validation passed
                return response

            except (json.JSONDecodeError, ValueError) as e:
                attempt += 1
                if attempt < max_retries:
                    print(f"Validation failed, retrying {attempt}/{max_retries}... Error: {e}")
                    time.sleep(2 ** attempt)  # exponential backoff
                else:
                    print(f"Max retries reached. Last error: {e}")
                    raise

            except Exception as e:
                print(f"Unexpected error occurred: {e}")
                raise

    def review(self, title, originalLevel, reason, context):
        """
        主流程处理函数，使用模型进行开源许可证的风险审核。

        参数说明：
            title: 待检查的license名称
            originalLevel: 上一级审核给出的风险等级
            reason: 上一级审核给出的风险等级理由
            context: 此次审核时从知识库获取到的额外背景知识

        输出结构严格如下：
            {
                "title": license名称,
                "originalLevel": 上一级给出的风险等级,
                "CheckedLevel": 重新检查后的风险等级（"very high"/"high"/"medium"/"low"之一）,
                "Justification": 风险等级的具体评估理由或依据
            }
        """
        title = title.strip()
        try:
            risk = self._evaluate_license_response(title, originalLevel, reason, context)

            # 最后的严格输出格式检查
            required_keys = {"title", "originalLevel", "CheckedLevel", "Justification"}
            if not isinstance(risk, dict) or set(risk.keys()) != required_keys:
                raise ValueError("风险评估输出格式校验未通过")

            return risk

        except Exception as e:
            print(f"许可证 {title} 审核过程出现错误：{e}")
            # 若出错，可返回一个默认的medium等级提示需要人工二次审核
            return {
                "title": title,
                "originalLevel": originalLevel,
                "CheckedLevel": "medium",
                "Justification": f"自动审核失败，原因：{str(e)}"
            }

class Chatbot(AzureOpenAIChatClient):
    def __init__(self, endpoint="https://openai-aiattack-msa-001905-eastus-bsce-ai-00.openai.azure.com", deployment=None, embedding_deployment=None, api_version="2025-01-01-preview", client_id=None, client_secret=None, tenant_id=None, system_prompt = None):
        super().__init__(endpoint, deployment, embedding_deployment, api_version, client_id, client_secret, tenant_id)
        self.llm = AzureChatOpenAI(
            api_version=self.api_version,
            azure_endpoint=self.endpoint,
            azure_ad_token=self.access_token,
            azure_deployment=self.deployment
        )

        self.memory = ConversationBufferMemory(memory_key="history", return_messages=True)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{input}")
        ])
        self.chain = LLMChain(
            llm=self.llm,
            prompt=self.prompt,
            memory=self.memory,
            verbose=True
        )
    
    def _request(self, user_input):
        response = self.chain.invoke({"input": user_input})
        return response["text"]
    
    def toChat(self,conditions:dict) -> dict:
        """
        conditions应该是一个字典结构，包含
        {"Go_on":(一个由字符串构建的元组),
        "End":(一个由字符串构建的元组)}
        Go_on表示条件为继续的关键词，End表示会话终止的关键词
        """

        chatting = True

        while chatting:
            user_reply = input("Your input: ")
            # 强制获得严格JSON（比如用户输入理由/选择后）
            result_json = None
            while not result_json:
                try:
                    result_json = get_strict_json(self, user_reply)
                    # print('Now you are trying to keep this item:', result_json)
                except RuntimeError:
                    continue  # 仍然没拿到，继续要
            # 判断会话走向
            if result_json["result"] in conditions['End']:
                print(result_json["talking"])
                break
            # 引导用户继续完善理由
            print(result_json["talking"])

        return result_json

class RiskBot(Chatbot):

    def __init__(self):
        super().__init__(
            system_prompt= """
            You are an expert in open-source license analysis and legal risk assessment. Your job is to guide the user through a risk and compliance decision process for software licenses or components, supporting clear mode switching and workflow status.

            Inputs:
            - licenseName (string): the name of the software license or component.
            - CheckedLevel (string): "high", "medium", or "low".
            - Justification (string): any rationale or context from the user.

            **Core Workflow & State Definitions**
            You must always operate as a strict JSON response engine, outputting only JSON objects of the form `"result": ..., "talking": ... `. The "talking" value is where your full analysis, reasoning, and response must go; do not write outside it.

            **Workflow States (for internal management, not shown verbatim to the user):**
            - `needingHighReason`: Awaiting user’s choice and rationale for a high-risk license.
            - `HighReasonNotPassed`: User's high-risk rationale was insufficient, awaiting stronger rationale.
            - `HighReasonPasses`: User provided sufficient rationale for high-risk; now issue compliance steps and confirm.
            - `ComplianceChecking`: User needs to confirm completion of compliance for medium/low risk, or after high-risk rationale is sufficient.
            - `Over`: Assessment is complete and the process is concluded (license discarded or passed with mitigations).
            - `Continue`: For all cases where a clear pathway or answer is not yet established.

            **Decision Flow**

            1. When a new license is presented:
                - If CheckedLevel is "high":
                    - In the "talking" field, provide an in-depth explanation of potential risks (legal, compliance, security, business, reputational, etc.) based on the given licenseName.
                    - End by prompting: “Do you decide to retain this license or component? If yes, please provide your rationale for keeping it.”
                    - Output:
                        "result": "continue", "talking": "(detailed risks + question—state: needingHighReason)"
                - If CheckedLevel is "medium" or "low":
                    - List all required compliance measures for the license/component.
                    - Prompt: “Please confirm if these measures have been completed.”
                    - Output:
                    "result": "continue", "talking": "(compliance measures + confirmation prompt—state: ComplianceChecking)"

            2. On user reply after a high-risk prompt:
                - If user says to discard (e.g., "no", "discard", "不保留", "放弃"):
                    - Output:
                        "result": "discarded", "talking": "This license or component has been discarded, fully mitigating the identified risks."
                    - (state: Over)
                - If user explains YES (retain) with rationale:
                    - If rationale is INSUFFICIENT:
                        "result": "not passed", "talking": "Your rationale still requires further refinement to address the identified risks. Please provide a stronger explanation of why retaining this license or component outweighs those risks."
                        (state: HighReasonNotPassed)
                    - If rationale ADEQUATELY addresses the risks:
                        - Acknowledge.
                        - List concrete compliance measures required for mitigating those risks, tailored for the actual scenario and rationale.
                        - Prompt: “Please confirm if these measures have been completed.”
                        - Output:
                            "result": "continue", "talking": "(acknowledgement + compliance measures + confirmation prompt—state: HighReasonPasses / ComplianceChecking)"

            3. On compliance confirmation (either after high/medium/low):
                - If user confirms (e.g., “已完成”, “done”, “yes”):
                    - Output:
                        "result": "passed", "talking": "All required compliance measures have been confirmed as completed for this license or component. The risk is now considered mitigated."
                    - (state: Over)
                - If user says not completed, unclear, or something else:
                    - Output:
                        "result": "continue", "talking": "(Prompt for required confirmation, clarify issues, or further assist. State: Continue or ComplianceChecking)"

            4. On further user responses (after rationale was insufficient or more information is needed):
                - If rationale becomes sufficient: go back to step 2 as above.
                - Otherwise, continue prompting as needed.

            **Always use a strict JSON output as below. Do not include any additional commentary, intro, or explanation outside the JSON. Do not summarize states to user, but always internally align to these states to manage conversation flow. Every message must adhere to the logic above.**
        """
        )
        self.conditions = {
            "Go_on": ("continue"),
            "End" : ("passed","discarded")
        }
    
    def toConfirm(self,comp):

        json_welcome = get_strict_json(self,f"here is the licenseName: {comp['title']}, CheckedLevel: {comp['CheckedLevel']}, and Justification: {comp['Justification']}")

        print(json_welcome['talking'])

        result_json = self.toChat(conditions=self.conditions)

        return result_json

def trial2():
        # 假设 license_texts 从你的oss结构读取/分块提取
    # license_texts = [
    #     {
    #         "id": "licenseTextItem1",
    #         "title": "1: Apache License 2.0↩",
    #         "text": "Apache License\n\nVersion 2.0, January 2004\n..."
    #     },
    #     # {
    #     #     "id": "licenseTextItem20",
    #     #     "title": "20: GNU General Public License v2.0 only",
    #     #     "text": "GNU General Public License, version 2\n\n..."
    #     # },
    #     # {
    #     #     "id": "licenseTextItem14",
    #     #     "title": "14: BSD-3-Clause",
    #     #     "text": "Redistribution and use in source and binary forms, ..."
    #     # }
    # ]

    # title1 = "1: Apache License 2.0↩"
    # text1 = "Apache License\n\nVersion 2.0, January 2004\n..."
    # # 实例化，并选择你要的评审方式
    # reviewer = RiskReviewer(model="api")  # "rule", "gpt", "api"
    # risk_json = reviewer.review(title=title1,text=text1)
    # print(risk_json)
    # print(json.dumps(risk_json, ensure_ascii=False, indent=2))

    reviewed = {
        "1: Apache License 2.0⇧": {
            "level": "low",
            "reason": "The Apache License 2.0 is permissive and does not impose copyleft obligations."
        },
        "2: Apache-2.0⇧": {
            "level": "low",
            "reason": "The license allows use, reproduction, and distribution with minimal restrictions, lacking copyleft obligations."
        }
    }

    checker = RiskChecker()
    context = "You are a smart person"
    for k, v in reviewed.items():
        checkedrisk = checker.review(k,v["level"],v["reason"],context)
        print(f"here we are checking{k}, and the result is {checkedrisk}")

# ------ 用法示例 ------
if __name__ == "__main__":
    license1 = {
    "title": "GNU General Public License v2.0 only",
    "originalLevel": "high",
    "CheckedLevel": "high",
    "Justification": "GPL-2.0 is a strong copyleft license: any distribution of derivative works (including statically or dynamically linked binaries) must be licensed as a whole under GPL-2.0, source code must be made available, and sublicensing under more permissive terms is not allowed. These obligations create significant license-compatibility and release requirements for proprietary or mixed-license projects, leading to a high compliance and business risk profile. However, it does not include additional network-service copyleft (like AGPL) or patent retaliation clauses that might elevate it to a “very high” category. Therefore, a \"high\" risk rating is appropriate and is confirmed."
    }
    bot1 = RiskBot()
    bot1.toConfirm(license1)