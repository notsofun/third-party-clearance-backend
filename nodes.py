from pocketflow import Node, BatchNode
import re
from bs4 import BeautifulSoup
import json
from utils.LLM_Analyzer import (RiskReviewer, RiskChecker, ComponentsConfirmer)
from utils.vectorDB import VectorDatabase
from utils.callAIattack import AzureOpenAIChatClient
from utils.tools import (clean_license_title, reverse_exec)

class ParsingOriginalHtml(Node):
    """处理原始OSS-Readme文件，生成Json文件方便后续调用
    prep：拿数据
    exec：干活
    post：存数据&收尾
    数据靠 shared 字典在节点间流转
    """

    def __init__(self):
        """初始化预处理节点，生成json格式文件方便后续处理"""
        super().__init__()
        
    def prep(self,shared):
        """开始解析，先读取该文档"""
        html_path = shared["html_path"]
        # shared就是需要提供的html路径
        with open(html_path, "r", encoding="utf-8") as html:
            html_content = html.read()

            soup = BeautifulSoup(html_content,"html.parser")

        shared["data"] = soup

        return shared["data"]
    
    
    def exec(self, data):

        if data is None:
            return None
        
        meta = {
            "doctype" : "html",
            "head" : str(data.head),
            "title" : data.title.text if data.title else ""
        }

        body = data.body
        all_body_html = str(body)
        overview = data.find("ul", id="releaseOverview")
        if overview:
            intro_html = all_body_html.split(str(overview))[0]
            intro_html = intro_html.replace("<body>", "").strip()
        else:
            intro_html = all_body_html

        # release overview目录
        release_overview = []
        if overview:
            for li in overview.find_all("li"):
                t = li.text.strip()
                id_match = re.search(r'h3(.+)_([\d\.]+)', li.a['href']) if li.find('a') else None
                if id_match:
                    name = id_match.group(1).replace("_", " ").replace("-", " ").strip()
                    version = id_match.group(2)
                    href_id = li.a['href'].strip("#")
                else:
                    # fallback
                    match = re.match(r'(.*)\s+([\d\.]+)$', t)
                    name, version = (match.group(1), match.group(2)) if match else (t, "")
                    href_id = li.a['href'].strip("#") if li.find('a') else ""
                release_overview.append({
                    "name": name,
                    "version": version,
                    "href_id": href_id,
                    "text": t
                })

        # release详情分块
        releases = []
        for li in data.find_all("li", class_="release"):
            block = {}

            # 组件名与版本
            h3 = li.find("h3")
            if h3:
                name_ver = h3.text.strip().replace("↩", "").strip()
                name_match = re.match(r'(.*?)\s+([0-9][\d\.]+)$', name_ver)
                if name_match:
                    name = name_match.group(1)
                    version = name_match.group(2)
                else:
                    name, version = name_ver, ""
                block["name"] = name
                block["version"] = version
                block["block_html"] = str(li)  # 原始HTML备份

            # license名
            licenses = []
            for l in li.select('.licenseEntry'):
                licenses.append(l['title'])
            block["license_names"] = licenses

            # license原文
            license_texts = []
            for license_link in li.select('.licenseEntry a'):
                href = license_link.attrs.get('href', '')
                if href.startswith("#licenseTextItem"):
                    lic_text_block = data.select_one(href)
                    if lic_text_block and lic_text_block.pre:
                        ltxt = lic_text_block.pre.text.strip()
                        license_texts.append(ltxt)
            block["license_texts"] = license_texts

            # Copyright/Ack
            cp_pre = li.find("pre", class_="copyrights")
            block['copyright'] = cp_pre.text.strip() if cp_pre else ""
            ack_pre = li.find("pre", class_="acknowledgements")
            block['acknowledgement'] = ack_pre.text.strip() if ack_pre else ""

            releases.append(block)

        # license 全文区块
        license_texts = []
        ul = data.find("ul", id="licenseTexts")
        if ul:
            for lic in ul.find_all("li"):
                lic_id = lic.get("id", "")
                h3 = lic.find("h3")
                title = h3.text if h3 else ""
                pre = lic.find("pre", class_="licenseText")
                text = pre.text.strip() if pre else ""
                license_texts.append({
                    "id": lic_id,
                    "title": title,
                    "text": text
                })

        # body后面（可能还有div、尾注等）
        # extra_html = "" # 如有尾注等自定义提取
        tail_marker = '</ul>' if ul else '</body>'
        extra_html = all_body_html.split(tail_marker)[-1]

        final_Result = {
            "meta": meta,
            "intro_html": intro_html,
            "release_overview": release_overview,
            "releases": releases,
            "license_texts": license_texts,
            "extra_html": extra_html
        }
        # 后面传组件名用text字段，license的列表在licensesNames，licenseTexts里面找实际用到的license，然后给模型title和text
        # 聚合全部
        return final_Result
    
    def post(self, shared, prep_res, exec_res):
        shared["parsedHtml"] =  exec_res
        with open("parsed_original_oss.json","w",encoding="utf-8") as f:
            json.dump(exec_res,f,ensure_ascii=False,indent=2)
        return "default"

class LicenseReviewing(BatchNode):
    
    """
    对上文生成的包含原始OSS readme消息的内容做风险评估，并生成一个新的仅包含组件名、风险的json文件
    """

    def __init__(self, deployment=None):
        super().__init__()
        self.deployment = deployment

    def prep(self, shared):
        # super的prep的话就是そのまま把数据搞出来了
        parsedHtml = shared["parsedHtml"]
        licenseTexts = [(item['id'], item['title'], item['text']) 
                        for item in parsedHtml['license_texts']]
        return licenseTexts
    
    def exec(self, licenseText):
        lId, lTitle, lText = licenseText
        reviewer = RiskReviewer()
        risk = reviewer.review(lTitle,lText)

        return lTitle, risk
    
    def post(self, shared, prep_res, exec_res_list):

        """
        遍历全部license文本后合并风险评级
        """
        shared["riskAnalysis"] = {
            lTitle : risk
            for lTitle, risk in exec_res_list
        }

        with open("analysisOfRisk.json","w", encoding="utf-8" ) as f1:
            json.dump(shared["riskAnalysis"],f1,ensure_ascii=False,indent=2)

        return "default"
    
class RiskCheckingRAG(BatchNode):

    def __init__(self, deployment = None, embedding_deployment = None,max_retries=1, wait=0):
        super().__init__(max_retries, wait)
        self.deployment = deployment
        self.embedding_deployment = embedding_deployment

    def prep(self, shared):
        originalRiskAnalysis = [ (k, v["level"], v["reason"]) for k,v in shared["riskAnalysis"].items()]
        return originalRiskAnalysis
    
    def exec(self, item):
        reviewedTitle, reviewedLevel, reviewedReason = item
        db1 = VectorDatabase()
        db1.load("LicenseTable")
        retrievedDocument = db1.search(reviewedTitle)
        checker = RiskChecker()
        checkedRisk = checker.review(reviewedTitle,reviewedLevel,reviewedReason,retrievedDocument)
        # 姑且以checker的结果为标准吧
        return checkedRisk
    
    def post(self, shared, prep_res, exec_res):

        shared["checkedRisk"] = exec_res

        
        toBeConfrimed_risk_comps = [
            info for info in exec_res
            if info.get("CheckedLevel") == "high" or "medium"
        ]

        shared["toBeConfirmedComps"] = toBeConfrimed_risk_comps

        with open("checkedRisk.json","w", encoding="utf-8" ) as f1:
            json.dump(shared["checkedRisk"],f1,ensure_ascii=False,indent=2)

        return "default"
    
class getFinalOSS(Node):
    """这个节点的作用应该是传入最终的组件清单，
    和之前的解析的html文件中不变的部分组合，并逆向当时的解析过程，给到最终的html文件"""
    def __init__(self, max_retries=1, wait=0):
        super().__init__(max_retries, wait)

    def prep(self, shared):
        
        final_licenses = shared["final_licenses"]

        final_releases = shared["final_releases"]

        final_overview = shared["final_overview"]

        parsedHtml = shared["parsedHtml"]


    # 高风险组件需要让人去确认，不应该删除，加一个chat的环节，也有无论如何都要用的

        return {
            "meta" : parsedHtml["meta"],
            "intro_html" : parsedHtml["intro_html"],
            "release_overview" : final_overview,
            "releases":final_releases,
            "license_texts":final_licenses,
            "extra_html":parsedHtml["extra_html"]
        }
    
    def exec(self, prep_res):
        reconstructedHtml = reverse_exec(prep_res)
        return reconstructedHtml
    
    def post(self, shared, prep_res, exec_res):
        shared["reconstructedHtml"] = exec_res
        return super().post(shared, prep_res, exec_res)
    
class GetUserConfirming(Node):

    def __init__(self, max_retries=1, wait=0):
        super().__init__(max_retries, wait)
        # 是不是得在flow里面去写，这个判定的流程
        # 我看PocketFlow给的这个是把上下文的存储和获取都放在shared里面了，但是我这个适合这样吗？
        # 通过post的返回为“continue”还是“exit”来确定是否推进


    def prep(self, shared):
        # 但是这种方式，就没有单个会话的上下文了呀，还得维护一个三问三答的上下文
        if shared["toBeConfirmedComps"] is None:
            print("Now we have checked all risky components!")
            return None

        print(f"Now we are confirming {shared["toBeConfirmedComps"][0]['title']}")
        return shared["toBeConfirmedComps"][0]
    
    def exec(self, prep_res):
        if prep_res == None:
             return None
        
        confirmer = ComponentsConfirmer()
         
        # 先处理高风险组件，要求用户确认是否删除，并提供理由
        if prep_res['CheckedLevel'] == "high":
            explanation = confirmer.highRiskExplainer(prep_res)
            print(f"{explanation}\n Are you sure you want to keep this component?")
            user_res = input("Please provide your answer (Yes/No)")
            if user_res == "Yes":
                reason = print("Plese provide your reason")
                pass
            elif user_res == "No":
                pass
            else:
                print("Please input Yes or No!")


        # 再处理中风险组件，要求用户确认是否按照标准来处理
        return super().exec(prep_res)