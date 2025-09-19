# Markdown文档构建器类
class MarkdownDocumentBuilder:
    """用于构建多章节Markdown文档的工具类"""
    
    def __init__(self, title=None):
        """
        初始化Markdown文档构建器
        
        Args:
            title (str, optional): 文档标题，如果提供，将作为H1标题添加
        """
        self.sections = []
        self.title = title
    
    def add_section(self, content, title=None, position=None):
        """
        添加文档章节
        
        Args:
            title (str): 章节标题
            content (str): 章节内容，可以包含转义字符
            position (int, optional): 插入位置，默认添加到末尾
        
        Returns:
            int: 章节在文档中的索引
        """
        # 处理转义字符
        if content and isinstance(content, str):
            # 尝试使用unicode_escape解码
            try:
                content = content.encode().decode('unicode_escape')
            except UnicodeDecodeError:
                # 如果失败，尝试直接替换字面的\n
                content = content.replace('\\n', '\n')
                content = content.replace('\\t', '\t')
        
        # 准备章节内容
        if title:
            section_content = f"# {title}\n\n{content}\n\n"
        else:
            section_content = f"{content}\n\n"
        
        # 插入到指定位置或添加到末尾
        if position is not None and 0 <= position < len(self.sections):
            self.sections.insert(position, section_content)
            return position
        else:
            self.sections.append(section_content)
            return len(self.sections) - 1
        
    def find_section_index_by_title(self, title):
        """
        根据章节标题查找其在文档中的索引。
        
        Args:
            title (str): 要查找的章节标题。
        
        Returns:
            int: 如果找到，返回章节的索引；如果未找到，返回 None。
        """
        if not isinstance(title, str) or not title:
            # 如果标题无效，直接返回None
            return None
            
        # 构造要查找的标题行格式，与 add_section 中保持一致
        search_pattern = f"# {title}\n\n"
        
        for index, section_content in enumerate(self.sections):
            # 检查章节内容是否以该标题行开头
            if section_content.startswith(search_pattern):
                return index
        
        # 如果遍历完所有章节都没有找到，则返回 None
        return None
    
    def remove_section(self, index):
        """
        移除指定索引的章节
        
        Args:
            index (int): 要移除的章节索引
        
        Returns:
            bool: 移除成功返回True，否则返回False
        """
        if 0 <= index < len(self.sections):
            self.sections.pop(index)
            return True
        return False
    
    def move_section(self, from_index, to_index):
        """
        移动章节位置
        
        Args:
            from_index (int): 原位置
            to_index (int): 目标位置
        
        Returns:
            bool: 移动成功返回True，否则返回False
        """
        if 0 <= from_index < len(self.sections) and 0 <= to_index < len(self.sections):
            section = self.sections.pop(from_index)
            self.sections.insert(to_index, section)
            return True
        return False
    
    def build_document(self):
        """
        构建完整的文档
        
        Returns:
            str: 完整的Markdown文档内容
        """
        doc = ""
        
        # 添加文档标题
        if self.title:
            doc = f"# {self.title}\n\n"
        
        # 添加所有章节
        for section in self.sections:
            doc += section
        
        return doc
    
    def save_document(self, file_path):
        """
        将文档保存到文件
        
        Args:
            file_path (str): 保存路径
        
        Returns:
            bool: 保存成功返回True，否则抛出异常
        """

        import os
        
        # 确保目录存在
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        document = self.build_document()
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(document)
        
        return True
    
    def get_section(self, index):
        """
        获取指定索引的章节内容
        
        Args:
            index (int): 章节索引
        
        Returns:
            str: 章节内容，如果索引无效则返回None
        """
        if 0 <= index < len(self.sections):
            return self.sections[index]
        return None
    
    def get_section_count(self):
        """
        获取章节数量
        
        Returns:
            int: 章节数量
        """
        return len(self.sections)
    
if __name__ == '__main__':

    doc = MarkdownDocumentBuilder()

    doc.add_section('product_overview', '# Product Overview\n\n## Product Description\nTC5 is a KNX S-Mode multi-functional touch panel for display, operation and control. The device offers a 5-inch color capacitive touch screen at a resolution of 480 × 854. The device is powered over KNX on DC 24...30 V auxiliary supply voltage.\n\n### Key Features\n- KNX controller with extensive range of functions – integrated temperature sensor\n- Password protection\n- Proximity sensor\n- Customization of wall papers, screen savers and icons\n- LED colored light strip Control functions\n  - Lighting control\n  - Solar protection\n  - HVAC\n  - Scene control\n  - Schedule and timer function\n  - Alarm handling\n\nThe original manufacturer is GVS. All software and hardware is provided by GVS, no development is done by Siemens.\n\n## Sales and Delivery Channels\nStandard SI B sales channels.\n\n## Development Details\nThis is an OEM product developed by GVS (https://www.gvssmart.com/).\nIt is based on a customized Linux.')

    doc.save_document('./markdown/first.md')