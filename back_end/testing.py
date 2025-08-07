from abc import ABC, abstractmethod

class StateHandler(ABC):

    def __init__(self):
        super().__init__()

        self.CONTINUE = 'continue'
        self.NEXT = 'next'

    def check(self, status):
        if status == self.CONTINUE:
            print('ok')
        elif status == self.NEXT:
            print('not ok')

s = StateHandler()

resi = s.check('continue')
print(resi)

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