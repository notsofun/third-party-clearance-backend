import warnings
import functools

def deprecated(reason=None):
    """
    这是一个用于标记函数或方法为废弃的装饰器。

    当废弃的函数/方法被调用时，会发出 DeprecationWarning。

    用法示例：
    @deprecated(reason="请使用新的 calculate_total_v2() 方法代替。")
    def calculate_total(a, b):
        pass

    @deprecated() # 没有提供原因，使用默认消息
    def old_function():
        pass
    """
    if reason is None:
        reason_msg = "此功能已被废弃。"
    else:
        reason_msg = f"此功能已被废弃。原因: {reason}"

    def decorator(func):
        @functools.wraps(func) # 保留原始函数的元数据（如名称、文档字符串）
        def wrapper(*args, **kwargs):
            warnings.warn(
                f"调用废弃的方法 '{func.__name__}'. {reason_msg}",
                category=DeprecationWarning,
                stacklevel=2 # 确保警告指向调用废弃方法的代码行，而不是装饰器内部
            )
            return func(*args, **kwargs)
        return wrapper
    return decorator