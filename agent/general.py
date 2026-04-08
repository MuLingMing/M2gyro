# coding=utf-8
# 通用函数


class ParamMerger:
    """
    参数合并器类
    用于合并 custom_params 和 attach_params，支持递归合并字典和数组
    """

    # 可配置的标识字段列表，用于匹配对象和字符串
    # 可以在此添加其他字段如 "node", "node_name" 等
    IDENTIFIER_FIELDS = ["name", "node", "node_name"]

    def __init__(self, identifier_fields: list[str] | None = None, schema: dict | None = None):
        """
        初始化合并器

        参数:
        - identifier_fields: 自定义标识字段列表，覆盖默认值
        - schema: 参数类型定义字典，用于类型检查和转换
        """
        if identifier_fields is not None:
            self.IDENTIFIER_FIELDS = identifier_fields
        self.schema = schema or {}

    def merge_params(self, merge_type: str, custom_params: dict, attach_params: dict, schema: dict | None = None) -> dict:
        """
        通用参数合并方法，将 attach 中的参数与 custom_params 合并
        attach 中的参数会覆盖 custom_params 中的对应值
        如果 attach 中没有对应参数，会使用 custom_params 中的默认值
        递归合并子参数字典和数组

        参数:
        - merge_type: custom类型，分为reco和action
        - custom_params: 自定义参数字典
        - attach_params: attach 中参数字典
        - schema: 参数类型定义字典（优先级高于实例化时的schema）

        返回值:
        - dict: 合并后的参数字典

        示例:
        - "custom_recognition_param": {
            "Interrupt": "A",
            "Continue": [
                "释放技能Q",
                "释放技能W",
                {
                    "name": "释放状态E",
                    "interval": 3,
                    "run": false
                }
            ],
            "logger": false
        }
        - attach_params = {
            "reco": {
                "Interrupt": {
                    "name": "B"
                },
                "Continue": [
                    {
                        "name": "释放技能W",
                        "interval": 5
                    },
                    "释放状态E",
                    "释放状态R"
                ],
                "Over": "C",
                "logger": true
            }
        }
        - merge_params("reco", custom_params, attach_params) -> {
            "Interrupt": [
                "A",
                {
                    "name": "B"
                }
            ],
            "Continue": [
                "释放技能Q",
                {
                    "name": "释放技能W",
                    "interval": 5,
                    "run": false
                },
                "释放状态E",
                "释放状态R"
            ],
            "Over": "C",
            "logger": true
        }
        """
        current_schema = schema if schema is not None else self.schema

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

        # 确定要遍历的 attach 参数
        if merge_type in ("reco", "recognition"):
            attach_reco = attach_params.get("reco") or attach_params.get("recognition")
            if attach_reco:
                attach_params = attach_reco
        elif merge_type in ("act", "action"):
            attach_act = attach_params.get("act") or attach_params.get("action")
            if attach_act:
                attach_params = attach_act

        # 递归合并
        for key, value in attach_params.items():
            field_schema = current_schema.get(key) if isinstance(current_schema, dict) else None
            merged_params[key] = self._merge_value(
                key,
                merged_params.get(key),
                value,
                field_schema,
                merge_type
            )

        return merged_params

    def _merge_value(self, key: str, custom_value, attach_value, field_schema, merge_type: str):
        """
        合并单个值，根据 schema 进行类型检查和转换

        参数:
        - key: 参数名称
        - custom_value: custom 中的值
        - attach_value: attach 中的值
        - field_schema: 当前字段的类型定义
        - merge_type: custom类型（reco/action）
        """
        # 如果 custom_value 不存在，直接用 attach_value
        if custom_value is None:
            return self._apply_type_conversion(key, attach_value, field_schema)

        # 解析 schema
        schema_info = self._parse_schema(field_schema)
        expected_type = schema_info.get("type")

        # 如果有 schema 定义的预期类型
        if expected_type is not None:
            return self._merge_with_type_check(key, custom_value, attach_value, schema_info, merge_type)

        # 没有 schema 定义，按实际类型处理
        return self._merge_by_actual_type(key, custom_value, attach_value, merge_type)

    def _parse_schema(self, field_schema) -> dict:
        """
        解析 schema，支持简单类型和复杂类型

        返回:
        - dict: {"type": expected_type, "items": item_schema, "dict_schema": dict_schema, ...}
        """
        result = {"type": None, "items": None, "dict_schema": None}  # type: ignore

        if field_schema is None:
            return result

        # 简单类型：直接是类型对象
        if isinstance(field_schema, (type, tuple)):
            result["type"] = field_schema  # type: ignore
            
            # 特殊处理：(str, node_schema, list) 这种格式
            if isinstance(field_schema, tuple):
                # 提取 dict schema（如果有）
                dict_schemas = [t for t in field_schema if isinstance(t, dict)]
                if dict_schemas:
                    result["dict_schema"] = dict_schemas[0]  # type: ignore
                    # 列表项的 schema 是 (str, dict_schema)
                    result["items"] = (str, dict_schemas[0])  # type: ignore
            
            return result

        # 复杂类型：字典格式
        if isinstance(field_schema, dict):
            result["type"] = field_schema.get("type")  # type: ignore
            result["items"] = field_schema.get("items")  # type: ignore
            result["dict_schema"] = field_schema.get("dict_schema")  # type: ignore
            # 其他字段留作扩展
            for k, v in field_schema.items():
                if k not in ("type", "items", "dict_schema"):
                    result[k] = v  # type: ignore
            return result

        return result

    def _apply_type_conversion(self, key: str, value, field_schema):
        """
        根据 schema 进行类型转换

        参数:
        - key: 参数名称
        - value: 值
        - field_schema: 类型定义
        """
        if field_schema is None:
            return value

        schema_info = self._parse_schema(field_schema)
        expected_type = schema_info.get("type")
        item_schema = schema_info.get("items")

        if expected_type is None:
            return value

        try:
            # 检查是否是多种类型之一
            if isinstance(expected_type, tuple):
                dict_schema = schema_info.get("dict_schema")
                list_item_schema = schema_info.get("items")
                
                for t in expected_type:
                    # 检查 t 是否是类型，或者是 dict schema
                    type_to_check = t
                    if isinstance(t, dict):
                        type_to_check = dict
                    
                    if isinstance(value, type_to_check):
                        # 类型匹配，检查是否需要进一步验证
                        if type_to_check == dict and dict_schema:
                            return self._validate_dict(value, dict_schema, key)
                        elif type_to_check == list and list_item_schema:
                            return self._validate_list(value, list_item_schema, key)
                        return value
                # 都不匹配，尝试转换为第一个类型
                first_type = expected_type[0]
                if isinstance(first_type, dict):
                    first_type = dict
                return self._convert_to_type(value, first_type, key)

            # 单个类型
            if expected_type == str:
                if not isinstance(value, str):
                    import logging
                    logging.warning(f"参数 '{key}' 类型不匹配，期望 str，实际为 {type(value).__name__}，已自动转换")
                    return str(value)
                return value
            elif expected_type == int:
                if not isinstance(value, int):
                    import logging
                    logging.warning(f"参数 '{key}' 类型不匹配，期望 int，实际为 {type(value).__name__}，已自动转换")
                    return int(value)
                return value
            elif expected_type == float:
                if not isinstance(value, float):
                    import logging
                    logging.warning(f"参数 '{key}' 类型不匹配，期望 float，实际为 {type(value).__name__}，已自动转换")
                    return float(value)
                return value
            elif expected_type == bool:
                if not isinstance(value, bool):
                    import logging
                    logging.warning(f"参数 '{key}' 类型不匹配，期望 bool，实际为 {type(value).__name__}，已自动转换")
                    return bool(value)
                return value
            elif expected_type == list:
                if not isinstance(value, list):
                    value = [value]
                if item_schema:
                    return self._validate_list(value, item_schema, key)
                return value
            elif expected_type == dict:
                if not isinstance(value, dict):
                    import logging
                    logging.warning(f"参数 '{key}' 类型不匹配，期望 dict，实际为 {type(value).__name__}")
                    return {}
                if item_schema:
                    return self._validate_dict(value, item_schema, key)
                return value
            else:
                return value
        except Exception as e:
            import logging
            logging.warning(f"参数 '{key}' 类型转换失败: {e}，使用原值")
            return value

    def _convert_to_type(self, value, target_type, key: str):
        """尝试将值转换为目标类型"""
        import logging
        try:
            if target_type == str:
                logging.warning(f"参数 '{key}' 类型不匹配，期望 str，实际为 {type(value).__name__}，已自动转换")
                return str(value)
            elif target_type == int:
                logging.warning(f"参数 '{key}' 类型不匹配，期望 int，实际为 {type(value).__name__}，已自动转换")
                return int(value)
            elif target_type == float:
                logging.warning(f"参数 '{key}' 类型不匹配，期望 float，实际为 {type(value).__name__}，已自动转换")
                return float(value)
            elif target_type == bool:
                logging.warning(f"参数 '{key}' 类型不匹配，期望 bool，实际为 {type(value).__name__}，已自动转换")
                return bool(value)
            elif target_type == list:
                return [value]
            elif target_type == dict:
                logging.warning(f"参数 '{key}' 类型不匹配，期望 dict，实际为 {type(value).__name__}")
                return {}
            else:
                return value
        except Exception as e:
            logging.warning(f"参数 '{key}' 类型转换失败: {e}，使用原值")
            return value

    def _validate_dict(self, value: dict, item_schema, key: str):
        """验证字典类型的项"""
        if not isinstance(value, dict):
            return value

        result = value.copy()
        for field_key, field_type in item_schema.items():
            if field_key in result:
                result[field_key] = self._apply_type_conversion(f"{key}.{field_key}", result[field_key], field_type)
        return result

    def _validate_list(self, value: list, item_schema, key: str):
        """验证列表类型的项"""
        if not isinstance(value, list):
            return value

        return [self._apply_type_conversion(f"{key}[{i}]", item, item_schema) for i, item in enumerate(value)]

    def _merge_with_type_check(self, key: str, custom_value, attach_value, schema_info: dict, merge_type: str):
        """
        有 schema 类型定义时的合并逻辑

        参数:
        - key: 参数名称
        - custom_value: custom 中的值
        - attach_value: attach 中的值
        - schema_info: 完整的 schema 信息字典
        - merge_type: custom类型
        """
        import logging
        
        expected_type = schema_info.get("type")
        item_schema = schema_info.get("items")
        dict_schema = schema_info.get("dict_schema")

        # 检查是否是多种类型之一
        if isinstance(expected_type, tuple):
            # 检查 attach_value 是否匹配任意类型
            attach_matches = False
            for t in expected_type:
                type_to_check = t
                if isinstance(t, dict):
                    type_to_check = dict
                if isinstance(attach_value, type_to_check):
                    attach_matches = True
                    break
            
            if not attach_matches:
                # 尝试转换为第一个类型
                first_type = expected_type[0]
                if isinstance(first_type, dict):
                    first_type = dict
                attach_value = self._convert_to_type(attach_value, first_type, key)
            
            # 验证 attach_value
            if isinstance(attach_value, dict) and dict_schema:
                attach_value = self._validate_dict(attach_value, dict_schema, key)
            elif isinstance(attach_value, list) and item_schema:
                attach_value = self._validate_list(attach_value, item_schema, key)
            
            # 按实际类型处理
            return self._merge_by_actual_type(key, custom_value, attach_value, merge_type)

        # 预期类型是 list
        if expected_type == list:
            # 将两者都转为列表
            custom_list = [custom_value] if not isinstance(custom_value, list) else custom_value
            attach_list = [attach_value] if not isinstance(attach_value, list) else attach_value
            # 验证项
            if item_schema:
                custom_list = self._validate_list(custom_list, item_schema, key)
                attach_list = self._validate_list(attach_list, item_schema, key)
            return self._merge_arrays(custom_list, attach_list)

        # 预期类型是 dict
        elif expected_type == dict:
            if isinstance(custom_value, dict) and isinstance(attach_value, dict):
                nested_schema = self.schema.get(key) if isinstance(self.schema, dict) and isinstance(self.schema.get(key), dict) else None
                return self.merge_params(merge_type, custom_value, attach_value, nested_schema)
            elif isinstance(attach_value, dict):
                if dict_schema or item_schema:
                    return self._validate_dict(attach_value, dict_schema or item_schema, key)
                return attach_value
            else:
                logging.warning(f"参数 '{key}' 类型不匹配，期望 dict，attach值不是 dict")
                return custom_value

        # 预期类型是 str
        elif expected_type == str:
            if isinstance(attach_value, str):
                return attach_value
            else:
                logging.warning(f"参数 '{key}' 类型不匹配，期望 str，实际为 {type(attach_value).__name__}，已自动转换")
                return str(attach_value)

        # 预期类型是 int/float/bool
        elif expected_type in (int, float, bool):
            try:
                return expected_type(attach_value)
            except (ValueError, TypeError):
                logging.warning(f"参数 '{key}' 类型转换失败，期望 {expected_type.__name__}，使用 custom 值")
                return custom_value

        # 其他类型，按实际类型处理
        return self._merge_by_actual_type(key, custom_value, attach_value, merge_type)

    def _merge_by_actual_type(self, key: str, custom_value, attach_value, merge_type: str):
        """
        没有 schema 时按实际类型合并

        参数:
        - key: 参数名称
        - custom_value: custom 中的值
        - attach_value: attach 中的值
        - merge_type: custom类型（reco/action）
        """
        # 都是字典
        if isinstance(custom_value, dict) and isinstance(attach_value, dict):
            nested_schema = self.schema.get(key) if isinstance(self.schema, dict) and isinstance(self.schema.get(key), dict) else None
            return self.merge_params(merge_type, custom_value, attach_value, nested_schema)

        # 都是数组
        elif isinstance(custom_value, list) and isinstance(attach_value, list):
            return self._merge_arrays(custom_value, attach_value)

        # 一方是数组
        elif isinstance(custom_value, list) or isinstance(attach_value, list):
            custom_list = [custom_value] if not isinstance(custom_value, list) else custom_value
            attach_list = [attach_value] if not isinstance(attach_value, list) else attach_value
            return self._merge_arrays(custom_list, attach_list)

        # 一方是字符串，一方是对象
        elif (isinstance(custom_value, str) and isinstance(attach_value, dict)) or (isinstance(custom_value, dict) and isinstance(attach_value, str)):
            return [custom_value, attach_value]

        # 其他情况，attach 覆盖
        else:
            return attach_value

    def _get_identifier(self, item: dict) -> str | None:
        """
        从对象中获取标识符值
        按 IDENTIFIER_FIELDS 列表顺序查找第一个存在的字段
        """
        for field in self.IDENTIFIER_FIELDS:
            if field in item:
                return item[field]
        return None

    def _has_identifier(self, item: dict) -> bool:
        """检查对象是否有标识字段"""
        return any(field in item for field in self.IDENTIFIER_FIELDS)

    def _merge_arrays(self, original: list, attach: list) -> list:
        """
        合并两个数组
        - 如果 attach 中有带标识字段的对象，则按标识匹配合并：
          * 同标识对象：合并属性，attach 属性优先
          * 同标识（对象/字符串）：attach 项替换 original 项
          * 保留所有不同的字符串项（original 和 attach 独有的都保留）
        - 否则 attach 覆盖 original
        """
        if not attach:
            return original

        # 检查 attach 中是否有带标识字段的对象
        attach_has_named_objects = any(isinstance(item, dict) and self._has_identifier(item) for item in attach)

        if not attach_has_named_objects:
            # attach 覆盖 original
            return attach

        # 构建 original 的查找字典（按标识）
        original_dict = {}
        for item in original:
            if isinstance(item, dict):
                identifier = self._get_identifier(item)
                if identifier:
                    original_dict[identifier] = ("object", item)
            elif isinstance(item, str):
                original_dict[item] = ("string", item)

        # 收集 attach 中所有的标识（包括对象和字符串）
        attach_names = set()
        for item in attach:
            if isinstance(item, dict):
                identifier = self._get_identifier(item)
                if identifier:
                    attach_names.add(identifier)
            elif isinstance(item, str):
                attach_names.add(item)

        # 先添加 original 独有的字符串项
        result = []
        for item in original:
            if isinstance(item, str) and item not in attach_names:
                # original 独有的字符串，保留
                result.append(item)

        # 按 attach 顺序处理
        for attach_item in attach:
            if isinstance(attach_item, dict) and self._has_identifier(attach_item):
                # attach 对象项
                identifier = self._get_identifier(attach_item)
                if identifier in original_dict:
                    orig_type, orig_value = original_dict[identifier]
                    if orig_type == "object":
                        # 合并两个对象，attach 属性优先
                        merged_item = orig_value.copy()
                        merged_item.update(attach_item)
                        result.append(merged_item)
                    else:
                        # attach 对象替换 original 字符串
                        result.append(attach_item)
                else:
                    # 新增项
                    result.append(attach_item)
            elif isinstance(attach_item, str):
                # attach 字符串项
                name = attach_item
                if name in original_dict:
                    orig_type, orig_value = original_dict[name]
                    if orig_type == "object":
                        # attach 字符串替换 original 对象
                        result.append(attach_item)
                    else:
                        # 都是字符串，用 attach 的（去重）
                        if attach_item not in result:
                            result.append(attach_item)
                else:
                    # 新增字符串
                    result.append(attach_item)
            else:
                # 其他类型直接添加
                result.append(attach_item)

        return result


# 为了向后兼容，保留模块级别的函数
def merge_params(merge_type: str, custom_params: dict, attach_params: dict) -> dict:
    """
    通用参数合并方法（兼容函数）
    使用默认的 ParamMerger 实例进行合并
    """
    merger = ParamMerger()
    return merger.merge_params(merge_type, custom_params, attach_params)
