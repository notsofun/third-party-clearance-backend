from pocketflow import Flow
from nodes import (ParsingOriginalHtml, LicenseReviewing, RiskCheckingRAG)

def review_oss_readme():
    """
    To delete risky components in this project
    """

    parsingNode = ParsingOriginalHtml()

    riskAnalysisNode = LicenseReviewing()

    riskCheckingNode = RiskCheckingRAG()

    parsingNode >> riskAnalysisNode >> riskCheckingNode

    review_flow = Flow(start=parsingNode)

    return review_flow