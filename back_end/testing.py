from utils.tools import format_oss_text_to_html

with open('src\doc\intro.txt', 'r', encoding='utf-8') as f1:
    intro = f1.read()
    print(intro)
    html = format_oss_text_to_html(intro)
    print(html)

        # if not updated_shared.get('all_confirmed', False):

        #     processing_type = updated_shared.get('processing_type', 'license')
        #     item_type = ItemType.LICENSE if processing_type == 'license' else ItemType.COMPONENT

        #     item_info = self.chat_manager.get_item(updated_shared,item_type)
        #     if item_info.valid:
        #         _, _, current_item = item_info.data

        #         instruction_data, item_name = self._get_item_instuction(item_type, current_item)
                
        #         # 组合完整的初始化消息
        #         status = self.chat_flow.current_state.value
        #         general_instruction = self.get_instructions(updated_shared, status)
        #         specific_instruction = instruction_data.get('talking', f"please check {item_name}")
                
        #         message = f"{general_instruction}\n\n startting checking: {item_name}\n{specific_instruction}"
        #     else:
        #         # 如果没有有效的项目信息，提供通用消息
        #         message = "Checking started, but no valid item found. Please check with the administrator"
        # else:
        #     message = "All items have been checked"