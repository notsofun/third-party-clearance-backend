from pocketflow import Flow
from nodes import (ParsingOriginalHtml, LicenseReviewing, RiskCheckingRAG,
                    initializeSession, itemFiltering, getFinalOSS,
                    SpecialLicenseCollecting, DependecyCheckingRAG)

def pre_chat_flow():
    """解析和风险分析流程"""
    parsingNode = ParsingOriginalHtml()
    riskAnalysisNode = LicenseReviewing()
    collectionNode = SpecialLicenseCollecting()
    riskCheckingNode = RiskCheckingRAG()
    sessionNode = initializeSession()
    dependecyCheckingNode = DependecyCheckingRAG()
    
    parsingNode >> riskAnalysisNode >> collectionNode >> riskCheckingNode >> dependecyCheckingNode >> sessionNode
    return Flow(start=parsingNode)

def post_chat_flow():
    """报告生成流程"""
    item_filtering = itemFiltering()
    get_html = getFinalOSS()

    item_filtering >> get_html
    return Flow(start=item_filtering)

def test_flow():
    '''为了测试节点而设置的工作流'''
    parsingNode = ParsingOriginalHtml()

    parsingNode

    return Flow(start=parsingNode)