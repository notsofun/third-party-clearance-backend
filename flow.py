from pocketflow import Flow
from nodes import (ParsingOriginalHtml, LicenseReviewing, RiskCheckingRAG,
                    ossGenerating, initializeSession, GetUserConfirming,
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

def chat_flow():
    """交互确认流程"""
    confirmingNode = GetUserConfirming()
    confirmingNode - 'continue' >> confirmingNode

    return Flow(start=confirmingNode)

def post_chat_flow():
    """报告生成流程"""
    ossGenNode = ossGenerating()
    return Flow(start=ossGenNode)