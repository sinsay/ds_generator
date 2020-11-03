from ...common.type_def import *

mapping_dict = {
    "void": "bool",
    "bool": "bool",
    "int": "int32",
    "int32": "int32",
    "int64": "int64",
    "float": "float",
    "double": "double",
    "string": "string",
    "char": "string",
    "list": "repeated",
    "dict": "message"
}

mapping_revers_dict = {
    "bool": "bool",
    "int32": "int",
    "int": "int",
    "float": "float",
    "str": "str",
    "string": "str",
    "list": "List",
    "dict": "dict",
    "void": "bool"
}

mapping_default = {
    "bool": "False",
    "int": "0",
    "int32": "0",
    "float": "0",
    "str": "\"\"",
    "string": "\"\"",
    "list": [],
    "dict": {},
    "void": "False"
}


def get_default(t: RpcType) -> str:
    if t.default_value is not None:
        if is_numeric(t) or is_boolean(t):
            return t.default_value
        if is_string(t):
            return f'"{t.default_value}"'
        if is_dict(t):
            return format(t.default_value)

    f = mapping_revert(t)
    return mapping_default.get(f)


def mapping(t: RpcType) -> str:
    """
    从 python type 转为 rpc type
    :param t:
    :return:
    """
    f = t.get_type()
    return mapping_dict.get(f)


def mapping_revert(t: RpcType) -> str:
    """
    从 rpc type 转为 python type
    :param t:
    :return:
    """
    if not hasattr(t, "get_type"):
        raise Exception(f"got an error argument of mapping_revert, expect RpcType got {type(t)} ")
    f = t.get_type()
    return mapping_revers_dict.get(f)
