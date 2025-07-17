from pocketflow import Node, BatchNode
import re
from bs4 import BeautifulSoup
import json
from utils.licenseReviewer import RiskReviewer

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
        # with open("pased_original_oss.json","w",encoding="utf-8") as f:
        #     json.dump(exec_res,f,ensure_ascii=False,indent=2)
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
        reviewer = RiskReviewer(model="api")
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