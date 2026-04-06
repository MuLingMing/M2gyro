# coding=utf-8
# 通用函数


def merge_params(custom_params: dict, attach_params: dict) -> dict:
    """
    通用参数合并方法，将 attach 中的参数与 custom_params 合并
    attach 中的参数会覆盖 custom_params 中的对应值

    参数:
    custom_params: 自定义参数字典
    attach_params: attach 中参数字典

    返回值:
    - dict: 合并后的参数字典
    """
    # 确保 custom_params 是字典
    if not isinstance(custom_params, dict):
        custom_params = {}

    # 确保 attach_params 是字典
    if not isinstance(attach_params, dict):
        attach_params = {}

    # 合并参数，attach_params 中的值会覆盖 custom_params 中的对应值
    if not attach_params:
        return custom_params
    merged_params = custom_params.copy()

    for key, value in attach_params.items():
        merged_params[key] = value

    return merged_params
