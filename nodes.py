from pocketflow import Node, BatchNode
import re, os
from spire.doc import *
from spire.doc.common import *
from bs4 import BeautifulSoup
import json
from utils.LLM_Analyzer import (RiskReviewer, RiskChecker, RiskBot,
                                credentialChecker, sourceCodeChecker,
                                DependecyChecker)
from utils.vectorDB import VectorDatabase
from back_end.items_utils.item_types import TYPE_CONFIG, ItemType
from utils.tools import (reverse_exec, format_oss_text_to_html, extract_h1_content)
from utils.itemFilter import filter_components_by_credential_requirement, filter_html_content
import random
from log_config import get_logger
from back_end.items_utils.item_utils import process_items_and_generate_finals

logger = get_logger(__name__)  # 每个模块用自己的名称
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

    def prep(self, shared):
        logger.info("Now we are parsing the original HTML File")
        html_path = shared["html_path"]
        
        # 确保文件存在
        if not os.path.exists(html_path):
            raise FileNotFoundError(f"HTML file not found: {html_path}")
            
        # 读取文件
        try:
            with open(html_path, "r", encoding="utf-8") as html:
                html_content = html.read()
                soup = BeautifulSoup(html_content, "html.parser")
                shared["data"] = soup
                return shared["data"]
        except Exception as e:
            logger.error(f"Error parsing HTML: {str(e)}")
            raise
    
    
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
        logger.info("Successfully parsed!")
        return "default"

class LicenseReviewing(BatchNode):
    
    """
    对上文生成的包含原始OSS readme消息的内容做风险评估，并生成一个新的仅包含组件名、风险的json文件，
    同时生成对于许可证是否需要授权的判断
    """

    def __init__(self, deployment=None):
        super().__init__()
        self.deployment = deployment

    def prep(self, shared):
        logger.info('Now we are reviewing the components list')
        # super的prep的话就是そのまま把数据搞出来了
        parsedHtml = shared["parsedHtml"]
        random_int = random.getrandbits(64)
        licenseTexts = [(item['id'], item['title'], item['text'],random_int)
                        for item in parsedHtml['license_texts']]
        logger.info(f'We have {len(licenseTexts)} to review')
        return licenseTexts
    
    def exec(self, licenseText):
        lId, lTitle, lText, randInt = licenseText
        
        reviewer = RiskReviewer(session_id=f'review{randInt:016x}')
        creChecker = credentialChecker(session_id=f'credentialCheck{randInt:016x}')
        srcChecker = sourceCodeChecker(session_id=f'credentialCheck{randInt:016x}')

        risk = reviewer.review(lTitle,lText)
        credentialOrNot = creChecker.check(lTitle,lText)
        srcOrNot = srcChecker.check(lTitle,lText)
        logger.info('We have reviewed one component')

        return lTitle,risk, credentialOrNot, srcOrNot
    
    def post(self, shared, prep_res, exec_res_list):

        """
        遍历全部license文本后合并风险评级
        """

        shared["riskAnalysis"] = [
            {
                'licenseTitle': lTitle,
                'risk': risk,
                'credentialOrNot': credential,
                'sourceCodeRequired': srcOrNot,
            }
            for lTitle, risk, credential, srcOrNot in exec_res_list
        ]

        ### 这里为了测试！！！选了一个组件改credential为true！
        shared["riskAnalysis"][0]["credentialOrNot"]["CredentialOrNot"] = True

        with open("analysisOfRisk.json","w", encoding="utf-8" ) as f1:
            json.dump(shared["riskAnalysis"],f1,ensure_ascii=False,indent=2)

        logger.info('Completely Reviewed.')
        return "default"

class SpecialLicenseCollecting(BatchNode):

    def __init__(self, max_retries=1, wait=0):
        super().__init__(max_retries, wait)

    def prep(self, shared):
        logger.info("Now we are collecing special licenses such as GPL")
        parsedHtml = shared["parsedHtml"]
        # 在prep阶段只准备数据，不初始化分类字典
        licenseTexts = [(item['id'], item['title'], item['text'])
                        for item in parsedHtml['license_texts']]
        return licenseTexts
    
    def exec(self, licenseText):
        # If licenseText is a tuple from prep, extract the title
        if isinstance(licenseText, tuple):
            _, lTitle, _ = licenseText  # Extract title from (id, title, text)
        else:
            lTitle = licenseText
        
        # 每个exec返回一个包含lTitle和它应该属于哪个类别的元组
        if "GPLv3" in lTitle or "LGPLv3" in lTitle:
            category = "GPLv3, LGPLv3"
        elif "GPL" in lTitle and "Exception" in lTitle:
            category = "GPL with Exception"
        elif "LPGPL" in lTitle:
            category = "LPGPL"
        elif "LGPL" in lTitle:
            category = "GPL, LGPL"
        elif "GPL" in lTitle:
            category = "GPL"
        else:
            category = None
        
        # 返回许可证标题和它所属的类别

        if category:

            result = {
                'licName': lTitle,
                'category': category
            }

            return result
        
        else:
            return None
    
    def post(self, shared, prep_res, exec_res):
        # # 在post阶段创建并填充分类字典
        # categories = {
        #     "GPLv3, LGPLv3": [],
        #     "GPL with Exception": [],
        #     "LPGPL": [],
        #     "GPL, LGPL": [],
        #     "GPL": []
        # }
        
        # # exec_res包含了所有exec方法的返回结果
        # for result in exec_res:
        #     if result is not None:  # 过滤掉没有匹配的许可证
        #         lTitle, category = result
        #         categories[category].append(lTitle)
        
        # 将结果存入shared，保持和之前的一样是一个字典格式

        # !!! 为了测试加入这个GPL的文件
        test_item = {
                'licName': 'GPL',
                'category': 'GPL'
            }
        exec_res.append(test_item)
        filtered_results = [result for result in exec_res if result is not None]
        shared[TYPE_CONFIG[ItemType.SPECIALCHECK]['items_key']] = filtered_results

        with open("specialCollections.json","w", encoding="utf-8" ) as f1:
            json.dump(shared[TYPE_CONFIG[ItemType.SPECIALCHECK]['items_key']],f1,ensure_ascii=False,indent=2)
        return "default"
    
    
class RiskCheckingRAG(BatchNode):

    def __init__(self, deployment = None, embedding_deployment = None,max_retries=1, wait=0):
        super().__init__(max_retries, wait)
        self.deployment = deployment
        self.embedding_deployment = embedding_deployment
    # 这个prompt要改一下，我觉得check也得基于text
    def prep(self, shared):
        logger.info('Now checking the reviewed risks')
        parsedHtml = shared["parsedHtml"]
        random_int = random.getrandbits(64)
        licenseTexts = [(item['id'], item['title'], item['text'],random_int)
                for item in parsedHtml['license_texts']]
        originalRiskAnalysis = [ (k['licenseTitle'], k["risk"]['level'], k["risk"]['reason'],random_int) for k in shared["riskAnalysis"]]
        logger.info(f'We have {len(originalRiskAnalysis)} components to check')

        # 创建一个基于title的licenseTexts字典
        license_dict = {}
        for _, title, text, _ in licenseTexts:
            license_dict[title] = (text, random_int)
        
        # 连接两个列表，基于title
        combined_data = []
        for title, risk_level, risk_reason, _ in originalRiskAnalysis:
            if title in license_dict:
                license_text, random_int = license_dict[title]
                # 组合数据：title, license_text, risk_level, risk_reason, random_int
                combined_data.append((title, license_text, risk_level, risk_reason, random_int))
        
        logger.info(f'Successfully combined {len(combined_data)} license and risk records')
        return combined_data
    
    def exec(self, item):
        reviewedTitle, originalText, reviewedLevel, reviewedReason, randInt = item
        db1 = VectorDatabase()
        db1.load("component_licenses_db")
        retrievedDocument = db1.search(reviewedTitle)
        checker = RiskChecker(session_id=f'check{randInt:016x}')
        checkedRisk = checker.review(reviewedTitle,originalText, reviewedLevel,reviewedReason,retrievedDocument)

        # 姑且以checker的结果为标准吧
        logger.info('We have checked one component')

        return checkedRisk
    
    def post(self, shared, prep_res, exec_res):

        shared[TYPE_CONFIG[ItemType.LICENSE]['items_key']] = exec_res

        toBeConfrimed_risk_license = [
            info for info in exec_res
            if info.get("CheckedLevel") == "high" or "medium"
        ]

        shared["toBeConfirmedLicenses"] = toBeConfrimed_risk_license

        with open("toBeConfirmedLicenses.json","w", encoding="utf-8" ) as f1:
            json.dump(shared["toBeConfirmedLicenses"],f1,ensure_ascii=False,indent=2)

        with open("checkedRisk.json","w", encoding="utf-8" ) as f1:
            json.dump(shared[TYPE_CONFIG[ItemType.LICENSE]['items_key']],f1,ensure_ascii=False,indent=2)

        logger.info('finished checking, now we are checking the dependecies')
        return "default"
    
class DependecyCheckingRAG(BatchNode):
    
    def __init__(self, max_retries=1, wait=0):
        super().__init__(max_retries, wait)

    def prep(self, shared):
        logger.info("now we start analyzing depencies between components")
        parsedHtml = shared['parsedHtml']
        random_int = random.getrandbits(64)
        components = [ (item['name'], item['block_html'],random_int )
                    for item in parsedHtml['releases']]
        
        with open("components.json","w", encoding="utf-8" ) as f1:
            json.dump(components,f1,ensure_ascii=False,indent=2)
        return components
    
    def exec(self, comp):
        compName, compHtml, randInt = comp
        db = VectorDatabase()
        db.load('component_licenses_db')
        context = db.search(compName)
        dependecyChecker = DependecyChecker(
            session_id=f'check{randInt:016x}')
        dependency = dependecyChecker.check(compName,compHtml,context)
        logger.info("Now we have checked dependency of one component")

        return dependency
    
    def post(self, shared, prep_res, exec_res):

        credential_required_components = filter_components_by_credential_requirement(
            prep_res,
            shared['parsedHtml'],
            shared['riskAnalysis']
        )
        shared[TYPE_CONFIG[ItemType.CREDENTIAL]['items_key']] = credential_required_components

        dependency_required__components = [comp for comp in exec_res if comp.get("dependency") == True]
        shared[TYPE_CONFIG[ItemType.COMPONENT]['items_key']] = dependency_required__components
        shared['toBeConfirmedComponents'] = exec_res

        with open("dependecies.json","w", encoding="utf-8" ) as f1:
            json.dump(shared[TYPE_CONFIG[ItemType.COMPONENT]['items_key']],f1,ensure_ascii=False,indent=2)
        
        with open("credentialComps.json","w", encoding="utf-8" ) as f1:
            json.dump(shared[TYPE_CONFIG[ItemType.CREDENTIAL]['items_key']],f1,ensure_ascii=False,indent=2)

        logger.info('finished checking, now we are starting the chat...')
        shared['toInitialize'] = 'riskBot'

        return 'default'
class initializeSession(Node):
    """
    这个节点用来维护一个会话，方便管理上下文
    """
    def __init__(self, max_retries=1, wait=0):
        super().__init__(max_retries, wait)

    def prep(self, shared):

        """依赖上个节点对toInitialize的修改来决定创建哪个类型的会话"""
        if shared.get('toInitialize', '') != '':
            return shared['toInitialize']
        
    def exec(self, prep_res):
        if prep_res == 'riskBot':
            random_int = random.getrandbits(64)
            riskBot = RiskBot(session_id=f"riskBot{random_int:016x}")
            logger.info('Initialized session successfully, waiting for the bot to start conversation')
        return riskBot
    
    def post(self, shared, prep_res, exec_res):
        if prep_res == 'riskBot':
            shared[prep_res] = exec_res

        logger.info("Starting Chatting...")
        
        return 'default'

class itemFiltering(Node):

    def __init__(self, max_retries=1, wait=0):
        super().__init__(max_retries, wait)

    def prep(self, shared):
        logger.info('now we are filtering items...')
        filted_items = process_items_and_generate_finals(shared)

        return shared, filted_items
    
    def exec(self, prep_res):
        '''
        许可证和组件都是选择用户确认过的部分
        '''

        shared, filtered_itmes = prep_res
        filtered_components = filtered_itmes[f'final_{ItemType.CREDENTIAL.value}s']
        # filtered_components = shared['filtered_components']
        filtered_licenses = filtered_itmes[f'final_{ItemType.LICENSE.value}s']
        # filtered_licenses = shared['filtered_licenses']
        logger.info('Now we are generating filtered html...')
        final_html = filter_html_content(shared['parsedHtml'], filtered_components, filtered_licenses)

        return final_html
    
    def post(self, shared, prep_res, exec_res):

        shared["final_licenses"] = exec_res['license_texts']

        shared["final_releases"] = exec_res['releases']

        shared["final_overview"] = exec_res['release_overview']

        return 'default'
    

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

        project_title = extract_h1_content(parsedHtml['intro_html'])

        with open('src/doc/intro.txt', 'r', encoding='utf-8') as f1:
            intro = f1.read()
            intro_html = format_oss_text_to_html(intro)

        return {
            "meta" : parsedHtml["meta"],
            'project_title': project_title,
            "intro_html" : intro_html,
            "release_overview" : final_overview,
            "releases": final_releases,
            "license_texts": final_licenses,
            "extra_html":parsedHtml["extra_html"]
        }
    
    def exec(self, prep_res):
        reconstructedHtml = reverse_exec(prep_res)
        logger.info("We got the reconstructed html successfully!")
        return reconstructedHtml
    
    def post(self, shared, prep_res, exec_res):
        shared["reconstructedHtml"] = exec_res
        session_id = shared.get('session_id', '')

        with open('reconstructedHtml.html', "w", encoding="utf-8") as f:
            f.write(shared["reconstructedHtml"])

        document = Document()
        document.LoadFromFile('reconstructedHtml.html',FileFormat.Html, XHTMLValidationType.none)
        document.SaveToFile(f'downloads/{session_id}/Final_OSS_Readme.docx', FileFormat.Docx2019)
        document.Close()
        logger.info("We have generated the oss readme file successfully!")
        return super().post(shared, prep_res, exec_res)
