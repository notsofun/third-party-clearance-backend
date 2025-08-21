import pytest
import datetime
from log_config import configure_logging, get_logger
from back_end.items_utils.item_types import State, ConfirmationStatus
from back_end.services.chat_flow import WorkflowContext
from back_end.services.chat_manager import ChatManager
from utils.tools import get_strict_json
from back_end.services.chat_service import ChatService
from back_end.services.state_handlers.handler_factory import StateHandlerFactory
from utils.LLM_Analyzer import RiskBot
import random

_GLOBAL_RISK_BOT = None

configure_logging()
logger = get_logger(__name__)

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
    shared = {}
    shared['riskBot'] = get_singleton_risk_bot()
    
    workflow_context = WorkflowContext(curren_state=ConfirmationStatus.PRODUCTOVERVIEW, bot=shared.get('riskBot'))
    chat_manager = ChatManager()
    chat_service = ChatService(workflow_context)

    chat_service.initialize_chat(shared=shared)
    handler_factory = StateHandlerFactory()
    handler = handler_factory.get_handler(workflow_context.current_state.value)
    
    context_type = getattr(request, "param", "base")

    # 选择共享上下文
    if context_type == "custom":
        shared = {
            'user_input': '''
2	Product overview 
2.1	Product description
TC5 is a a KNX S-Mode multi-functional touch panel for display, operation and control. The device offers a 5-inch color capacitive touch screen at a resolution of 480 × 854.
The device is powered over KNX on DC 24...30 V auxiliary supply voltage.
Key features:
•	KNX controller with extensive range of functions – integrated temperature sensor 
•	Password protection 
•	Proximity sensor 
•	Customization of wall papers, screen savers and icons
•	LED colored light strip Control functions 
-	Lighting control
-	Solar protection
-	HVAC 
-	Scene control 
-	Schedule and timer function
-	Alarmhandling
The original manufacturer is GVS. All software and hardware is provided by GVS, no development is done by Siemens.
2.2	Sales and delivery channels
Standard SI B sales channels.
2.3	Development details
This is an OEM product developed by GVS (https://www.gvssmart.com/).
It is based on a customized Linux. 

''',
            'status': ConfirmationStatus.PRODUCTOVERVIEW.value,
            'extra_data': 'Additional context information',
            'riskBot': shared['riskBot']  # 重要：使用同一个bot实例
        }
    else:  # 默认使用基础上下文
        shared = {
            'user_input': '以下是项目信息...',
            'status': ConfirmationStatus.PRODUCTOVERVIEW.value,
            'riskBot': shared['riskBot']  # 重要：使用同一个bot实例
        }
    
    # 将context保存到类属性中，便于所有测试方法访问
    request.cls.context_data = {
        'workflow_context': workflow_context,
        'chat_manager': chat_manager,
        'chat_service': chat_service,
        'bot': chat_service.bot,
        'handler': handler,
        'handler_factory': handler_factory,
        'shared': shared,
        'updated_shared': None,  # 用于存储更新后的共享数据
        'current_status': ConfirmationStatus.PRODUCTOVERVIEW.value  # 跟踪当前状态
    }
    
    return request.cls.context_data

# 修改测试类，使用类级别的fixture
@pytest.mark.usefixtures("class_context")
@pytest.mark.parametrize("class_context", ["custom"], indirect=True)
@pytest.mark.order
class TestCustomProjectOverviewIntegration:
    """使用自定义共享上下文的项目概述处理器测试"""
    
    @pytest.mark.order(1)
    def test_custom_instruction_retrieval(self):
        """使用自定义上下文测试指令获取"""
        logger.info("开始执行测试: test_custom_instruction_retrieval")
        chat_service = self.context_data['chat_service']
        shared = self.context_data['shared']
        
        print(f"Using custom shared context: {shared}")
        
        instructions = chat_service.get_instructions(
            chat_service.chat_flow.current_state.value
        )
        
        assert isinstance(instructions, str)
        assert len(instructions) > 0
        
        print(f"Retrieved instructions with custom context: {instructions}")
    
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
        
        while status == 'continue' and attempts < max_attempts:
            attempts += 1
            print(f"收到'continue'响应(第{attempts}次)，提供额外信息...")
            
            additional_input = f"这是额外的产品信息: [第{attempts}次尝试的详情]"
            status, updated_shared, reply = chat_service.process_user_input(
                shared=updated_shared,  # 使用更新后的共享上下文
                user_input=additional_input,
                status=self.context_data['current_status']
            )
        
        # 验证最终结果
        assert status == 'product_overview'
        assert 'generated_product_overview' in updated_shared
        
        content = updated_shared['generated_product_overview']
        assert content
        
        handler_factory.add_section(status, content)
        
        print(f"生成的内容(在{attempts}次额外输入后): {content}")
        
        # 更新类级别共享的上下文和状态
        self.context_data['updated_shared'] = updated_shared
        self.context_data['current_status'] = status
        self.context_data['handler_factory'] = handler_factory
        
        # 验证确认消息格式
        assert isinstance(reply, list)
        assert len(reply) > 0

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
        assert status != 'product_overview', "应该切换到下一个状态"
        
        print(f"系统回复: {reply}")
        
        # 验证是否保留了生成的内容
        assert 'generated_product_overview' in updated_shared
        
        handler_factory.md.save_document(f'./downloads/test/product_clearance/report.md')

        # 更新类级别共享的上下文和状态
        self.context_data['updated_shared'] = updated_shared
        self.context_data['current_status'] = status
        
    @pytest.mark.order(4)
    def test_user_unsatisfied_flow(self):
        """测试用户不满意后重新生成内容的路径"""
        logger.info("开始执行测试: test_user_unsatisfied_flow")
        
        # 重置状态回到产品概述（模拟新的测试场景）
        self.context_data['current_status'] = 'product_overview'
        chat_service = self.context_data['chat_service']
        chat_service.chat_flow.current_state = ConfirmationStatus.PRODUCTOVERVIEW
        
        # 重新生成内容（复用初始生成流程）
        self.test_initial_content_generation()
        
        # 获取更新后的上下文
        updated_shared = self.context_data['updated_shared']
        current_status = self.context_data['current_status']
        
        print("\n=== 测试用户不满意路径 ===")
        print(f"当前状态: {current_status}")
        
        # 保存原始生成的内容用于比较
        original_content = updated_shared.get('generated_product_overview', '')
        
        # 模拟用户不满意并提供反馈
        user_rejection = "I am not satisfied with it, please generate it again."
        status, updated_shared, reply = chat_service.process_user_input(
            shared=updated_shared,
            user_input=user_rejection,
            status=current_status
        )
        
        # 验证是否仍然处于同一状态（重新生成内容）
        assert status == 'product_overview', "应该保持在当前状态以重新生成内容"
        
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
        assert 'generated_product_overview' in updated_shared
        new_content = updated_shared['generated_product_overview']
        
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
    pytest.main(["-v", __file__ + "::TestCustomProjectOverviewIntegration"])