from pocketflow import Node, BatchNode
import os
from spire.doc import *
from spire.doc.common import *
from bs4 import BeautifulSoup
import json
from utils.LLM_Analyzer import (RiskReviewer, RiskChecker, RiskBot,
                                credentialChecker, sourceCodeChecker,
                                DependencyChecker)
from utils.database.vectorDB import VectorDatabase
from back_end.items_utils.item_types import TYPE_CONFIG, ItemType
from utils.tools import (reverse_exec, format_oss_text_to_html, extract_h1_content, split_tuples)
from utils.htmlParsing import parse_html
from utils.itemFilter import filter_components_by_credential_requirement, filter_html_content
import random
from utils.PCR_Generation.original_PCR_parsing import parse_docx_to_hierarchical_json
from log_config import get_logger
from back_end.items_utils.item_utils import process_items_and_generate_finals
from typing import Dict

logger = get_logger(__name__)  # 每个模块用自己的名称
output_dir = 'resultsInProgress'
# 确保存在resultsInProgress这一个中间目录
try:
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Directory '{output_dir}' ensured to exist.")
except OSError as e:
    logger.error(f"Error creating directory '{output_dir}': {e}")

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
    
    def exec(self, data):

        final_Result = parse_html(data)
        components = [ {"compName": item['name'], "licenses": item['license_names']}
            for item in final_Result['releases']]

        return final_Result, components
    
    def post(self, shared, prep_res, exec_res):
        final, comps = exec_res
        shared[TYPE_CONFIG[ItemType.PC]['items_key']] = comps
        shared["parsedHtml"] =  final

        with open("resultsInProgress/parsed_original_oss.json","w",encoding="utf-8") as f:
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

        with open("resultsInProgress/analysisOfRisk.json","w", encoding="utf-8" ) as f1:
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

        # !!! 为了测试加入这个GPL的文件
        test_item = {
                'licName': 'GPL',
                'category': 'GPL'
            }
        exec_res.append(test_item)

        filtered_results = [result for result in exec_res if result is not None]
        shared[TYPE_CONFIG[ItemType.SPECIALCHECK]['items_key']] = filtered_results

        with open("resultsInProgress/specialCollections.json","w", encoding="utf-8" ) as f1:
            json.dump(shared[TYPE_CONFIG[ItemType.SPECIALCHECK]['items_key']],f1,ensure_ascii=False,indent=2)
        return "default"
    
    
class RiskCheckingRAG(BatchNode):

    def __init__(self, deployment = None, embedding_deployment = None,max_retries=1, wait=0):
        super().__init__(max_retries, wait)
        self.deployment = deployment
        self.embedding_deployment = embedding_deployment

    def prep(self, shared):
        logger.info('Now checking the reviewed risks')
        parsedHtml = shared["parsedHtml"]
        random_int = random.getrandbits(64)
        licenseTexts = [(item['id'], item['title'], item['text'],random_int)
                for item in parsedHtml['license_texts']]
        originalRiskAnalysis = [ (k['licenseTitle'], k["risk"]['level'], k["risk"]['reason'],random_int) for k in shared["riskAnalysis"]]
        logger.info(f'We have {len(originalRiskAnalysis)} licenses to check')

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

        logger.info('We have checked one component')

        return checkedRisk
    
    def post(self, shared, prep_res, exec_res):

        shared[TYPE_CONFIG[ItemType.LICENSE]['items_key']] = exec_res

        toBeConfrimed_risk_license = [
            info for info in exec_res
            if info.get("CheckedLevel") == "high" or "medium"
        ]

        shared["toBeConfirmedLicenses"] = toBeConfrimed_risk_license

        with open("resultsInProgress/toBeConfirmedLicenses.json","w", encoding="utf-8" ) as f1:
            json.dump(shared["toBeConfirmedLicenses"],f1,ensure_ascii=False,indent=2)

        with open("resultsInProgress/checkedRisk.json","w", encoding="utf-8" ) as f1:
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
        components = [ (item['name'], item['block_html'],item['license_names'],random_int)
                    for item in parsedHtml['releases']]
        
        with open("resultsInProgress/components.json","w", encoding="utf-8" ) as f1:
            json.dump(components,f1,ensure_ascii=False,indent=2)
        return components
    
    def exec(self, comp):
        compName, compHtml, license_list, randInt = comp
        db = VectorDatabase()
        db.load('component_licenses_db')
        context = db.search(compName)
        dependecyChecker = DependencyChecker(
            session_id=f'check{randInt:016x}')
        dependency = dependecyChecker.check(compName,compHtml,context)
        compDict = {
            'compName': compName,
            'compHtml': compHtml,
            'licenseList': license_list,
        }
        logger.info("Now we have checked dependency of one component")

        return dependency, compDict
    
    def post(self, shared, prep_res, exec_res):
        dependencies, components = split_tuples(exec_res)

        credential_required_components = filter_components_by_credential_requirement(
            prep_res,
            shared['parsedHtml'],
            shared['riskAnalysis']
        )
        shared[TYPE_CONFIG[ItemType.CREDENTIAL]['items_key']] = credential_required_components

        dependency_required__components = [comp for comp in dependencies if comp.get("dependency") == True]
        shared[TYPE_CONFIG[ItemType.COMPONENT]['items_key']] = dependency_required__components
        shared[TYPE_CONFIG[ItemType.MAINLICENSE]['items_key']] = components

        with open("resultsInProgress/mainLicenseRequiringComponents.json","w", encoding="utf-8" ) as f1:
            json.dump(shared[TYPE_CONFIG[ItemType.MAINLICENSE]['items_key']],f1,ensure_ascii=False,indent=2)

        with open("resultsInProgress/dependecies.json","w", encoding="utf-8" ) as f1:
            json.dump(shared[TYPE_CONFIG[ItemType.COMPONENT]['items_key']],f1,ensure_ascii=False,indent=2)
        
        with open("resultsInProgress/credentialComps.json","w", encoding="utf-8" ) as f1:
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

        with open('resultsInProgress/reconstructedHtml.html', "w", encoding="utf-8") as f:
            f.write(shared["reconstructedHtml"])

        document = Document()
        document.LoadFromFile('resultsInProgress/reconstructedHtml.html',FileFormat.Html, XHTMLValidationType.none)
        document.SaveToFile(f'downloads/{session_id}/Final_OSS_Readme.docx', FileFormat.Docx2019)
        document.Close()
        logger.info("We have generated the oss readme file successfully!")
        return super().post(shared, prep_res, exec_res)

class ParsingPCR(Node):

    def __init__(self, max_retries=1, wait=0):
        super().__init__(max_retries, wait)

    def prep(self, shared: Dict):
        logger.info("Now we are parsing the original PCR file.")
        PCR_path = shared.get('PCR_Path', '')

        return PCR_path

    def exec(self, prep_res):
        pcr = parse_docx_to_hierarchical_json(prep_res, 'resultsInProgress/pcr.json')
        return pcr
    
    def post(self, shared, prep_res, exec_res):
        shared['ParsedPCR'] = exec_res
        return 'default'