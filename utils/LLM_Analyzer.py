import json
from utils.callAIattack import AzureOpenAIChatClient
import time
from utils.tools import get_strict_json
from langchain_openai import AzureChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("msal").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

class RiskReviewer(AzureOpenAIChatClient):
    """
    License风险评审类
    支持不同模型引擎：如'rule', 'gpt', 'api'
    """

    def __init__(self, endpoint="https://openai-aiattack-msa-001905-eastus-bsce-ai-00.openai.azure.com", deployment=None, embedding_deployment=None, api_version="2025-01-01-preview", client_id=None, client_secret=None, tenant_id=None, session_id='default', promptName='automation/riskChecker'):
        super().__init__(endpoint, deployment, embedding_deployment, api_version, client_id, client_secret, tenant_id, session_id, promptName)
        self.promptName = promptName
    
    def _call_api(self, title, text):
        """
        纯调用API函数
        """

        message = {
            'title': title,
            'text': text
        }

        result = self._request(message)
        return result

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

    def __init__(self, endpoint="https://openai-aiattack-msa-001905-eastus-bsce-ai-00.openai.azure.com", deployment=None, embedding_deployment=None, api_version="2025-01-01-preview", client_id=None, client_secret=None, tenant_id=None, session_id='default', promptName='automation/riskReviewer'):
        super().__init__(endpoint, deployment, embedding_deployment, api_version, client_id, client_secret, tenant_id, session_id, promptName)
        self.deployment = "o3-2025-04-16"
        self.promptName = promptName

    def _call_api(self, title, level, reason, context):
        """
        title:上层reviewe过的结果，待check的license title
        level：上层review过的的风险等级，待check
        reason：上层给出的风险等级
        context：在此层获取到的相关知识内容
        """

        message = {
            'context':context,
            'level':level,
            'reason':reason,
            'title':title,
        }

        result = self._request(message)

        return result
    
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

class credentialChecker(AzureOpenAIChatClient):
    def __init__(self, endpoint="https://openai-aiattack-msa-001905-eastus-bsce-ai-00.openai.azure.com", deployment=None, embedding_deployment=None, api_version="2025-01-01-preview", client_id=None, client_secret=None, tenant_id=None, session_id='default', promptName="automation/CredentialChecker"):
        super().__init__(endpoint, deployment, embedding_deployment, api_version, client_id, client_secret, tenant_id, session_id, promptName)
        self.promptName = promptName

    def check(self,title:str,text:str) -> str:
        """
        result should be a json object:{"LicenseName":"Apache License 2.0","CredentialOrNot":false}
        """
        message = {
            "license_name" : title,
            "license_text" : text,
        }
        result = get_strict_json(self,user_input=message)

        return result

class Chatbot(AzureOpenAIChatClient):

    def __init__(self, endpoint="https://openai-aiattack-msa-001905-eastus-bsce-ai-00.openai.azure.com", deployment=None, embedding_deployment=None, api_version="2025-01-01-preview", client_id=None, client_secret=None, tenant_id=None, session_id='default', promptName='default',system_prompt=None):
        super().__init__(endpoint, deployment, embedding_deployment, api_version, client_id, client_secret, tenant_id, session_id, promptName)
        self.llm = AzureChatOpenAI(
            api_version=self.api_version,
            azure_endpoint=self.endpoint,
            azure_ad_token=self.access_token,
            azure_deployment=self.deployment
        )

        self.system_prompt = self.langfusePrompt.prompt

        self.memory = ConversationBufferMemory(memory_key="history", return_messages=True)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
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

        if not isinstance(user_input, str):
            raise TypeError("Input 'user_input' must be a string.")
    
        response = self.chain.invoke(
            {"input": user_input},
            config = {
            'callbacks' : [self.langfuse_handler],
            'metadata' : {
                "langfuse_session_id": f"{self.session_id}",
                "langfuse_user_id" : "NotSoFun"}
        })
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

    def __init__(self, session_id):
        super().__init__(
            promptName="bot/RiskBot",
            session_id = 'default'
        )
        self.session_id = session_id
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

def trial1():
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

# ------ 用法示例 ------
if __name__ == "__main__":
    # license1 = {
    # "title": "GNU General Public License v2.0 only",
    # "originalLevel": "high",
    # "CheckedLevel": "high",
    # "Justification": "GPL-2.0 is a strong copyleft license: any distribution of derivative works (including statically or dynamically linked binaries) must be licensed as a whole under GPL-2.0, source code must be made available, and sublicensing under more permissive terms is not allowed. These obligations create significant license-compatibility and release requirements for proprietary or mixed-license projects, leading to a high compliance and business risk profile. However, it does not include additional network-service copyleft (like AGPL) or patent retaliation clauses that might elevate it to a “very high” category. Therefore, a \"high\" risk rating is appropriate and is confirmed."
    # }
    # bot1 = RiskBot(session_id = 'ChatbotTrial')
    # bot1.toConfirm(license1)
    message = {
        "license_name":"1: Apache License 2.0⇧",
        "license_text":"Apache License\n\nVersion 2.0, January 2004\n\nhttp://www.apache.org/licenses/ TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION\n\n   1. Definitions.\n\n      \n\n      \"License\" shall mean the terms and conditions for use, reproduction, and distribution as defined by Sections 1 through 9 of this document.\n\n      \n\n      \"Licensor\" shall mean the copyright owner or entity authorized by the copyright owner that is granting the License.\n\n      \n\n      \"Legal Entity\" shall mean the union of the acting entity and all other entities that control, are controlled by, or are under common control with that entity. For the purposes of this definition, \"control\" means (i) the power, direct or indirect, to cause the direction or management of such entity, whether by contract or otherwise, or (ii) ownership of fifty percent (50%) or more of the outstanding shares, or (iii) beneficial ownership of such entity.\n\n      \n\n      \"You\" (or \"Your\") shall mean an individual or Legal Entity exercising permissions granted by this License.\n\n      \n\n      \"Source\" form shall mean the preferred form for making modifications, including but not limited to software source code, documentation source, and configuration files.\n\n      \n\n      \"Object\" form shall mean any form resulting from mechanical transformation or translation of a Source form, including but not limited to compiled object code, generated documentation, and conversions to other media types.\n\n      \n\n      \"Work\" shall mean the work of authorship, whether in Source or Object form, made available under the License, as indicated by a copyright notice that is included in or attached to the work (an example is provided in the Appendix below).\n\n      \n\n      \"Derivative Works\" shall mean any work, whether in Source or Object form, that is based on (or derived from) the Work and for which the editorial revisions, annotations, elaborations, or other modifications represent, as a whole, an original work of authorship. For the purposes of this License, Derivative Works shall not include works that remain separable from, or merely link (or bind by name) to the interfaces of, the Work and Derivative Works thereof.\n\n      \n\n      \"Contribution\" shall mean any work of authorship, including the original version of the Work and any modifications or additions to that Work or Derivative Works thereof, that is intentionally submitted to Licensor for inclusion in the Work by the copyright owner or by an individual or Legal Entity authorized to submit on behalf of the copyright owner. For the purposes of this definition, \"submitted\" means any form of electronic, verbal, or written communication sent to the Licensor or its representatives, including but not limited to communication on electronic mailing lists, source code control systems, and issue tracking systems that are managed by, or on behalf of, the Licensor for the purpose of discussing and improving the Work, but excluding communication that is conspicuously marked or otherwise designated in writing by the copyright owner as \"Not a Contribution.\"\n\n      \n\n      \"Contributor\" shall mean Licensor and any individual or Legal Entity on behalf of whom a Contribution has been received by Licensor and subsequently incorporated within the Work.\n\n   2. Grant of Copyright License. Subject to the terms and conditions of this License, each Contributor hereby grants to You a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable copyright license to reproduce, prepare Derivative Works of, publicly display, publicly perform, sublicense, and distribute the Work and such Derivative Works in Source or Object form.\n\n   3. Grant of Patent License. Subject to the terms and conditions of this License, each Contributor hereby grants to You a perpetual, worldwide, non-exclusive, no-charge, royalty-free, irrevocable (except as stated in this section) patent license to make, have made, use, offer to sell, sell, import, and otherwise transfer the Work, where such license applies only to those patent claims licensable by such Contributor that are necessarily infringed by their Contribution(s) alone or by combination of their Contribution(s) with the Work to which such Contribution(s) was submitted. If You institute patent litigation against any entity (including a cross-claim or counterclaim in a lawsuit) alleging that the Work or a Contribution incorporated within the Work constitutes direct or contributory patent infringement, then any patent licenses granted to You under this License for that Work shall terminate as of the date such litigation is filed.\n\n   4. Redistribution. You may reproduce and distribute copies of the Work or Derivative Works thereof in any medium, with or without modifications, and in Source or Object form, provided that You meet the following conditions:\n\n      (a) You must give any other recipients of the Work or Derivative Works a copy of this License; and\n\n      (b) You must cause any modified files to carry prominent notices stating that You changed the files; and\n\n      (c) You must retain, in the Source form of any Derivative Works that You distribute, all copyright, patent, trademark, and attribution notices from the Source form of the Work, excluding those notices that do not pertain to any part of the Derivative Works; and\n\n      (d) If the Work includes a \"NOTICE\" text file as part of its distribution, then any Derivative Works that You distribute must include a readable copy of the attribution notices contained within such NOTICE file, excluding those notices that do not pertain to any part of the Derivative Works, in at least one of the following places: within a NOTICE text file distributed as part of the Derivative Works; within the Source form or documentation, if provided along with the Derivative Works; or, within a display generated by the Derivative Works, if and wherever such third-party notices normally appear. The contents of the NOTICE file are for informational purposes only and do not modify the License. You may add Your own attribution notices within Derivative Works that You distribute, alongside or as an addendum to the NOTICE text from the Work, provided that such additional attribution notices cannot be construed as modifying the License.\n\n      You may add Your own copyright statement to Your modifications and may provide additional or different license terms and conditions for use, reproduction, or distribution of Your modifications, or for any such Derivative Works as a whole, provided Your use, reproduction, and distribution of the Work otherwise complies with the conditions stated in this License.\n\n   5. Submission of Contributions. Unless You explicitly state otherwise, any Contribution intentionally submitted for inclusion in the Work by You to the Licensor shall be under the terms and conditions of this License, without any additional terms or conditions. Notwithstanding the above, nothing herein shall supersede or modify the terms of any separate license agreement you may have executed with Licensor regarding such Contributions.\n\n   6. Trademarks. This License does not grant permission to use the trade names, trademarks, service marks, or product names of the Licensor, except as required for reasonable and customary use in describing the origin of the Work and reproducing the content of the NOTICE file.\n\n   7. Disclaimer of Warranty. Unless required by applicable law or agreed to in writing, Licensor provides the Work (and each Contributor provides its Contributions) on an \"AS IS\" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied, including, without limitation, any warranties or conditions of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A PARTICULAR PURPOSE. You are solely responsible for determining the appropriateness of using or redistributing the Work and assume any risks associated with Your exercise of permissions under this License.\n\n   8. Limitation of Liability. In no event and under no legal theory, whether in tort (including negligence), contract, or otherwise, unless required by applicable law (such as deliberate and grossly negligent acts) or agreed to in writing, shall any Contributor be liable to You for damages, including any direct, indirect, special, incidental, or consequential damages of any character arising as a result of this License or out of the use or inability to use the Work (including but not limited to damages for loss of goodwill, work stoppage, computer failure or malfunction, or any and all other commercial damages or losses), even if such Contributor has been advised of the possibility of such damages.\n\n   9. Accepting Warranty or Additional Liability. While redistributing the Work or Derivative Works thereof, You may choose to offer, and charge a fee for, acceptance of support, warranty, indemnity, or other liability obligations and/or rights consistent with this License. However, in accepting such obligations, You may act only on Your own behalf and on Your sole responsibility, not on behalf of any other Contributor, and only if You agree to indemnify, defend, and hold each Contributor harmless for any liability incurred by, or claims asserted against, such Contributor by reason of your accepting any such warranty or additional liability. END OF TERMS AND CONDITIONS\n\nAPPENDIX: How to apply the Apache License to your work.\n\nTo apply the Apache License to your work, attach the following boilerplate notice, with the fields enclosed by brackets \"[]\" replaced with your own identifying information. (Don't include the brackets!) The text should be enclosed in the appropriate comment syntax for the file format. We also recommend that a file or class name and description of purpose be included on the same \"printed page\" as the copyright notice for easier identification within third-party archives.\n\nCopyright [yyyy] [name of copyright owner]\n\nLicensed under the Apache License, Version 2.0 (the \"License\");\n\nyou may not use this file except in compliance with the License.\n\nYou may obtain a copy of the License at\n\nhttp://www.apache.org/licenses/LICENSE-2.0\n\nUnless required by applicable law or agreed to in writing, software\n\ndistributed under the License is distributed on an \"AS IS\" BASIS,\n\nWITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.\n\nSee the License for the specific language governing permissions and\n\nlimitations under the License."}
    riskReviewer = RiskReviewer(session_id='trial')
    riskChecker = RiskChecker(session_id='trial')

    # result = riskReviewer.review(message['license_name'],message['license_text'])
    result = riskChecker.review("BSD-3-Clause","low","Permissive license without copyleft obligations","I like it")
    print(result)