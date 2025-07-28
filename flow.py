from pocketflow import Flow
from nodes import (ParsingOriginalHtml, LicenseReviewing, RiskCheckingRAG, ossGenerating,initializeSession, GetUserConfirming)

def review_oss_readme():
    """
    To delete risky components in this project
    """

    parsingNode = ParsingOriginalHtml()

    riskAnalysisNode = LicenseReviewing()

    riskCheckingNode = RiskCheckingRAG()

    sessionNode = initializeSession()

    confirmingNode = GetUserConfirming()

    parsingNode >> riskAnalysisNode 
    
    # >> riskCheckingNode >> sessionNode >> confirmingNode

    # confirmingNode - 'continue' >> confirmingNode
    # confirmingNode - 'over' >> ossGenerating()

    review_flow = Flow(start=parsingNode)

    return review_flow