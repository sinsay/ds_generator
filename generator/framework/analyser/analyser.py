import inspect
import re
import types

from collections import namedtuple
from typing import List, Union, Dict
from flask_restplus import fields

from ...common import MetaData, Entry, Arg, ArgSource, RpcType,\
    type_def, rpc_doc_args_key, rpc_doc_resp_key, rpc_impl_rename
from ...common.web.namespace import get_namespace, NamespaceInfo


function_type = frozenset([staticmethod, classmethod, types.FunctionType])

func_obj_types = frozenset([staticmethod, classmethod])

method_reg = re.compile(r"^[\s\S]+?(?=:param|:return:|$)")


class Analyser(object):
    """
    解析器，解析指定的类型所绑定的 document 信息
    """
    @staticmethod
    def analyse(service_classes, service_impl_classes, need_impl: bool = True) -> List[MetaData]:
        """
        解析 service_classes 的信息，并返回其元数据，如果该类型未添加元数据，则不将其加入元数据列表
        service_impl_classes 则为对应 service 的实现器, 两者应该是一一对应的关系
        need_impl 指示了是否需要为 service_class 获取其具体实现
        :param service_classes:
        :param service_impl_classes
        :param need_impl:
        :return:
        """
        meta_data = []
        for c in service_classes:

            methods = extract_methods(c)
            if not methods:
                continue

            # 查看是否有自定义名称
            impl_name = getattr(c, rpc_impl_rename, c.__name__)

            # 找到对应 impl
            impl = list(filter(lambda i: i.__name__ ==
                               impl_name, service_impl_classes))
            if not impl and need_impl:
                raise Exception(
                    "found service %s definition without implement code" % c.__name__)

            meta = MetaData(c.__name__, c, methods,
                            impl_type=impl and impl[0] or None)
            meta_data.append(meta)

        return sorted(meta_data, key=lambda m: m.name.lower())


def extract_methods(cls):
    """
    解析一个 Class, 得到所有定义了 api doc 的方法
    :param cls:
    :return:
    """

    # process cls' s apidoc if exists
    base_entries_arg: List[Arg] = process_cls_args(cls)

    entries = []
    for (attr_name, attr) in cls.__dict__.items():
        attr_type = type(attr)
        if attr_name.startswith('_') or attr_type not in function_type:
            continue

        rpc_doc_args: type_def.Dict = getattr(attr, rpc_doc_args_key, None)
        rpc_doc_resp: type_def.RpcType = getattr(attr, rpc_doc_resp_key, None)

        if attr_type in func_obj_types:
            # extract real method from method object
            attr = getattr(attr, "__func__", None)

        api_doc = getattr(attr, '__apidoc__', None)

        # TODO: 暂时不做多种配置方式的合并, 后续考虑提供
        entry = None
        if api_doc:
            entry = analyse_doc(cls, attr, attr_name, api_doc, base_entries_arg)
            entry.args = base_entries_arg + entry.args

        args = list(base_entries_arg)

        result = type_def.Void()
        if rpc_doc_args:
            # args 必然是 model 的 RpcType.Dict 类型
            # 根据 attr_name 来选择 ArgSource, 如果是非 http method, 则不管设置
            # 成何种类型都不会有影响

            for name, value in rpc_doc_args.get_elem_info().items():
                source = get_source_type(attr_name, value)
                args.append(Arg(name, value, value.default_value,
                                value.description, value.required, source))

        if rpc_doc_resp:
            result = rpc_doc_resp

        if not entry:
            raw_doc = inspect.getdoc(attr) or ""
            method_doc = method_reg.search(raw_doc)
            if method_doc:
                method_doc = method_doc.group(0)

            args = sorted(args, key=lambda a: a.name.lower())
            entry = Entry(attr_name, args, result, method_doc)

        entries.append(entry)

    return sorted(entries, key=lambda e: e.name.lower())


def get_source_type(method_name: str, field: RpcType) -> ArgSource:
    """
    获取 field 字段的来源信息，首先根据方法名，如果是 http 的方法，
    则按照 get 对应 params, post 对应 body 的形式，
    如果 field 主动设置了 source, 则使用 field 的
    """
    source = ArgSource.UNKNOWN
    if method_name == "get":
        source = ArgSource.PARAMS
    elif method_name == "post":
        source = ArgSource.BODY

    if field.source != ArgSource.UNKNOWN:
        source = field.get_source()

    return source


def process_cls_args(cls) -> List[Arg]:
    """
    从 cls 的 api_doc 中获取参数信息
    """
    cls_api_doc = getattr(cls, "__apidoc__", {})
    params: dict = cls_api_doc.get("params", {})

    args: List[Arg] = []
    for key, value in params.items():
        field_type = switch_type(value.get("type", "str"), value)
        source_in = value.get("in", "path")
        source = ArgSource.PARAMS
        if source_in == "path":
            source = ArgSource.PATH
        elif source_in == "body":
            source = ArgSource.BODY
        elif source_in == "header":
            source = ArgSource.HEADER

        args.append(Arg(key, field_type, field_type.default_value, source=source, description=field_type.description))

    # 处理完 Flask 的定义，还需要处理 CommonBase 的定义
    ns_info: Union[NamespaceInfo, None] = get_namespace(cls)
    if ns_info is not None:
        for arg_name, arg_value in ns_info.params.items():
            args.append(
                Arg(
                    arg_name,
                    arg_value,
                    arg_value.default_value,
                    description=arg_value.description,
                    required=arg_value.required,
                    source=ArgSource.PATH
                )
            )
    return args


def analyse_doc(cls, method, name, api_doc, class_args: List[Arg]) -> Entry:
    """
    解析 cls 类型中 method 的 api_doc 信息，转换为本地格式，便于后续的分析
    :param cls
    :param method
    :param name:
    :param api_doc:
    :param class_args:
    :return:
    """
    # 首先查找函数命名的参数
    # 首先解开函数的 wrapper, 拿到实际调用的函数体

    while hasattr(method, "__wrapped__"):
        method = getattr(method, "__wrapped__")

    # 尝试获取 entry 的注释
    method_doc_raw = inspect.getdoc(method) or ""
    method_doc = method_reg.search(method_doc_raw) or ""
    if method_doc:
        method_doc = method_doc.group(0)

    args = analyse_args(cls, method, method_doc_raw, api_doc, class_args)
    entry = Entry(name, args, type_def.Void(), method_doc)

    status_codes = api_doc.get("responses", {}).keys()
    for status_code in status_codes:
        result = analyse_result(api_doc, status_code)
        if result:
            entry.set_result(status_code, result)
    return entry


def analyse_result(api_doc, status_code: int) -> type_def.RpcType:
    """
    解析出 api_doc 中的返回值信息
    :param api_doc:
    :param status_code:
    :return:
    """
    (desc, data_meta) = api_doc.get("responses", {}).get(status_code, (None, None))
    if not desc and not data_meta:
        return type_def.Void()  # 该接口返回空类型

    if isinstance(data_meta, dict):
        # 说明是复合类型
        result = type_def.fields.Dict(required=True)
        for (key, type_info) in data_meta.items():
            result.add_field(key, switch_type(type_info))
    else:
        # 说明是基础类型
        result = switch_type(data_meta)

    return result


def analyse_args(cls, method, method_doc_raw, api_doc, class_args: List[Arg]) -> List[Arg]:
    """
    cls 为要解析的模块， method 为该模块对应的方法， api_doc 是该 method 的描述文件
    通过以上信息解析出该函数的参数信息
    :param cls:
    :param method:
    :param method_doc_raw:
    :param api_doc:
    :param class_args:
    :return:
    """
    frame_info = inspect.getfullargspec(method)
    method_args = frame_info.args
    if len(frame_info.args) > 0 and frame_info.args[0] == "self":
        method_args = method_args[1:]

    if len(method_args) > len(frame_info.annotations):
        #  缺少必要的参数类型描述
        raise Exception(
            "模块 %s 的函数 %s 有 %s 个参数，但具有类型描述的参数个数只有 %s 个. \n"
            "请为缺少类型描述的参数 %s 添加类型信息, eg: 为 id 添加参数说明\n\t"
            "def hello(id: int): pass" %
            (
                cls.__name__,
                method.__name__,
                len(frame_info.args),
                len(frame_info.annotations),
                frame_info.args
            )
        )

    params: List[Arg] = []
    params_dict = api_doc.get("params", {})
    params.extend(analyse_flask_args(method, params_dict, False) or [])

    # post
    expect_list = api_doc.get("expect", [])
    for expect in expect_list:
        params.extend(analyse_flask_args(method, expect, True) or [])

    # 最后才处理函数定义的参数
    func_params: List[Arg] = []
    for (index, arg) in enumerate(method_args):
        arg_type = switch_type(frame_info.annotations[arg])
        if isinstance(arg_type, (type_def.Void, )):
            continue

        # try to extract documentation from doc
        arg_doc = re.search(
            r":param %s:(?P<doc>[\s\S]+?)(?=:param|:return|$)" % arg, method_doc_raw)
        if arg_doc:
            arg_doc = arg_doc.group("doc")

        arg_info = Arg(arg, arg_type, None, arg_doc or "")
        func_params.append(arg_info)

    args_len = len(func_params) - 1
    for (index, default) in enumerate(frame_info.defaults or []):
        func_params[len(args_len - index)].default = default

    # 移除重复的参数
    for p in func_params:
        is_dup: bool = False
        for pp in params:
            if p.name == pp.name:
                is_dup = True
                break
        if not is_dup:
            for pp in class_args:
                if p.name == pp.name:
                    is_dup = True
                    break

        if not is_dup:
            params.append(p)

    return params


def analyse_flask_args(method, type_dict, in_body: bool) -> List[Arg]:
    """
    解析 type_dict 中的信息，将其转换为无 flask 模块依赖的类型信息
    :param method
    :param type_dict:
    :param in_body: 如果 in_body 则参数来自于 body, 否则的话需要根据 in 字段进行判断，如果
                    in header 则参数来自 header, 否则是 get 的参数
    :return:
    """
    params = []
    for (key, value) in type_dict.items():
        if isinstance(value, dict):
            # 可能是 param 定义，或 flask doc 的说明
            attr_type = value.get("type", None)
            attr_type = switch_type(attr_type, value)
            if not attr_type or isinstance(attr_type, type_def.Void):
                raise Exception("%s 的参数 %s 没有类型定义" % (method, key))

            if in_body:
                source = ArgSource.BODY
            else:
                if value.get("in", "params") == "params":
                    source = ArgSource.PARAMS
                else:
                    source = ArgSource.HEADER

            arg = Arg(key, attr_type, default=value.get("default", None),
                      description=value.get("description", ""), source=source,
                      required=attr_type.required)

            params.append(arg)
        else:
            attr_type = switch_type(value)
            if attr_type:
                if in_body:
                    source = ArgSource.BODY
                else:
                    source = ArgSource.PARAMS

                required = True
                if value.required is not None:
                    required = not not value.required

                arg = Arg(key, attr_type, attr_type.default_value, value.description,
                          required=required, source=source)
                params.append(arg)

    return params


str_literal = ["str", "string"]
number_literal = ["int", "integer"]

base_mapping_fields = {
    "default": None,
    "required": True,
    "default_value": None,
    "maximum": None,
    "minimal": None,
}


sm = namedtuple(
    "DefaultMapping",
    [
        "description", "required", "min_length",
        "max_length", "min_items", "max_items",
        "default_value", "must_true",
        "must_false", "minimum", "maximum"
    ]
)(
    ("description", ""),
    ("required", True),
    ("min_length", None),
    ("max_length", None),
    ("min_items", None),
    ("max_items", None),
    ("default_value", None),
    ("must_true", None),
    ("must_false", None),
    ("minimum", None),
    ("maximum", None)
)

field_adaptor = {
    "minimum": "min",
    "maximum": "max",
    "default_value": "default"
}

base_sm = [sm.description, sm.default_value, sm.required]


def build_sm(*args, need_base: bool = True):

    sm_list = (need_base and base_sm or []) + list(args)

    def wrap(addition: Union[Dict, object, None]):
        def get_method(_key, _default):
            pass

        if isinstance(addition, dict):
            def get_method(key, default_value):
                return addition.get(key, default_value)
        elif isinstance(addition, object):
            def get_method(key, default_value):
                return getattr(addition, key, default_value)

        d = {}
        for (k, v) in sm_list:
            d[k] = v
            if not addition:
                continue

            v = get_method(k, None)
            if v is None:
                adapt_key = field_adaptor.get(k, None)
                if adapt_key is not None:
                    v = get_method(adapt_key, None)

            if v is not None:
                d[k] = v

        return d

    return wrap


number_sm = build_sm(sm.minimum, sm.maximum)
str_sm = build_sm(sm.min_length, sm.max_length)
bool_sm = build_sm(sm.must_true, sm.must_false)
list_sm = build_sm(sm.description, sm.min_items, sm.max_items, need_base=False)

type_switch_mapping = {
    "int": number_sm,
    int: number_sm,
    "integer": number_sm,
    fields.Integer: number_sm,
    "float": number_sm,
    float: number_sm,
    fields.Float: number_sm,
    "str": str_sm,
    "string": str_sm,
    str: str_sm,
    fields.String: str_sm,
    "bool": bool_sm,
    bool: bool_sm,
    fields.Boolean: bool_sm,
    "list": list_sm,
    fields.List: list_sm,
}

type_convert_mapping = {
    int: type_def.fields.Integer,
    str: type_def.fields.String,
    float: type_def.fields.Float,
    bool: type_def.fields.Bool,
    fields.Integer: type_def.fields.Integer,
    fields.String: type_def.fields.String,
    fields.Boolean: type_def.fields.Boolean,
    fields.Float: type_def.fields.Float
}


def switch_type(from_type, addition: Union[dict, None] = None) -> type_def.RpcType:
    """
    转换类型定义，将第三的定义转换为本地类型,
    addition 为 flask 类型信息的附加信息，可以为其增加类似 maximum, default, max_items 等信息
    :param from_type:
    :param addition
    :return:
    """

    map_func = type_switch_mapping.get(from_type, None)
    if map_func is None:
        map_func = type_switch_mapping.get(type(from_type), lambda _: {})

    kwargs = map_func(addition)

    if isinstance(from_type, str):
        if from_type in str_literal:
            return type_def.fields.String(**kwargs)
        elif from_type in number_literal:
            return type_def.fields.Integer(**kwargs)

    # 如果是基础类型，或 flask 的基础类型，可以直接构造
    from_type_constructor = type_convert_mapping.get(from_type, None)
    if not from_type_constructor:
        from_type_constructor = type_convert_mapping.get(type(from_type), None)

    if from_type_constructor:
        return from_type_constructor(**kwargs)

    if isinstance(from_type, fields.List):
        elem_type = switch_type(from_type.container)
        return type_def.fields.List(
            elem_type, **kwargs)
    elif isinstance(from_type, fields.Nested):
        field_dict = {}
        for (field, field_value) in from_type.model.items():
            field_dict[field] = switch_type(field_value, field_value)
        return type_def.fields.Dict(field_dict, from_type.description, from_type.required)
    else:
        return type_def.Void()
