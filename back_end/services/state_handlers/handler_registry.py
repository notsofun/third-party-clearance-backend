
class HandlerRegistry:
    _instance = None
    _handlers = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HandlerRegistry, cls).__new__(cls)
        return cls._instance
    
    def get_handler(self, handler_class):
        """获取指定类型的handler实例，如果不存在则创建"""
        class_name = handler_class.__name__
        if class_name not in self._handlers:
            self._handlers[class_name] = handler_class()
        return self._handlers[class_name]
    
class HandlerStateWrapper:
    '''
    包装StateHandler类，特别是针对Content Generation Handler类，
    用于在保持多项目使用相同子标题处理器的同时维护不同content_generated和content_confirmed属性
    相当于只需要创建一次subcontent的实例，这些就另外再加一个两个属性，不随着这个subcontent走
    '''

    def __init__(self, handler):
        self.handler = handler
        if hasattr(handler, 'logger') and handler.logger is not None:
            self.logger = handler.logger
        self.content_confirmed: bool = False
        self.content_generated: bool = False
        self.instructed: bool = False

    def handle(self, context):
        """代理处理方法，根据处理结果更新状态"""
        # 根据处理器类型调用不同的处理方法
        go, self = self.handler.handle(context, self)
        return go, self

    def set_instructed(self) -> None:
        if not self.instructed:
            self.instructed = True

    def __getattr__(self, name):
        """将未定义的属性和方法转发给内部handler"""
        # 添加安全检查，防止无限递归
        if self.handler is None:
            raise AttributeError(f"{self.__class__.__name__} 的 handler 属性为 None，无法访问 {name}")
        
        # 如果handler对象本身是HandlerStateWrapper，可能会导致递归
        if isinstance(self.handler, type(self)):
            raise AttributeError(f"检测到潜在递归: {self.__class__.__name__} 的 handler 也是 HandlerStateWrapper")
            
        try:
            return getattr(self.handler, name)
        except (AttributeError, RecursionError) as e:
            # 捕获可能的递归错误或属性错误
            self.logger.error(f"访问 handler.{name} 时出错: {e}")
            raise AttributeError(f"{self.handler.__class__.__name__} 没有属性 {name}")