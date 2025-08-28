import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from docx import Document
import json
import re
import os
from collections import OrderedDict
from difflib import SequenceMatcher

def clean_title(title):
    """清理标题，移除页码和多余空格"""
    # 移除页码（如"标题\t2"中的"\t2"）
    title = re.sub(r'\t\d+$', '', title)
    return title.strip()

def similar(a, b):
    """计算两个字符串的相似度"""
    return SequenceMatcher(None, a, b).ratio()

def merge_hierarchical_document(input_json_path, output_json_path=None):
    """
    合并和修复层级文档结构
    
    Args:
        input_json_path: 输入JSON文件路径
        output_json_path: 输出JSON文件路径(可选)
        
    Returns:
        修复后的层级JSON文档对象
    """
    # 加载原始JSON
    with open(input_json_path, 'r', encoding='utf-8') as f:
        doc = json.load(f)
    
    sections = doc['document']['sections']
    
    # 第一步：确定数字编号章节与哈希章节的对应关系
    section_mappings = {}  # 哈希ID到数字编号的映射
    
    # 数字编号章节和它们的子章节列表
    numbered_sections = {key: sections[key] for key in sections if re.match(r'^\d+(\.\d+)*$', key)}
    hash_sections = {key: sections[key] for key in sections if key.startswith('h')}
    
    # 为每个哈希章节找到匹配的数字章节
    for hash_key, hash_section in hash_sections.items():
        hash_title = clean_title(hash_section['title'])
        best_match = None
        best_match_ratio = 0
        
        for num_key, num_section in numbered_sections.items():
            num_title = clean_title(num_section['title'])
            ratio = similar(hash_title, num_title)
            
            if ratio > best_match_ratio and ratio > 0.7:  # 70%相似度阈值
                best_match = num_key
                best_match_ratio = ratio
        
        if best_match:
            section_mappings[hash_key] = best_match
    
    # 第二步：合并章节内容
    for hash_key, num_key in section_mappings.items():
        hash_section = sections[hash_key]
        num_section = None
        
        # 处理子章节路径
        if '.' in num_key:
            parts = num_key.split('.')
            parent_key = parts[0]
            if parent_key in sections:
                current = sections[parent_key]
                for i in range(1, len(parts)):
                    path_so_far = '.'.join(parts[:i+1])
                    if path_so_far in current['children']:
                        current = current['children'][path_so_far]
                num_section = current
        else:
            if num_key in sections:
                num_section = sections[num_key]
        
        # 合并内容和表格
        if num_section:
            # 合并内容
            if not num_section['content'] and hash_section['content']:
                num_section['content'] = hash_section['content']
            
            # 合并表格
            if hash_section['tables']:
                num_section['tables'].extend(hash_section['tables'])
    
    # 第三步：删除哈希章节
    for hash_key in hash_sections:
        if hash_key in sections:
            del sections[hash_key]
    
    # 第四步：验证并更新元数据
    total_sections = 0
    total_tables = 0
    
    def count_sections(node):
        nonlocal total_sections, total_tables
        if isinstance(node, dict):
            total_sections += 1
            total_tables += len(node.get('tables', []))
            
            for child in node.get('children', {}).values():
                count_sections(child)
    
    # 计算章节和表格数量
    for section in sections.values():
        count_sections(section)
    
    # 更新元数据
    doc['document']['metadata']['total_sections'] = total_sections
    doc['document']['metadata']['total_tables'] = total_tables
    
    # 保存结果
    if output_json_path:
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
    
    return doc

# 使用示例
def process_and_fix_document(input_json_path, output_json_path=None):
    """
    处理并修复文档，合并重复章节
    
    Args:
        input_json_path: 输入JSON文件路径
        output_json_path: 输出JSON文件路径(可选)
    
    Returns:
        处理后的文档对象
    """
    print(f"正在处理文件: {input_json_path}")
    doc = merge_hierarchical_document(input_json_path, output_json_path)
    
    print("\n文档统计:")
    print(f"- 总章节数: {doc['document']['metadata']['total_sections']}")
    print(f"- 总表格数: {doc['document']['metadata']['total_tables']}")
    
    # 打印章节结构示例
    print("\n章节结构示例:")
    sections = doc['document']['sections']
    for key in sorted(list(sections.keys()))[:3]:  # 显示前3个章节
        section = sections[key]
        print(f"- {key}: {section['title']}")
        
        # 显示内容摘要
        if section['content']:
            content_preview = section['content'][:50] + "..." if len(section['content']) > 50 else section['content']
            print(f"  内容: {content_preview}")
        
        # 显示表格数量
        if section['tables']:
            print(f"  表格: {len(section['tables'])}个")
        
        # 显示子章节
        if section['children']:
            print(f"  子章节:")
            for child_key, child in list(section['children'].items())[:2]:  # 显示前2个子章节
                print(f"    - {child_key}: {child['title']}")
    
    if output_json_path:
        print(f"\n已保存到: {output_json_path}")
    
    return doc

# 调用示例
# fixed_doc = process_and_fix_document("input.json", "fixed_output.json")

def parse_docx_to_hierarchical_json(docx_path, output_path=None):
    """
    解析Word文档为层级化的JSON结构
    
    Args:
        docx_path: Word文档路径
        output_path: 输出JSON文件路径(可选)
        
    Returns:
        层级化的JSON文档对象
    """
    doc = Document(docx_path)
    
    # 创建基本文档结构
    document = {
        "document": {
            "title": os.path.basename(docx_path).split('.')[0],
            "metadata": {
                "total_sections": 0,
                "total_tables": 0,
                "version": "1.0",
                "document_type": "Word Document"
            },
            "sections": {}
        }
    }
    
    # 第一步：识别目录并建立章节框架
    toc_entries = extract_toc_entries(doc)
    if toc_entries:
        build_chapter_structure(document["document"]["sections"], toc_entries)
    
    # 第二步：遍历文档并填充内容
    fill_document_content(doc, document["document"]["sections"])
    
    # 第三步：处理表格并分配到对应章节
    process_tables(doc, document["document"]["sections"])
    
    # 最后：计算统计数据
    calculate_document_stats(document)
    
    # 保存结果
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(document, f, ensure_ascii=False, indent=2)
    
    return document

def extract_toc_entries(doc):
    """
    从文档中提取目录项
    """
    toc_entries = []
    in_toc = False
    
    for i, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        
        # 检测目录的开始和结束
        if text.lower() == 'table of contents' or text.lower() == 'contents':
            in_toc = True
            continue
        
        # 如果已经离开目录区域，停止处理
        if in_toc and not text:
            # 连续两个空行可能表示目录结束
            if i + 1 < len(doc.paragraphs) and not doc.paragraphs[i + 1].text.strip():
                in_toc = False
                continue
        
        if in_toc:
            # 检查是否为目录项（通常包含章节编号和页码）
            # 目录项格式通常为: "1. Introduction....................10"
            match = re.match(r'^([\d\.]+)\s+([^\.]+).*?(\d+)$', text)
            if match:
                number = match.group(1).strip()
                title = match.group(2).strip()
                toc_entries.append({
                    'number': number,
                    'title': title,
                    'level': len(number.split('.'))
                })
            
            # 处理没有编号的目录项
            elif re.search(r'\.*\d+$', text):  # 以页码结尾
                # 尝试提取标题和页码
                parts = re.split(r'\.{2,}', text)
                if len(parts) >= 2:
                    title = parts[0].strip()
                    toc_entries.append({
                        'number': f"h{len(toc_entries) + 1}",  # 生成一个编号
                        'title': title,
                        'level': 1  # 默认为顶级
                    })
    
    # 如果没有找到目录，尝试通过标题样式识别章节结构
    if not toc_entries:
        toc_entries = extract_chapters_by_headings(doc)
    
    return toc_entries

def extract_chapters_by_headings(doc):
    """
    通过标题样式识别章节结构
    """
    chapters = []
    
    for para in doc.paragraphs:
        if not para.text.strip():
            continue
        
        style_name = para.style.name.lower() if para.style and hasattr(para.style, 'name') else ""
        is_heading = 'heading' in style_name
        
        if is_heading:
            # 提取标题级别
            heading_level = 1
            if re.search(r'heading\s+(\d+)', style_name):
                heading_level = int(re.search(r'heading\s+(\d+)', style_name).group(1))
            
            # 提取章节编号和标题
            number, title = extract_chapter_number(para.text)
            
            if number is None:
                number = f"h{len(chapters) + 1}"
            
            chapters.append({
                'number': number,
                'title': title,
                'level': heading_level
            })
    
    # 如果仍然没有找到章节，尝试从普通段落中提取
    if not chapters:
        chapters = extract_chapters_from_paragraphs(doc)
    
    return chapters

def extract_chapters_from_paragraphs(doc):
    """
    通过段落内容识别章节结构
    """
    chapters = []
    
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        
        # 尝试识别章节标题（通常以数字开头）
        number, title = extract_chapter_number(text)
        
        if number:
            level = len(number.split('.'))
            chapters.append({
                'number': number,
                'title': title,
                'level': level
            })
    
    return chapters

def extract_chapter_number(text):
    """
    从文本中提取章节编号
    """
    # 匹配如 "1. Introduction" 或 "1.2.3 Details"
    match = re.match(r'^(\d+(\.\d+)*)\s*(.+)$', text.strip())
    if match:
        return match.group(1).strip(), match.group(3).strip()
    
    # 特殊情况：只有数字的标题
    if text.isdigit():
        return text, "Section " + text
    
    return None, text.strip()

def build_chapter_structure(sections, toc_entries):
    """
    根据目录项建立章节框架
    """
    for entry in toc_entries:
        number = entry['number']
        title = entry['title']
        
        # 创建基本章节结构
        section = {
            "title": title,
            "content": "",
            "tables": [],
            "children": {}
        }
        
        # 如果是顶级章节，直接添加
        if '.' not in number or not number.replace('.', '').isdigit():
            sections[number] = section
        else:
            # 否则，找到父章节并添加为子章节
            parts = number.split('.')
            parent_key = '.'.join(parts[:-1])
            
            # 递归创建父章节（如果不存在）
            parent = find_or_create_parent(sections, parent_key)
            
            # 添加到父章节
            parent["children"][number] = section

def find_or_create_parent(sections, parent_key):
    """
    查找或创建父章节
    """
    # 如果父章节存在于顶级，直接返回
    if parent_key in sections:
        return sections[parent_key]
    
    # 否则递归查找或创建
    if '.' in parent_key:
        parts = parent_key.split('.')
        grand_parent_key = '.'.join(parts[:-1])
        last_part = parts[-1]
        
        # 递归找到祖父章节
        grand_parent = find_or_create_parent(sections, grand_parent_key)
        
        # 创建父章节（如果不存在）
        if parent_key not in grand_parent["children"]:
            grand_parent["children"][parent_key] = {
                "title": f"Section {parent_key}",
                "content": "",
                "tables": [],
                "children": {}
            }
        
        return grand_parent["children"][parent_key]
    
    # 创建顶级父章节
    sections[parent_key] = {
        "title": f"Section {parent_key}",
        "content": "",
        "tables": [],
        "children": {}
    }
    
    return sections[parent_key]

def fill_document_content(doc, sections):
    """
    遍历文档内容，填充到对应章节
    """
    current_section = None
    current_content = []
    
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        
        # 检查是否是标题
        style_name = para.style.name.lower() if para.style and hasattr(para.style, 'name') else ""
        is_heading = 'heading' in style_name
        
        # 提取章节编号和标题
        number, title = extract_chapter_number(text)
        
        if is_heading or number:
            # 保存当前章节内容
            if current_section and current_content:
                section_obj = find_section_by_key(sections, current_section)
                if section_obj:
                    section_obj["content"] = "\n\n".join(current_content)
                current_content = []
            
            # 设置当前章节
            current_section = number if number else f"h{hash(text) % 10000}"
            
            # 如果章节不存在于框架中，添加它
            if not find_section_by_key(sections, current_section):
                # 检查是否是子章节
                if '.' in current_section and current_section.replace('.', '').isdigit():
                    parts = current_section.split('.')
                    parent_key = '.'.join(parts[:-1])
                    parent = find_or_create_parent(sections, parent_key)
                    parent["children"][current_section] = {
                        "title": title,
                        "content": "",
                        "tables": [],
                        "children": {}
                    }
                else:
                    sections[current_section] = {
                        "title": title,
                        "content": "",
                        "tables": [],
                        "children": {}
                    }
        else:
            # 添加到当前章节的内容
            if current_section:
                current_content.append(text)
    
    # 保存最后一个章节的内容
    if current_section and current_content:
        section_obj = find_section_by_key(sections, current_section)
        if section_obj:
            section_obj["content"] = "\n\n".join(current_content)

def find_section_by_key(sections, key):
    """
    根据键查找章节对象
    """
    # 直接在顶级查找
    if key in sections:
        return sections[key]
    
    # 在子章节中递归查找
    for section_key, section in sections.items():
        if 'children' in section and section['children']:
            result = find_section_by_key(section['children'], key)
            if result:
                return result
    
    return None

def process_tables(doc, sections):
    """
    处理表格并分配到对应章节
    """
    current_section = None
    
    # 遍历文档，确定当前章节位置
    for i, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        if not text:
            continue
        
        # 检查是否是标题
        style_name = para.style.name.lower() if para.style and hasattr(para.style, 'name') else ""
        is_heading = 'heading' in style_name
        
        # 提取章节编号和标题
        number, title = extract_chapter_number(text)
        
        if is_heading or number:
            current_section = number if number else f"h{hash(text) % 10000}"
    
    # 处理所有表格
    for table_idx, table in enumerate(doc.tables):
        # 解析表格为行对象数组
        table_data = parse_table(table)
        
        if current_section:
            # 找到当前章节并添加表格
            section_obj = find_section_by_key(sections, current_section)
            if section_obj:
                section_obj["tables"].extend(table_data)
        else:
            # 如果没有当前章节，添加到最后一个章节
            last_section_key = list(sections.keys())[-1] if sections else None
            if last_section_key:
                sections[last_section_key]["tables"].extend(table_data)

def parse_table(table):
    """
    解析Word表格为行对象数组
    
    格式: [{"header1": "value1", "header2": "value2"}, ...]
    """
    if not table.rows:
        return []
        
    # 提取表头
    headers = []
    for cell in table.rows[0].cells:
        header = cell.text.strip()
        if header:
            headers.append(header)
        else:
            headers.append(f"Column{len(headers) + 1}")
    
    # 提取数据行
    rows = []
    for row_idx in range(1, len(table.rows)):
        row = table.rows[row_idx]
        row_data = {}
        
        for col_idx, cell in enumerate(row.cells):
            if col_idx < len(headers):
                header = headers[col_idx]
                cell_text = cell.text.strip().replace("\n", " ")
                row_data[header] = cell_text
        
        if row_data:  # 只添加非空行
            rows.append(row_data)
    
    return rows

def calculate_document_stats(document):
    """
    计算文档统计数据
    """
    def count_items(node):
        result = {"sections": 0, "tables": 0}
        
        if isinstance(node, dict):
            if 'title' in node:  # 这是一个章节节点
                result["sections"] += 1
                
                # 计算表格
                if 'tables' in node and isinstance(node['tables'], list):
                    result["tables"] += len(node['tables'])
                
                # 递归处理子章节
                if 'children' in node and isinstance(node['children'], dict):
                    for child in node['children'].values():
                        child_count = count_items(child)
                        result["sections"] += child_count["sections"]
                        result["tables"] += child_count["tables"]
            
            # 处理非章节节点
            elif 'sections' in node:
                for section in node['sections'].values():
                    section_count = count_items(section)
                    result["sections"] += section_count["sections"]
                    result["tables"] += section_count["tables"]
        
        return result
    
    # 计算统计数据
    counts = count_items(document["document"])
    document["document"]["metadata"]["total_sections"] = counts["sections"]
    document["document"]["metadata"]["total_tables"] = counts["tables"]

# 使用示例
def process_docx_file(docx_path, output_path=None):
    """
    处理Word文档并生成层级化JSON
    
    Args:
        docx_path: Word文档路径
        output_path: 输出JSON文件路径(可选)
    
    Returns:
        处理后的文档对象
    """
    print(f"正在处理Word文档: {docx_path}")
    document = parse_docx_to_hierarchical_json(docx_path, output_path)
    
    print("\n文档统计:")
    print(f"- 总章节数: {document['document']['metadata']['total_sections']}")
    print(f"- 总表格数: {document['document']['metadata']['total_tables']}")
    print(f"- 顶级章节数: {len(document['document']['sections'])}")
    
    # 打印部分章节结构
    print("\n章节结构示例:")
    sections = document["document"]["sections"]
    for i, (key, section) in enumerate(list(sections.items())[:3]):  # 显示前3个章节
        print(f"{i+1}. {key}: {section['title']}")
        if section['children']:
            child_keys = list(section['children'].keys())[:2]  # 显示前2个子章节
            for child_key in child_keys:
                child = section['children'][child_key]
                print(f"   - {child_key}: {child['title']}")
            if len(section['children']) > 2:
                print(f"   - ... (还有 {len(section['children']) - 2} 个子章节)")
    
    if output_path:
        print(f"\n已保存到: {output_path}")
        print(f"文件大小: {os.path.getsize(output_path)} 字节")
    
    return document

# 示例使用
if __name__ == "__main__":
    doc_path = r"uploads\test\ProjectClearingReport-Wireless Room Sensor-2.0-2025-08-28_03_14_37.docx"

    json_output =process_docx_file(doc_path, 'uploads/test/test.json')
    print(json_output)
    # print(json_output)