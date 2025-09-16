from docx import Document
from docx.oxml.ns import qn
from log_config import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

doc = Document(r'uploads\test\ProjectClearingReport-Wireless Room Sensor-2.0-2025-08-28_03_14_37.docx')

body_elements = doc.element.body.iter()

for element in body_elements:
    logger.info(f'{element}')