import re
from bs4 import BeautifulSoup
import json

def clean_license_title(title):
    # 去掉前面的编号和冒号，去掉后面的特殊符号和空格
    # 例如 "4: Apache-2.0⇧" -> "Apache-2.0"
    return re.sub(r'^\d+:\s*', '', title).replace('⇧', '').strip()

def reverse_exec(final_result):
    """
    理想输入格式
    final_Result = {
        "meta": meta,
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
    soup.insert(0, html)
    
    # 填充head:
    head_html = BeautifulSoup(final_result["meta"]["head"], "html.parser")
    html.append(head_html)

    # 确保title存在：
    if soup.title:
        soup.title.string = final_result["meta"].get("title", "")
    else:
        title_tag = soup.new_tag("title")
        title_tag.string = final_result["meta"].get("title", "")
        head_html.append(title_tag)
    
    # 填充body:
    body = soup.new_tag("body")
    html.append(body)

    # intro_html部分：
    intro_soup = BeautifulSoup(final_result["intro_html"], "html.parser")
    body.append(intro_soup)

    # releaseOverview部分（目录列表）：
    if final_result["release_overview"]:
        release_overview_ul = soup.new_tag("ul", id="releaseOverview")
        for item in final_result["release_overview"]:
            li_tag = soup.new_tag("li")

            if item["href_id"]:
                a_tag = soup.new_tag("a", href=f'#{item["href_id"]}')
                a_tag.string = item["text"]
                li_tag.append(a_tag)
            else:
                li_tag.string = item["text"]

            release_overview_ul.append(li_tag)
        body.append(release_overview_ul)

    # 各release具体区块
    for block in final_result["releases"]:
        li_release = BeautifulSoup(block["block_html"], "html.parser")
        body.append(li_release)

    # 完整License全文区域
    if final_result["license_texts"]:
        license_ul = soup.new_tag("ul", id="licenseTexts")
        for lic_text_item in final_result["license_texts"]:
            lic_li = soup.new_tag("li", id=lic_text_item["id"])
            
            lic_h3 = soup.new_tag("h3")
            lic_h3.string = lic_text_item["title"]
            lic_li.append(lic_h3)

            lic_pre = soup.new_tag("pre", **{"class": "licenseText"})
            lic_pre.string = lic_text_item["text"]
            lic_li.append(lic_pre)

            license_ul.append(lic_li)
        body.append(license_ul)

    # extra_html部分
    extra_html_soup = BeautifulSoup(final_result["extra_html"], "html.parser")
    body.append(extra_html_soup)

    # 渲染回HTML字符串
    reconstructed_html = f'<!DOCTYPE {final_result["meta"]["doctype"]}>\n' + str(soup)
    
    return reconstructed_html

def get_strict_json(bot, user_input, prompt=None):
    """
    Try response up to 5 times until getting strictly valid JSON.
    No user perception of retries.
    """
    for _ in range(5):
        if prompt:
            response = bot._request(prompt)
            prompt = None
        else:
            response = bot._request(user_input)
        # 后处理：去除 ```json ... ``` 或 ``` ... ```
        response_strip = response.strip()
        if response_strip.startswith('```json'):
            response_strip = response_strip[7:].strip()
        if response_strip.startswith('```'):
            response_strip = response_strip[3:].strip()
        if response_strip.endswith('```'):
            response_strip = response_strip[:-3].strip()
        try:
            data = json.loads(response_strip)
            if isinstance(data, dict) and "result" in data and "talking" in data:
                return data
        except Exception:
            pass
        user_input = "Please provide ONLY the exact JSON object as required, no extra text."
    raise RuntimeError("Model did not give valid JSON after retries.")

if __name__ == "__main__":
    with open(r"C:\Users\z0054unn\Documents\Siemens-GitLab\Third-party\third-party-clearance\parsed_original_oss.json","r",encoding="utf-8") as f:
        final_result = json.load(f)
        html_output = reverse_exec(final_result)
        with open(r"C:\Users\z0054unn\Documents\Siemens-GitLab\Third-party\third-party-clearance\restored_document.html", "w", encoding="utf-8") as file:
            file.write(html_output)