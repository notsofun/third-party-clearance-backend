import re, os
from bs4 import BeautifulSoup
from typing import Dict, Any
from back_end.items_utils.item_types import ItemType
import json
from fastapi.responses import JSONResponse
from docx import Document
from log_config import get_logger

logger = get_logger(__name__)  # 每个模块用自己的名称

import re

def extract_h1_content(html_string):
    """
    使用正则表达式从HTML字符串中提取<h1>标签之间的内容
    
    参数:
    html_string (str): 包含<h1>标签的HTML字符串
    
    返回:
    str: <h1>标签之间的内容，如果没有找到则返回空字符串
    """
    pattern = r'<h1>(.*?)</h1>'
    match = re.search(pattern, html_string)
    if match:
        return match.group(1)
    return ""

def format_oss_text_to_html(plain_text):
    """
    Format plain text into HTML with <br/> tags for the Siemens OSS notice.
    
    Args:
        plain_text (str): The plain text OSS notice
        
    Returns:
        str: HTML formatted text with proper <br/> tags
    """
    # Split into paragraphs
    paragraphs = plain_text.split('\n\n')
    result = []
    
    for paragraph in paragraphs:
        # Handle address block specially
        if "Siemens AG" in paragraph and "Germany" in paragraph:
            lines = paragraph.strip().split('\n')
            for line in lines:
                result.append(f"<br/>\n<br/>  {line}")
        elif "Keyword:" in paragraph:
            # Handle the keyword line
            result.append(f"<br/>\n<br/>  {paragraph}")
        else:
            # Regular paragraph
            result.append(f"<br/>\n<br/>{paragraph}")
    
    return '\n'.join(result)

def get_processing_type_from_shared(shared: Dict[str, Any], logger=logger) -> str:
    """
    从shared字典中安全获取processing_type
    
    Args:
        shared: 共享状态字典
        logger: 可选的日志记录器
    
    Returns:
        处理类型字符串
    """
    default_value = ItemType.COMPONENT.value
    
    if 'processing_type' not in shared:

        logger.warning(f"未找到处理类型(processing_type)，使用默认值: {default_value}")

        shared['processing_type'] = default_value
        
    return shared['processing_type']

def find_key_by_value(d:dict, target_value:str) -> str:
    """
    从字典中查找目标值所在的键。
    
    :param d: 字典，键值对集合。
    :param target_value: 目标值，需要查找的值。
    :return: 如果找到，返回对应的键；否则返回None。
    """
    for key, value in d.items():
        if value == target_value:
            return key
    return None

def clean_license_title(title):
    # 去掉前面的编号和冒号，去掉后面的特殊符号和空格
    # 例如 "4: Apache-2.0⇧" -> "Apache-2.0"
    return re.sub(r'^\d+:\s*', '', title).replace('⇧', '').strip()

def clean_text(text):
    """清理文本，移除特殊符号如⇧和多余的空白"""
    if not text:
        return ""
    # 移除⇧符号和多余的空白
    cleaned = re.sub(r'\s*⇧\s*', '', text)
    # 移除多余的空白
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()

def reverse_exec(final_result):
    """
    理想输入格式
    final_Result = {
        "meta": meta,
        'project_title': project_title
        "intro_html": intro_html,
        "release_overview": release_overview,
        "releases": releases,
        "license_texts": license_texts,
        "extra_html": extra_html
    }
    
    """
    
    # 创建空白HTML结构
    soup = BeautifulSoup("", "html.parser")

    # 构造HTML根节点（doctype在实际文件中作为声明，BeautifulSoup通常无需显式指定doctype）
    html = soup.new_tag("html")
    soup.append(html)
    
    # 填充head:
    head_html = BeautifulSoup(final_result["meta"]["head"], "html.parser")

    head = soup.new_tag('head')
    html.append(head)

    if head_html.meta:
        head.append(head_html.meta)

    # 找到原始样式标签
    original_style = head_html.find("style")
    if original_style:
        # 创建新的样式标签
        new_style = soup.new_tag("style")
        new_style["type"] = "text/css"
        
        # 合并原始样式和新样式
        new_style.string = original_style.string + """
        /* 新添加的居中标题样式 */
        .centered-title {
            text-align: center;
            margin: 20px 0;
            font-size: 24px;
            font-weight: bold;
        }

        /* 小字注释样式 */
        .note-to-resellers {
            text-align: left;
            font-size: 12px;
            margin-bottom: 20px;
            font-style: italic;
            color: #555;
        }

        /* 目录样式 */
        .toc-header {
            font-size: 16px;
            font-weight: bold;
            margin: 20px 0 15px 0;
        }
        
        .toc-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 30px;
            border: none;
        }
        
        .toc-table td {
            padding: 3px 0;
            font-size: 12px;
            vertical-align: bottom;
            border: none;
        }
        
        .toc-number {
            width: 30px;
            padding-right: 5px !important;
        }
        
        .toc-dots {
            width: auto;
            border-bottom: 1px dotted #999;
        }
        
        .toc-page {
            width: 20px;
            text-align: right;
            padding-left: 5px !important;
        }
        
        .page-break {
            page-break-after: always;
            height: 0;
            display: block;
        }
        """
        head.append(new_style)

    # 填充body:
    body = soup.new_tag("body")
    html.append(body)

    # 添加靠左展示的小字注释
    note = soup.new_tag("p")
    note["class"] = "note-to-resellers"
    note.string = "Note to Resellers: Please pass on this document to your customer to avoid license infringements."
    body.append(note)

    # 添加居中的标题（在intro_html之前）
    title_html = f"<h1 class='centered-title'>Third-Party Software Information for <br/> {final_result.get('project_title', '')}</h1>"
    title_soup = BeautifulSoup(title_html, "html.parser")
    body.append(title_soup.h1)

    # intro_html部分：
    intro_soup = BeautifulSoup(final_result["intro_html"], "html.parser")
    body.append(intro_soup)

    # releaseOverview部分（格式化目录）：
    if final_result["release_overview"]:
        # 添加目录标题
        toc_header = soup.new_tag("div", **{"class": "toc-header"})
        toc_header.string = "Table of Contents"
        body.append(toc_header)
        
        # 创建表格
        table = soup.new_tag("table", **{"class": "toc-table", "id": "releaseOverview"})
        body.append(table)
        
        # 添加主目录条目
        tr = soup.new_tag("tr")
        
        td_number = soup.new_tag("td", **{"class": "toc-number"})
        td_number.string = "1."
        tr.append(td_number)
        
        td_text = soup.new_tag("td")
        td_text.string = "Third Party Software Components"
        tr.append(td_text)
        
        td_dots = soup.new_tag("td", **{"class": "toc-dots"})
        tr.append(td_dots)
        
        td_page = soup.new_tag("td", **{"class": "toc-page"})
        td_page.string = "3"
        tr.append(td_page)
        
        table.append(tr)
        
        # 添加子目录条目
        for i, item in enumerate(final_result["release_overview"], 1):
            tr = soup.new_tag("tr")
            
            # 添加编号 (1.1, 1.2, 等)
            td_number = soup.new_tag("td", **{"class": "toc-number"})
            td_number.string = f"1.{i}"
            tr.append(td_number)
            
            # 添加文本内容并链接到对应的锚点
            td_text = soup.new_tag("td")
            if item["href_id"]:
                a_tag = soup.new_tag("a", href=f'#{item["href_id"]}')
                a_tag.string = item["text"]
                td_text.append(a_tag)
            else:
                td_text.string = item["text"]
            tr.append(td_text)
            
            # 添加点线
            td_dots = soup.new_tag("td", **{"class": "toc-dots"})
            tr.append(td_dots)
            
            # 添加页码
            td_page = soup.new_tag("td", **{"class": "toc-page"})
            td_page.string = "3"  # 可以根据需要调整页码
            tr.append(td_page)
            
            table.append(tr)
        
        # 添加分页符
        page_break = soup.new_tag("div", **{"class": "page-break"})
        body.append(page_break)

# 创建内容部分
    content_sections = []
    
    # 创建主标题
    main_heading = soup.new_tag("h1", id="third-party-components")
    main_heading.string = "1. Third Party Software Components"
    content_sections.append(main_heading)
    
    # 处理每个release
    for i, release in enumerate(final_result['releases'], 1):
        release_name = clean_text(release.get("name", ""))
        release_id = f"release-{i}"
        
        # 添加到目录
        release_row = soup.new_tag("tr")
        # toc_table.append(release_row)
        
        num_td = soup.new_tag("td", **{"class": "toc-number"})
        num_td.string = f"1.{i}"
        release_row.append(num_td)
        
        text_td = soup.new_tag("td")
        release_link = soup.new_tag("a", href=f"#{release_id}")
        release_link.string = release_name
        text_td.append(release_link)
        release_row.append(text_td)
        
        dots_td = soup.new_tag("td", **{"class": "toc-dots"})
        release_row.append(dots_td)
        
        page_td = soup.new_tag("td", **{"class": "toc-page"})
        page_td.string = f"{i+1}"  # 假设每个release占一页
        release_row.append(page_td)
        
        # 创建release标题
        release_heading = soup.new_tag("h2", id=release_id)
        release_heading.string = f"1.{i} {release_name}"
        content_sections.append(release_heading)
        
        # 子节点计数器
        sub_section = 1
        
        # 处理Acknowledgement（如果有）
        if "acknowledgement" in release and release["acknowledgement"]:
            ack_id = f"{release_id}-acknowledgement"
            
            # 添加到目录
            ack_row = soup.new_tag("tr")
            # toc_table.append(ack_row)
            
            num_td = soup.new_tag("td", **{"class": "toc-number"})
            num_td.string = f"1.{i}.{sub_section}"
            ack_row.append(num_td)
            
            text_td = soup.new_tag("td")
            ack_link = soup.new_tag("a", href=f"#{ack_id}")
            ack_link.string = "Acknowledgement"
            text_td.append(ack_link)
            ack_row.append(text_td)
            
            dots_td = soup.new_tag("td", **{"class": "toc-dots"})
            ack_row.append(dots_td)
            
            page_td = soup.new_tag("td", **{"class": "toc-page"})
            page_td.string = f"{i+1}"
            ack_row.append(page_td)
            
            # 创建Acknowledgement标题和内容
            ack_heading = soup.new_tag("h3", id=ack_id)
            ack_heading.string = f"1.{i}.{sub_section} Acknowledgement"
            content_sections.append(ack_heading)
            
            ack_content = soup.new_tag("pre")
            ack_content.string = release["acknowledgement"]
            content_sections.append(ack_content)
            
            sub_section += 1
        
        # 处理Copyright（如果有）
        if "copyright" in release and release["copyright"]:
            copyright_id = f"{release_id}-copyright"
            
            # 添加到目录
            copyright_row = soup.new_tag("tr")
            # toc_table.append(copyright_row)
            
            num_td = soup.new_tag("td", **{"class": "toc-number"})
            num_td.string = f"1.{i}.{sub_section}"
            copyright_row.append(num_td)
            
            text_td = soup.new_tag("td")
            copyright_link = soup.new_tag("a", href=f"#{copyright_id}")
            copyright_link.string = "Copyrights"
            text_td.append(copyright_link)
            copyright_row.append(text_td)
            
            dots_td = soup.new_tag("td", **{"class": "toc-dots"})
            copyright_row.append(dots_td)
            
            page_td = soup.new_tag("td", **{"class": "toc-page"})
            page_td.string = f"{i+1}"
            copyright_row.append(page_td)
            
            # 创建Copyright标题和内容
            copyright_heading = soup.new_tag("h3", id=copyright_id)
            copyright_heading.string = f"1.{i}.{sub_section} Copyrights"
            content_sections.append(copyright_heading)
            
            copyright_content = soup.new_tag("pre")
            copyright_content.string = release["copyright"]
            content_sections.append(copyright_content)
            
            sub_section += 1
        
        # 处理Licenses（如果有）
        if "license_names" in release and release["license_names"]:
            licenses_id = f"{release_id}-licenses"
            
            # 添加到目录
            licenses_row = soup.new_tag("tr")
            # toc_table.append(licenses_row)
            
            num_td = soup.new_tag("td", **{"class": "toc-number"})
            num_td.string = f"1.{i}.{sub_section}"
            licenses_row.append(num_td)
            
            text_td = soup.new_tag("td")
            licenses_link = soup.new_tag("a", href=f"#{licenses_id}")
            licenses_link.string = "Licenses"
            text_td.append(licenses_link)
            licenses_row.append(text_td)
            
            dots_td = soup.new_tag("td", **{"class": "toc-dots"})
            licenses_row.append(dots_td)
            
            page_td = soup.new_tag("td", **{"class": "toc-page"})
            page_td.string = f"{i+1}"
            licenses_row.append(page_td)
            
            # 创建Licenses标题
            licenses_heading = soup.new_tag("h3", id=licenses_id)
            licenses_heading.string = f"1.{i}.{sub_section} Licenses"
            content_sections.append(licenses_heading)
            
            # 处理每个license
            for j, (license_name, license_text) in enumerate(zip(release["license_names"], release["license_texts"]), 1):
                license_id = f"{licenses_id}-{j}"
                
                # 添加到目录
                license_row = soup.new_tag("tr")
                # toc_table.append(license_row)
                
                num_td = soup.new_tag("td", **{"class": "toc-number"})
                num_td.string = f"1.{i}.{sub_section}.{j}"
                license_row.append(num_td)
                
                text_td = soup.new_tag("td")
                license_link = soup.new_tag("a", href=f"#{license_id}")
                license_link.string = license_name
                text_td.append(license_link)
                license_row.append(text_td)
                
                dots_td = soup.new_tag("td", **{"class": "toc-dots"})
                license_row.append(dots_td)
                
                page_td = soup.new_tag("td", **{"class": "toc-page"})
                page_td.string = f"{i+1}"
                license_row.append(page_td)
                
                # 创建License标题和内容
                license_heading = soup.new_tag("h4", id=license_id)
                license_heading.string = f"1.{i}.{sub_section}.{j} {license_name}"
                content_sections.append(license_heading)
                
                license_content = soup.new_tag("pre")
                license_content.string = license_text
                content_sections.append(license_content)
    
    # 添加所有内容部分
    for section in content_sections:
        body.append(section)

    # 渲染回HTML字符串
    reconstructed_html = f'<!DOCTYPE {final_result["meta"]["doctype"]}>\n' + str(soup)
    
    return reconstructed_html

def json_strip(text:str) -> str:

    # 后处理：去除 ```json ... ``` 或 ``` ... ```
    response_strip = text.strip()
    if response_strip.startswith('```json'):
        response_strip = response_strip[7:].strip()
    if response_strip.startswith('```'):
        response_strip = response_strip[3:].strip()
    if response_strip.endswith('```'):
        response_strip = response_strip[:-3].strip()
    try:
        data = json.loads(response_strip)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError: # 更具体的捕获 JSON 解析错误
        return None # 失败时返回 None
    except Exception: # 捕获其他可能的异常
        return None


def load_json_files_as_variables(directory='filtered_results'):
    """
    批量读取指定目录下的所有JSON文件，并使用文件名作为变量名
    
    参数:
    directory - JSON文件所在的目录
    
    返回:
    包含所有加载的JSON数据的字典，键为文件名(不含扩展名)
    """
    # 存储结果的字典
    result_dict = {}
    
    try:
        # 确保目录存在
        if not os.path.exists(directory):
            logger.error(f"错误：目录 '{directory}' 不存在")
            return {}
        
        # 遍历目录中的所有文件
        for filename in os.listdir(directory):
            if filename.endswith('.json'):
                # 构建完整的文件路径
                file_path = os.path.join(directory, filename)
                
                # 提取不含扩展名的文件名作为变量名
                var_name = os.path.splitext(filename)[0]
                
                try:
                    # 读取JSON文件
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    # 将数据存储在结果字典中
                    result_dict[var_name] = data
                    # print(f"成功加载: {filename} -> 变量 '{var_name}'")
                    
                except Exception as e:
                    logger.error(f"读取文件 '{filename}' 时出错: {str(e)}")
        
        return result_dict
        
    except Exception as e:
        logger.error(f"处理目录时出错: {str(e)}")
        return {}

def get_strict_json(model:object, user_input, var=False, tags:list = None):
    """
    Try response up to 5 times until getting strictly valid JSON.
    No user perception of retries.
    model could be an object of a bot or a langchain model.

    var is used to decide whether request with variables or not
    """
    for _ in range(5):
        if var:
            response = model._fixed_request(user_input)
        else:
            response = model._request(user_input, tags)

        result = json_strip(response)
        if result:
            return result
    raise RuntimeError("Model did not give valid JSON after retries.")

def get_strict_string(model:object, user_input):

    """Try to get responses up to 5 times until getting strictly valid string.
    No user perception of retries.
    Model could be an object of a bot or a langchain model.
    """

    for _ in range(5):
        response = model._request(user_input)
        response = response.strip().lower()
        if isinstance(response,str):
            return response
    raise RuntimeError("Model did not give a strictly string response")

def create_error_response(error_code: str, error_message: str, status_code: int = 400):
    """创建统一的错误响应"""
    logger.error(f"Error {error_code}: {error_message}")
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error_code": error_code,
            "error_message": error_message
        }
    )

def create_success_response(data: dict, message: str = "Success"):
    """创建统一的成功响应"""
    return {
        "success": True,
        "message": message,
        "data": data
    }

def read_doc(file_path: str):
    '''
    用于阅读指定路径的doc文件，来生成python like的格式
    '''

    doc = Document(file_path)

    content = [paragraph.text
                for paragraph in doc.paragraphs]

    full_content = '\n'.join(content)

    return full_content

if __name__ == "__main__":
    with open(r"C:\Users\z0054unn\Documents\Siemens-GitLab\Third-party\third-party-clearance\parsed_original_oss.json","r",encoding="utf-8") as f:
        final_result = json.load(f)
        for key,value in final_result.items():
            print(final_result)
        html_output = reverse_exec(final_result)
        with open(r"C:\Users\z0054unn\Documents\Siemens-GitLab\Third-party\third-party-clearance\restored_document.html", "w", encoding="utf-8") as file:
            file.write(html_output)