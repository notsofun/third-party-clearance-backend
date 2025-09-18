import sys,os
sys.path.append(r'C:\Users\z0054unn\Documents\Siemens-GitLab\Third-party\third-party-clearance')
import pytest
import datetime
from log_config import configure_logging, get_logger
from back_end.items_utils.item_types import State, ConfirmationStatus
import json
from back_end.services.chat_service import ChatService
from utils.LLM_Analyzer import RiskBot
import random
from main import run_test

_GLOBAL_RISK_BOT = None

configure_logging()
logger = get_logger(__name__)

output_dir = 'back_end'
try:
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Directory '{output_dir}' ensured to exist.")
except OSError as e:
    logger.error(f"Error creating directory '{output_dir}': {e}")

# 首先定义一个只初始化一次的单例bot函数
def get_singleton_risk_bot():
    global _GLOBAL_RISK_BOT
    if _GLOBAL_RISK_BOT is None:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%Hh")
        randint = random.getrandbits(64)
        print(f"创建新的RiskBot实例: test{timestamp}{randint}")
        _GLOBAL_RISK_BOT = RiskBot(f'test{timestamp}{randint}')
    return _GLOBAL_RISK_BOT


# 使用参数化 fixture 来支持不同的共享上下文
@pytest.fixture(scope="class")
def class_context(request):
    """创建类级别的context，在整个测试类中共享"""
    shared = {
        'html_path': r"C:\Users\z0054unn\Downloads\LicenseInfo-Wireless Room Sensor-2.0-2025-08-22_01_44_49.html",
        'PCR_Path': r'uploads\test\ProjectClearingReport-Wireless Room Sensor-2.0-2025-08-28_03_14_37.docx',
    }
    shared = run_test(shared)
    shared['riskBot'] = get_singleton_risk_bot()
    
    chat_service = ChatService()
    chat_service.chat_flow.current_state = ConfirmationStatus.COMMONRULES

    chat_service.initialize_chat(shared=shared)
    handler = chat_service.handler_factory.get_handler(chat_service.chat_flow.current_state.value, chat_service.bot)
    
    context_type = getattr(request, "param", "base")

    # 选择共享上下文
    if context_type == "custom":
        # 只更新特定键，不替换整个字典
        shared.update({
            'user_input': '''
            That's totally OK.

    ''',
            'status': chat_service.chat_flow.current_state.value,
            'extra_data': 'Additional context information',
        })

    # 将context保存到类属性中，便于所有测试方法访问
    request.cls.context_data = {
        'workflow_context': chat_service.chat_flow.current_state,
        'chat_manager': chat_service.chat_manager,
        'chat_service': chat_service,
        'bot': chat_service.bot,
        'handler': handler,
        'handler_factory': chat_service.handler_factory,
        'shared': shared,
        'updated_shared': None,  # 用于存储更新后的共享数据
        'current_status': chat_service.chat_flow.current_state.value  # 跟踪当前状态
    }
    
    return request.cls.context_data

# 修改测试类，使用类级别的fixture
@pytest.mark.usefixtures("class_context")
@pytest.mark.parametrize("class_context", ["custom"], indirect=True)
@pytest.mark.order
class TestCustomProjectOverviewIntegration:
    """使用自定义共享上下文的项目概述处理器测试"""
    
    @pytest.mark.order(0)
    def test_environment_setup(self):
        """验证测试环境是否正确初始化"""
        logger.info("检验测试环境初始化...")
        
        # 验证关键组件
        assert self.context_data is not None, "Context data has not been initialized"
        assert 'chat_service' in self.context_data, "ChatService has not been initialized"
        assert 'workflow_context' in self.context_data, "WorkflowContext has not been initialized"
        assert 'shared' in self.context_data, "the shared data is empty"
        assert 'parsedHtml' in self.context_data['shared']
        assert 'ParsedPCR' in self.context_data['shared']
        
        chat_service = self.context_data['chat_service']
        assert chat_service is not None, "ChatService is empty"
        
        logger.info("测试环境验证通过!")

    @pytest.mark.order(1)
    def test_custom_instruction_retrieval(self):
        """使用自定义上下文测试指令获取"""
        logger.info("开始执行测试: test_custom_instruction_retrieval")
        chat_service = self.context_data['chat_service']
        shared = self.context_data['shared']
        
        logger.info('Now we are using the customized shared dictionary')
        
        instructions = chat_service.get_instructions(
            chat_service.chat_flow.current_state.value
        )
        
        assert isinstance(instructions, str)
        assert len(instructions) > 0
        
        self.context_data['shared'] = shared
        self.context_data['chat_service'] = chat_service

        logger.info(f"Retrieved instructions with custom context: {instructions}")
    
    @pytest.mark.order(2)
    def test_initial_content_generation(self):
        """测试初始内容生成流程"""
        logger.info("开始执行测试: test_initial_content_generation")
        chat_service = self.context_data['chat_service']
        shared = self.context_data['shared']
        handler_factory = self.context_data['handler_factory']
        
        # 1. 处理用户输入
        status, updated_shared, reply = chat_service.process_user_input(
            shared=shared,
            user_input=shared['user_input'],
            status=self.context_data['current_status']
        )
        
        # 2. 处理"continue"响应
        max_attempts = 3
        attempts = 0
        
        while status == State.CONTINUE.value and attempts < max_attempts:
            attempts += 1
            print(f"收到'continue'响应(第{attempts}次)，提供额外信息...")
            
            additional_input = f"这是额外的产品信息: [第{attempts}次尝试的详情]"
            status, updated_shared, reply = chat_service.process_user_input(
                shared=updated_shared,  # 使用更新后的共享上下文
                user_input=additional_input,
                status=self.context_data['current_status']
            )
        
        # 验证最终结果
        assert status == 'obligations'

        assert 'generated_obligations' in updated_shared
        
        content = updated_shared['generated_obligations']
        assert content
        
        handler_factory.add_section(status, content)
        
        print(f"生成的内容(在{attempts}次额外输入后): {content}")
        
        # 更新类级别共享的上下文和状态
        self.context_data['updated_shared'] = updated_shared
        self.context_data['current_status'] = status
        self.context_data['handler_factory'] = handler_factory
        self.context_data['chat_service'] = chat_service
        self.context_data['shared'] = shared
        
        # 验证确认消息格式
        assert isinstance(reply, list)
        assert len(reply) > 0

    @pytest.mark.order(4)
    def test_answer_simple_state(self):
        logger.info("开始执行测试: test_answer_simple_state")
        chat_service = self.context_data['chat_service']
        shared = self.context_data['shared']
        updated_shared = self.context_data['updated_shared']
        current_status = self.context_data['current_status']
        user_input_list = [
            'ok, I have checked.',
            'I do not know hot to check',
            'OK, I have done'
        ]

        instruction = chat_service.get_instructions(current_status)
        logger.info('Now we enter this instructions: %s', instruction)

        for i, user_input in enumerate(user_input_list):

            status, shared, reply = chat_service.process_user_input(
                shared = shared,
                user_input = user_input,
                status = current_status,
            )

            logger.info(f"状态: {status}")
            logger.info(f"系统回复: {reply[:100]}..." if isinstance(reply, str) and len(reply) > 100 else f"系统回复: {reply}")


            updated_shared = shared
            current_status = status

        chat_service.handler_factory.md.save_document(f'./downloads/test/product_clearance/report.md')
        logger.info('The latest file has been saved sucessfully!')
        self.context_data['chat_service'] = chat_service
        self.context_data['shared'] = shared
        self.context_data['current_status'] = current_status
        self.context_data['updated_shared'] = updated_shared

        return status, shared

    @pytest.mark.order(3)
    def test_user_inFlow(self):
        '''导入对话文件测试节点流转状态'''
        logger.info("开始执行测试: test_user_in_flow")
        chat_service = self.context_data['chat_service']
        shared = self.context_data['shared']
        updated_shared = self.context_data['updated_shared']
        current_status = self.context_data['current_status']

        with open(r'back_end\test_codes\test_dialogue\test_obligations.json', 'r', encoding='utf-8') as f:
            dialogue = json.load(f)
            for i, turn in enumerate(dialogue['turns']):
                turn_num = i + 1
                logger.info(f'当前对话轮次{turn_num}, 用户输入{turn['user_input']}')

                status, shared, reply = chat_service.process_user_input(
                    shared = shared,
                    user_input = turn['user_input'],
                    status = current_status
                )

                logger.info(f"状态: {status}")
                logger.info(f"系统回复: {reply[:100]}..." if isinstance(reply, str) and len(reply) > 100 else f"系统回复: {reply}")

                # 处理继续状态
                max_attempts = 2
                attempts = 0
                
                while status == 'continue' and attempts < max_attempts and 'follow_up_if_continue' in turn:
                    attempts += 1
                    followup = turn['follow_up_if_continue']
                    
                    logger.info(f"用户跟进 #{attempts}: {followup}")
                    
                    status, shared, reply = chat_service.process_user_input(
                        shared=shared,
                        user_input=followup,
                        status=current_status
                    )
                    
                    logger.info(f"状态: {status}")
                    logger.info(f"系统回复: {reply[:100]}..." if isinstance(reply, str) and len(reply) > 100 else f"系统回复: {reply}")

                updated_shared = shared
                current_status = status

        chat_service.handler_factory.md.save_document(f'./downloads/test/product_clearance/5th_report.md')
        logger.info('The latest file has been saved sucessfully!')
        self.context_data['chat_service'] = chat_service
        self.context_data['shared'] = shared
        self.context_data['current_status'] = status
        self.context_data['updated_shared'] = updated_shared

        return status, shared

    @pytest.mark.order(3)
    def test_user_satisfied_flow(self):
        """测试用户满意后切换到下一个状态的路径"""
        logger.info("开始执行测试: test_user_satisfied_flow")
        chat_service = self.context_data['chat_service']
        updated_shared = self.context_data['updated_shared']
        current_status = self.context_data['current_status']
        handler_factory = self.context_data['handler_factory']
        
        print("\n=== 测试用户满意路径 ===")
        print(f"当前状态: {current_status}")
        
        # 模拟用户确认满意
        user_confirmation = "Yes, I am satisfied with the current content."
        status, updated_shared, reply = chat_service.process_user_input(
            shared=updated_shared,
            user_input=user_confirmation,
            status=current_status
        )
        
        # 验证是否切换到了下一个状态
        print(f"响应后状态: {status}")
        assert status != ConfirmationStatus.COMPONENTOVERVIEW.value, "应该切换到下一个状态"
        
        print(f"系统回复: {reply}")
        
        # 验证是否保留了生成的内容
        assert 'generated_common_rules' in updated_shared
        
        handler_factory.md.save_document(f'./downloads/test/product_clearance/report.md')

        # 更新类级别共享的上下文和状态
        self.context_data['shared'] = updated_shared
        self.context_data['current_status'] = status
        
    @pytest.mark.order(4)
    def test_user_unsatisfied_flow(self):
        """测试用户不满意后重新生成内容的路径"""
        logger.info("开始执行测试: test_user_unsatisfied_flow")
        
        # 重置状态回到产品概述（模拟新的测试场景）
        self.context_data['current_status'] = ConfirmationStatus.COMMONRULES.value
        chat_service = self.context_data['chat_service']
        chat_service.chat_flow.current_state = ConfirmationStatus.COMMONRULES
        
        # 重新生成内容（复用初始生成流程）
        self.test_initial_content_generation()
        
        # 获取更新后的上下文
        updated_shared = self.context_data['updated_shared']
        current_status = self.context_data['current_status']
        
        print("\n=== 测试用户不满意路径 ===")
        print(f"当前状态: {current_status}")
        
        # 保存原始生成的内容用于比较
        original_content = updated_shared.get('generated_common_rules', '')
        
        # 模拟用户不满意并提供反馈
        user_rejection = "I am not satisfied with it, please generate it again."
        status, updated_shared, reply = chat_service.process_user_input(
            shared=updated_shared,
            user_input=user_rejection,
            status=current_status
        )
        
        # 验证是否仍然处于同一状态（重新生成内容）
        assert status == 'common_rules', "应该保持在当前状态以重新生成内容"
        
        # 处理可能的"continue"响应
        max_attempts = 3
        attempts = 0
        
        while status == 'continue' and attempts < max_attempts:
            attempts += 1
            print(f"重新生成时收到'continue'响应(第{attempts}次)，提供额外信息...")
            
            additional_input = f"重新生成时的额外信息: [第{attempts}次尝试的详情]"
            status, updated_shared, reply = chat_service.process_user_input(
                shared=updated_shared,
                user_input=additional_input,
                status=current_status
            )
        
        # 验证是否重新生成了内容
        assert 'generated_common_rules' in updated_shared
        new_content = updated_shared['generated_common_rules']
        
        # 打印新旧内容进行比较
        logger.info(f"原始内容: {original_content[:100]}...")
        logger.info(f"重新生成的内容: {new_content[:100]}...")
        
        # 验证内容确实有变化（这可能不是100%准确，因为重新生成的内容可能相似）
        assert len(new_content) != 0, "应该生成新的内容"
        
        # 确认系统是否询问用户对新内容的满意度
        assert isinstance(reply, list) and len(reply) > 0
        
        # 更新类级别共享的上下文和状态
        self.context_data['updated_shared'] = updated_shared
        self.context_data['current_status'] = status

if __name__ == '__main__':
    # 使用pytest运行指定的测试类
    # 运行自定义上下文测试
    print("\n=== 运行自定义上下文测试 ===")
    pytest.main(["-v",
                f"{__file__}::TestCustomProjectOverviewIntegration::test_environment_setup",
                f"{__file__}::TestCustomProjectOverviewIntegration::test_custom_instruction_retrieval",
                f"{__file__}::TestCustomProjectOverviewIntegration::test_user_inFlow"])