from pocketflow import Flow
from nodes import ParsingOriginalHtml

def review_oss_readme():
    """
    To delete risky components in this project
    """

    parsingNode = ParsingOriginalHtml()

    review_flow = Flow(start=parsingNode)

    return review_flow