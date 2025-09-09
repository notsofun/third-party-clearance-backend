import re
from bs4 import BeautifulSoup

def parse_html(data:BeautifulSoup):
    '''将Html文件解析为json数据'''
    if data is None:
        return None
    
    project_title = [h1.text for h1 in data.find_all('h1')][0]

    meta = {
        "doctype" : "html",
        "head" : str(data.head),
        "title" : data.title.text if data.title else "",
        "project_title": project_title,
    }

    body = data.body
    all_body_html = str(body)
    overview = data.find("ul", id="releaseOverview")
    if overview:
        intro_html = all_body_html.split(str(overview))[0]
        intro_html = intro_html.replace("<body>", "").strip()
    else:
        intro_html = all_body_html

    # release overview目录
    release_overview = []
    if overview:
        for li in overview.find_all("li"):
            t = li.text.strip()
            id_match = re.search(r'h3(.+)_([\d\.]+)', li.a['href']) if li.find('a') else None
            if id_match:
                name = id_match.group(1).replace("_", " ").replace("-", " ").strip()
                version = id_match.group(2)
                href_id = li.a['href'].strip("#")
            else:
                # fallback
                match = re.search(r'\s+((?:V|v)?\d[\d\.\s]*(?:\s*rel\d+)?)$', t)
                if match:
                    version = match.group(1).strip()
                    name = t[:match.start()].strip()
                else:
                    name, version = t, ""
                href_id = li.a['href'].strip("#") if li.find('a') else ""
            release_overview.append({
                "name": name,
                "version": version,
                "href_id": href_id,
                "text": t
            })

    # release详情分块
    releases = []
    for li in data.find_all("li", class_="release"):
        block = {}

        # 组件名与版本
        h3 = li.find("h3")
        if h3:
            name_ver = h3.text.strip().replace("↩", "").strip()
            version_match = re.search(r'\s+((?:V|v)?\d[\d\.\s]*(?:\s*rel\d+)?)$', name_ver)
            if version_match:
                name = version_match.group(1).strip()
                version = version_match.group(2).strip()
            else:
                name, version = name_ver, ""
            block["name"] = name
            block["version"] = version
            block["block_html"] = str(li)  # 原始HTML备份

        # license名
        licenses = []
        for l in li.select('.licenseEntry'):
            licenses.append(l['title'])
        block["license_names"] = licenses

        # license原文
        license_texts = []
        for license_link in li.select('.licenseEntry a'):
            href = license_link.attrs.get('href', '')
            if href.startswith("#licenseTextItem"):
                lic_text_block = data.select_one(href)
                if lic_text_block and lic_text_block.pre:
                    ltxt = lic_text_block.pre.text.strip()
                    license_texts.append(ltxt)
        block["license_texts"] = license_texts

        # Copyright/Ack
        cp_pre = li.find("pre", class_="copyrights")
        block['copyright'] = cp_pre.text.strip() if cp_pre else ""
        ack_pre = li.find("pre", class_="acknowledgements")
        block['acknowledgement'] = ack_pre.text.strip() if ack_pre else ""

        releases.append(block)

    # license 全文区块
    license_texts = []
    ul = data.find("ul", id="licenseTexts")
    if ul:
        for lic in ul.find_all("li"):
            lic_id = lic.get("id", "")
            h3 = lic.find("h3")
            title = h3.text if h3 else ""
            pre = lic.find("pre", class_="licenseText")
            text = pre.text.strip() if pre else ""
            license_texts.append({
                "id": lic_id,
                "title": title,
                "text": text
            })

    # body后面（可能还有div、尾注等）
    # extra_html = "" # 如有尾注等自定义提取
    tail_marker = '</ul>' if ul else '</body>'
    extra_html = all_body_html.split(tail_marker)[-1]

    final_Result = {
        "meta": meta,
        "intro_html": intro_html,
        "release_overview": release_overview,
        "releases": releases,
        "license_texts": license_texts,
        "extra_html": extra_html
    }
    # 后面传组件名用text字段，license的列表在licensesNames，licenseTexts里面找实际用到的license，然后给模型title和text
    # 聚合全部

    return final_Result

if __name__ == '__main__':

    with open(r"C:\Users\z0054unn\Downloads\LicenseInfo-Wireless Room Sensor-2.0-2025-08-22_01_40_30.html", 'r', encoding='utf-8') as html:
        html_content = html.read()
        soup = BeautifulSoup(html_content, "html.parser")
        json_result = parse_html(soup)