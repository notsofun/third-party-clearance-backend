from typing import Dict, Any
from back_end.items_utils.item_types import State, ConfirmationStatus
from back_end.services.state_handlers.handler_factory import StateHandlerFactory

from log_config import get_logger

logger = get_logger(__name__)  # 每个模块用自己的名称

class WorkflowContext:
    """工作流上下文，管理状态和转换"""
    def __init__(self, handlers: StateHandlerFactory, current_state=ConfirmationStatus.OEM):
        # 状态转移表
        self.transition_rules = {
            ConfirmationStatus.OEM: {
                State.COMPLETED.value: ConfirmationStatus.CONTRACT,
                State.INPROGRESS.value: ConfirmationStatus.OEM
            },
            ConfirmationStatus.COMPLIANCE: {
                State.COMPLETED.value: [
                    # 第一个条件：如果需要新增OEM再确认节点。暂时没有处理新节点
                    {
                        "condition": lambda ctx: ctx["shared"].get("is_oem_approved", False),
                        "target": ConfirmationStatus.FINALLIST
                    },
                    # 默认条件：原来的转移目标
                    {
                        "condition": lambda ctx: True,
                        "target": ConfirmationStatus.FINALLIST
                    }
                ],
                State.INPROGRESS.value: ConfirmationStatus.COMPLIANCE
            },
            ConfirmationStatus.CREDENTIAL: {
                State.COMPLETED.value: ConfirmationStatus.SPECIAL_CHECK,
                State.INPROGRESS.value: ConfirmationStatus.CREDENTIAL
            },
            ConfirmationStatus.SPECIAL_CHECK: {
                State.COMPLETED.value: ConfirmationStatus.COMPLIANCE,
                State.INPROGRESS.value: ConfirmationStatus.SPECIAL_CHECK
            },
            ConfirmationStatus.CONTRACT: {
                State.COMPLETED.value: ConfirmationStatus.DEPENDENCY,
                State.INPROGRESS.value: ConfirmationStatus.CONTRACT
            },
            ConfirmationStatus.DEPENDENCY: {
                State.COMPLETED.value: ConfirmationStatus.MAINLICENSE,
                State.INPROGRESS.value: ConfirmationStatus.DEPENDENCY
            },
            ConfirmationStatus.MAINLICENSE: {
                State.COMPLETED.value: ConfirmationStatus.CREDENTIAL,
                State.INPROGRESS.value: ConfirmationStatus.MAINLICENSE,
            },
            ConfirmationStatus.FINALLIST: {
                State.COMPLETED.value: ConfirmationStatus.OSSGENERATION,
                State.INPROGRESS.value: ConfirmationStatus.FINALLIST,
            },
            ConfirmationStatus.OSSGENERATION: {
                State.COMPLETED.value: ConfirmationStatus.PRODUCTOVERVIEW,
                State.INPROGRESS.value: ConfirmationStatus.OSSGENERATION,
            },
            ConfirmationStatus.PRODUCTOVERVIEW: {
                State.COMPLETED.value: ConfirmationStatus.COMPONENTOVERVIEW,
                State.INPROGRESS.value: ConfirmationStatus.PRODUCTOVERVIEW,
            },
            ConfirmationStatus.COMPONENTOVERVIEW: {
                State.COMPLETED.value: ConfirmationStatus.COMMONRULES,
                State.INPROGRESS.value: ConfirmationStatus.COMPONENTOVERVIEW
            },
            ConfirmationStatus.COMMONRULES: {
                State.COMPLETED.value: ConfirmationStatus.OBLIGATIONS,
                State.INPROGRESS.value: ConfirmationStatus.COMMONRULES
            },
            ConfirmationStatus.OBLIGATIONS: {
                State.COMPLETED.value: ConfirmationStatus.INTERACTION,
                State.INPROGRESS.value: ConfirmationStatus.OBLIGATIONS,
            },
            ConfirmationStatus.INTERACTION: {
                State.COMPLETED.value: ConfirmationStatus.COPYLEFT,
                State.INPROGRESS.value: ConfirmationStatus.INTERACTION,
            },
            ConfirmationStatus.COPYLEFT: {
                State.COMPLETED.value: ConfirmationStatus.SPECIAL_CONSIDERATION,
                State.INPROGRESS.value: ConfirmationStatus.COPYLEFT,
            },
            ConfirmationStatus.SPECIAL_CONSIDERATION: {
                State.COMPLETED.value: ConfirmationStatus.COMPLETED,
                State.INPROGRESS.value: ConfirmationStatus.SPECIAL_CONSIDERATION,
            },
            ConfirmationStatus.COMPLETED: {
                # 完成状态下一直停留在完成
                State.COMPLETED.value: ConfirmationStatus.COMPLETED,
                State.INPROGRESS.value: ConfirmationStatus.COMPLETED
            },
        }
        
        # 注册状态处理器
        self.handlers = handlers
        self.current_state = current_state
        self.initialized_states = set()  # 记录已初始化的状态
    
    def get_next_state(self, old_state, event, context):
        """
        根据当前状态和事件确定下一个状态
        
        参数:
        old_state - 当前状态
        event - 触发事件
        context - 条件判断所需的上下文信息
        
        返回:
        next_state - 下一个状态
        """
        # 获取转换规则
        transition = self.transition_rules.get(old_state, {}).get(event)

        # 如果没有找到转换规则，返回None或保持原状态
        if transition is None:
            return None  # 或者 return old_state

        # 检查转换规则是否是条件列表
        if isinstance(transition, list):
            # 遍历条件列表，找到第一个满足的条件
            for rule in transition:
                condition_func = rule.get("condition")
                if condition_func and condition_func(context):
                    return rule.get("target")
            # 如果没有满足的条件，返回None或保持原状态
            return None  # 或者 return old_state

        # 如果转换规则是直接的状态值，则直接返回
        return transition

    def process(self, context: Dict[str, Any]) -> Dict:
        """处理当前状态并可能转移到下一个状态"""
        handler = self.handlers.get_handler(self.current_state.value)
        if not handler:
            logger.error(f"We have not found the corresponding state: {self.current_state}")
            return {
                "success": False,
                "error": f"We have not found the corresponding state: {self.current_state}"
            }
            
        # 如果是子任务处理器，确保已初始化
        if handler.has_subtasks() and self.current_state not in self.initialized_states:
            handler.initialize_subtasks(context)
            self.initialized_states.add(self.current_state)
        
        logger.info(f'chat_flow.process: 处理状态: {self.current_state}')
        
        # 执行状态处理并获取事件
        event = handler.handle(context)
        old_state = self.current_state
        
        # 根据事件和转移表更新状态
        if event and old_state in self.transition_rules:
            context['status'] = event
            next_state = self.get_next_state(old_state, event, context)
            if next_state and next_state != old_state:
                logger.info(f'chat_flow.process: 状态转移: {old_state} -> {next_state}')
                self.current_state = next_state
                
                # 如果转移到了新状态，重置其子任务（如果有）
                if next_state in self.initialized_states:
                    self.initialized_states.remove(next_state)
        
        # 返回处理结果
        result = {
            "success": True,
            "previous_state": old_state.value,
            "current_state": self.current_state,
            "state_changed": old_state != self.current_state,
            "event": event
        }
        
        return result

# 使用示例
if __name__ == "__main__":
    workflow = WorkflowContext(curren_state= ConfirmationStatus.MAINLICENSE)
    context = {
        'shared': {
            "dependency_required__components": [
                {
                    "compName": "@ngrx/store 17.2.0",
                    "dependency": True,
                    "status": 'confirmed'
                }
            ],
            "credential_required_components" : [
                    {
                        "compName": "@ngrx/store 17.2.0\n                            ⇧",
                        "blockHtml": "<li class=\"release\" id=\"@ngrx/store_17.2.0\" title=\"@ngrx/store 17.2.0\">\n<div class=\"inset\">\n<h3 id=\"h3@ngrx/store_17.2.0\">@ngrx/store 17.2.0\n                            <a class=\"top\" href=\"#releaseHeader\">⇧</a>\n</h3>\n</div>\n\n\n                        Acknowledgements:<br>\n<pre class=\"acknowledgements\">\nDisclaimer of Warranties and Limitation of Liability.\n\na. Unless otherwise separately undertaken by the Licensor, to the extent possible, the Licensor offers the Licensed Material as-is and as-available, and makes no representations or warranties of any kind concerning the Licensed Material, whether express, implied, statutory, or other. This includes, without limitation, warranties of title, merchantability, fitness for a particular purpose, non-infringement, absence of latent or other defects, accuracy, or the presence or absence of errors, whether or not known or discoverable. Where disclaimers of warranties are not allowed in full or in part, this disclaimer may not apply to You.\n\nb. To the extent possible, in no event will the Licensor be liable to You on any legal theory (including, without limitation, negligence) or otherwise for any direct, special, indirect, incidental, consequential, punitive, exemplary, or other losses, costs, expenses, or damages arising out of this Public License or use of the Licensed Material, even if the Licensor has been advised of the possibility of such losses, costs, expenses, or damages. Where a limitation of liability is not allowed in full or in part, this limitation may not apply to You.\n\nc. The disclaimer of warranties and limitation of liability provided above shall be interpreted in a manner that, to the extent possible, most closely approximates an absolute disclaimer and waiver of all liability.\n    </pre>\n\n                    Licenses:<br>\n<ul class=\"licenseEntries\" style=\"list-style-type:none\">\n<li class=\"licenseEntry\" id=\"licenseEntry1\" title=\"Apache-2.0\">\n<a href=\"#licenseTextItem1\">Apache-2.0 (1)</a>\n</li>\n<li class=\"licenseEntry\" id=\"licenseEntry2\" title=\"CC-BY-4.0\">\n<a href=\"#licenseTextItem2\">CC-BY-4.0 (2)</a>\n</li>\n<li class=\"licenseEntry\" id=\"licenseEntry3\" title=\"MIT\">\n<a href=\"#licenseTextItem3\">MIT (3)</a>\n</li>\n</ul>\n<pre class=\"copyrights\">\nCopyright (c) 2017-2020 Nicholas Jamieson and contributors\nCopyright (c) 2015-2018 NgRx.\nCopyright 2009 International Color Consortium\nCopyright (c) 1998 Hewlett-Packard Company\n© Zeno Rocha\nCopyright (c) 2015-2023 Brandon Roberts, Mike Ryan, Victor Savkin, Rob Wormald\nCopyright 2006-2016 Google Inc. All Rights Reserved.\nCopyright Google Inc. All Rights Reserved.\n(c) 2007 Steven Levithan &lt;stevenlevithan.com&gt;\n<h3><a class=\"top\" href=\"#releaseHeader\">⇧</a></h3>\n    </pre>\n</br></br></li>",
                        "sessionId": 11712279331732835480,
                        "status": 'confirmed'
                    }
                ],
            'specialCollections' : [
                    {
                        "licName": "GPL",
                        "category": "GPL",
                        'status': 'confirmed'
                    }
            ],
            'checkedRisk' : [
                {
                    "title": "Apache-2.0",
                    "originalLevel": "low",
                    "CheckedLevel": "low",
                    "Justification": "The Apache License 2.0 is widely regarded as a permissive license that allows for modification, distribution, and use of the source code without strong copyleft obligations. While it does include a termination clause for patent licenses in the event of litigation, this does not significantly increase the overall risk associated with using the license, as the obligations are still manageable and do not impose severe restrictions. The previous assessment of 'low' risk is appropriate given the nature of this license.",
                    'status': 'confirmed',
                },
                {
                    "title": "CC-BY-4.0",
                    "originalLevel": "low",
                    "CheckedLevel": "medium",
                    "Justification": "While CC-BY-4.0 indeed allows wide usage and sharing with only attribution required, the risk associated with potential legal actions arising from insufficient attribution claims or failure to comply with the licensing terms is higher than indicated as low. Additionally, it is important to consider the nuances of derivative works and the responsibilities tied to attribution. Therefore, a medium risk level is more appropriate.",
                    'status': 'confirmed',
                },
                {
                    "title": "3: MIT⇧",
                    "originalLevel": "low",
                    "CheckedLevel": "low",
                    "Justification": "The MIT License is widely recognized as a permissive license that imposes minimal conditions on users. The requirement to include copyright and permission notices is standard for permissive licenses. Additionally, the lack of copyleft obligations reduces potential legal complications. Given its acceptance and clarity in usage, the risk level remains low.",
                    'status': 'confirmed',
                },
                ]
        },
            'mainLicenseRequiringComponents': [
            {
                "compName": "@ngrx/store 17.2.0\n                            ⇧",
                "compHtml": "<li class=\"release\" id=\"@ngrx/store_17.2.0\" title=\"@ngrx/store 17.2.0\">\n<div class=\"inset\">\n<h3 id=\"h3@ngrx/store_17.2.0\">@ngrx/store 17.2.0\n                            <a class=\"top\" href=\"#releaseHeader\">⇧</a>\n</h3>\n</div>\n\n\n                        Acknowledgements:<br>\n<pre class=\"acknowledgements\">\nDisclaimer of Warranties and Limitation of Liability.\n\na. Unless otherwise separately undertaken by the Licensor, to the extent possible, the Licensor offers the Licensed Material as-is and as-available, and makes no representations or warranties of any kind concerning the Licensed Material, whether express, implied, statutory, or other. This includes, without limitation, warranties of title, merchantability, fitness for a particular purpose, non-infringement, absence of latent or other defects, accuracy, or the presence or absence of errors, whether or not known or discoverable. Where disclaimers of warranties are not allowed in full or in part, this disclaimer may not apply to You.\n\nb. To the extent possible, in no event will the Licensor be liable to You on any legal theory (including, without limitation, negligence) or otherwise for any direct, special, indirect, incidental, consequential, punitive, exemplary, or other losses, costs, expenses, or damages arising out of this Public License or use of the Licensed Material, even if the Licensor has been advised of the possibility of such losses, costs, expenses, or damages. Where a limitation of liability is not allowed in full or in part, this limitation may not apply to You.\n\nc. The disclaimer of warranties and limitation of liability provided above shall be interpreted in a manner that, to the extent possible, most closely approximates an absolute disclaimer and waiver of all liability.\n    </pre>\n\n                    Licenses:<br>\n<ul class=\"licenseEntries\" style=\"list-style-type:none\">\n<li class=\"licenseEntry\" id=\"licenseEntry1\" title=\"Apache-2.0\">\n<a href=\"#licenseTextItem1\">Apache-2.0 (1)</a>\n</li>\n<li class=\"licenseEntry\" id=\"licenseEntry2\" title=\"CC-BY-4.0\">\n<a href=\"#licenseTextItem2\">CC-BY-4.0 (2)</a>\n</li>\n<li class=\"licenseEntry\" id=\"licenseEntry3\" title=\"MIT\">\n<a href=\"#licenseTextItem3\">MIT (3)</a>\n</li>\n</ul>\n<pre class=\"copyrights\">\nCopyright (c) 2017-2020 Nicholas Jamieson and contributors\nCopyright (c) 2015-2018 NgRx.\nCopyright 2009 International Color Consortium\nCopyright (c) 1998 Hewlett-Packard Company\n© Zeno Rocha\nCopyright (c) 2015-2023 Brandon Roberts, Mike Ryan, Victor Savkin, Rob Wormald\nCopyright 2006-2016 Google Inc. All Rights Reserved.\nCopyright Google Inc. All Rights Reserved.\n(c) 2007 Steven Levithan &lt;stevenlevithan.com&gt;\n<h3><a class=\"top\" href=\"#releaseHeader\">⇧</a></h3>\n    </pre>\n</br></br></li>",
                    "licenseList": [
                    "Apache-2.0",
                    "CC-BY-4.0",
                    "MIT"
                    ],
                    'status': 'confirmed'
            }
            ],
        'status': 'next'
    }
    
    state = workflow.current_state
    i = 0
    while state:
        print(f"当前状态: {state.value}")
        state = workflow.process(context)
        if state:
            print(f"this it the {i} 次")
            print(f"转移到状态: {state.value}")
        else:
            print(f"this it the {i} 次")
            print("流程结束")

        i += 1

        if i > 5:
            break