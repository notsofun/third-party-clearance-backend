from pocketflow import Flow
from nodes import (ParsingOriginalHtml, LicenseReviewing)

def review_oss_readme():
    """
    To delete risky components in this project
    """

    parsingNode = ParsingOriginalHtml()

    riskAnalysisNode = LicenseReviewing()

    parsingNode >> riskAnalysisNode

    review_flow = Flow(start=parsingNode)

    return review_flow