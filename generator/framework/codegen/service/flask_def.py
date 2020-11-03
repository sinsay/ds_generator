from enum import Enum
import typing
import copy

from ....common import MetaData, Entry, RpcType, fields, type_def, CommonBase, ArgSource
from ....common.type_def import Model
from ....common.web.namespace import get_namespace, NamespaceInfo
from ..config import ConfigBase
from ...util.cfg_generator import CfgGenerator
from ...util.text import pretty_name, split_by_upper_character
from ..grpc_py_mapping import get_default, mapping_revert

from .flask_mapping import flask_mapping, flask_mapping_literal


class Method(Enum):
    GET = "get"
    POST = "post"
    PUT = "put"
    DELETE = "delete"
    OPTIONS = "options"

    def __cmp__(self, other):
        ov = other
        if hasattr(ov, "value"):
            ov = ov.value

        return self.value == ov


class FlaskDef(ConfigBase, CfgGenerator):
    """
    生成 Flask 服务的模板类
    """
    def __init__(
            self,
            meta_data: MetaData,
            args_path: str = "",
            runtime_path: str = "runtime",
            api_path: str = "src"
    ):
        ConfigBase.__init__(self, meta_data)
        CfgGenerator.__init__(self)

        # 用于保存嵌套类型的定义，后续生成时保存到函数定义前
        self.header_def = CfgGenerator()
        # 用于保存服务定义
        self.service_def = CfgGenerator()

        # 参数类型的生成路径
        # self.args_path = args_path or f".{self.meta_data.name.lower()}"
        self.args_path = args_path

        self.runtime_path = runtime_path

        self.api_path = api_path

    def gen_conf(self):
        self.header_def.append_with("from flask_restplus import fields")
        self.header_def.append_with(f"from {self.runtime_path}.runtime.web import SSResource")
        self.header_def.append_with(f"from {self.api_path} import api")
        if self.meta_data.impl_type is not None:
            impl_name = self.meta_data.impl_type.__name__
            as_name = self.meta_data.name + "Impl"
            if impl_name.endswith != as_name:
                imp_str = f"from {self.meta_data.impl_type.__module__} import {impl_name} as {as_name}"
            else:
                imp_str = f"from {self.meta_data.impl_type.__module__} import {impl_name}"
            self.header_def.append_with(imp_str)

        if self.meta_data.service_type is not None:
            self.header_def.append_with(
                f"from {self.meta_data.service_type.__module__} import \
{self.meta_data.name} as {self.meta_data.name}Define"
            )
        # namespace info

        ns = get_namespace(self.meta_data.service_type)

        if self.args_path:
            self.header_def.append_with(f"from {self.args_path} import ", new_line=False)

        self.append_with(f"ns = api.namespace(\"{ns.name}\", description=\"{ns.description}\")")
        self.append_with()
        self.append_with()

        entries_args = []
        for entry in self.meta_data.entries:
            a = pretty_name(f"{entry.name}_arg")
            r = pretty_name(f"{entry.name}_result")
            entries_args.append(f"{a}, {r}")

        if self.args_path:
            self.header_def.append_with(", ".join(entries_args))

        # gen model define
        self.gen_model_define(ns)

        # gen Resource define
        self.gen_resource_define(ns)

        with self.with_ident():
            for ent in self.meta_data.entries:
                self.gen_method(ent, ns)

    def get_header_conf(self) -> str:
        return "".join(self.header_def.conf)

    def get_conf(self) -> str:
        return "".join(self.conf)

    def gen_model_define(self, _ns: NamespaceInfo):
        """
        生成该模块所需使用的参数模型及返回值模型定义，也包括了参数或返回值中的嵌套类型
        """
        for entry in self.meta_data.entries:
            args_dict = {}
            for arg in entry.args:
                if arg.source.value == ArgSource.PATH.value \
                        or arg.source.value == ArgSource.HEADER.value:
                    continue
                args_dict[arg.name] = arg.arg_type

            # gen argument first
            model = fields.model(
                # pretty_name(f"{self.meta_data.name}_{entry.name}"),
                self.meta_data.name,
                args_dict
            )
            self.build_arg_model(entry, model)

            if entry.result is not None:
                self.append_with()
                self.build_result_model(entry)

    def build_result_model(self, entry: Entry):
        """
        gen result
        """
        self.append_with()
        result_name = pretty_name(f"{self.meta_data.name}_{entry.name}_result_model")
        self.append_with(f"{result_name} = ns.response(")
        with self.with_ident():
            self.append_with("200,")
            self.append_with(f"\"{entry.result.description}\",")
            self.append_with(f"api.model(\"{result_name}\", {{")
            with self.with_ident():
                result: typing.Union[type_def.Dict, type_def.Void] = entry.result
                if result.get_type() != "void":
                    self.build_dict(result.get_elem_info(), result_name)
            self.append_with("})")
        self.append_with(")")

    def gen_resource_define(self, ns: NamespaceInfo):
        """
        根据当前 Resource 的定义生成 Flask 的接口定义
        """
        self.append_with()
        self.append_with()
        for url in ns.urls:
            self.append_with(f"@ns.route(\"{url}\")")
        for name, field in ns.params.items():
            self.append_with(f"@ns.param(\"{name}\", \"{field.description}\")")
        self.append_with(f'class {self.meta_data.name}Resource(SSResource):')

    def gen_method(self, entry: Entry, ns: NamespaceInfo):
        """
        生成具体的方法定义
        WARN: 如果有额外的 url 参数，则需要为每个生成的接口定义额外的参数
              现在已经不直接由 dispatch 来调用对应的接口了，所以应该无需在构建函数时添加
              额外的参数信息了
        """
        # 暂时只支持顶级 header 定义，TODO: 后续添加嵌套字段的 header 定义
        headers = filter(lambda a: a.source.value == ArgSource.HEADER.value, entry.args)
        _extra_args = get_extra_args(ns)
        self.append_with()
        model_name = f"{self.meta_data.name}_{entry.name}"
        arg_model = pretty_name(f"{model_name}_arg_model")
        arg_type = pretty_name(f"{entry.name}_arg")
        result_model = pretty_name(f"{model_name}_result_model")
        self.append_with(f"@{arg_model}")
        self.append_with(f"@{result_model}")
        for h in headers:
            self.append_with("@api.header(")
            with self.with_ident():
                self.append_with(f"\"{h.name}\",")
                self.append_with(f"description=\"{h.description}\",")
                self.append_with(f"required={h.required},")
                self.append_with(f"type={mapping_revert(h.arg_type)},")
                self.append_with(f"default={get_default(h.arg_type)}")
            self.append_with(")")
        self.append_with(f"def {entry.name}(self, *args, **kwargs) -> {pretty_name(entry.name)}Result :")
        with self.with_ident():
            self.append_with('"""')
            self.append_with(entry.description)
            self.append_with('"""')
            self.append_with("# extract args with method_name, define class, args type, addition args")
            self.append_with(
                f"args = self.extract_args(\"{entry.name}\", {self.meta_data.name}Define, {arg_type}, *args, **kwargs)"
            )
            if self.meta_data.impl_type is not None:
                self.append_with(
                    f"impl = {self.meta_data.name}Impl()"
                )
                self.append_with(f"return impl.{entry.name}(args)")
            else:
                self.append_with("raise NotImplementedError(\"Please Implement the logic first\")")

    def build_arg_model(self, entry: Entry, model: Model):
        """
        构建参数或返回值的 Model
        """
        model_name = f"{model.name}_{entry.name}_arg_model"
        ns_method = "doc"

        self.append_with(f"{pretty_name(model_name)} = ns.{ns_method}(")
        arg_dict = model.fs.get_elem_info()

        if entry.name == Method.GET.value:
            with self.with_ident():
                self.append_with(f"\"{pretty_name(model_name)}\",")
                self.append_with("params={")
                with self.with_ident():
                    self.build_get_dict(arg_dict)
                self.append_with("}")
        else:
            with self.with_ident():
                self.append_with(f"\"{model_name}\",")
                self.append_with(f"expect=[api.model(\"{pretty_name(model_name)}\", {{"),
                with self.with_ident():
                    self.build_dict(arg_dict, model_name)
                self.append_with("})]")

        self.append_with(")")
        self.append_with()

    def build_get_dict(self, fs: typing.Dict[str, RpcType]):
        for key, value in fs.items():
            if type_def.is_base_type(value):
                self.append_with(f"\"{key}\": {{")
                with self.with_ident():
                    self.append_with(f"\"type\": {flask_mapping_literal(value)},")
                    self.build_get_common(value)
                self.append_with("},")
            else:
                raise NotImplementedError("The get method's argument can not be nested type")

    def build_dict(self, fs: typing.Dict[str, RpcType], prev_key: str):
        for key, value in fs.items():
            # 跳过 Header 定义
            if value.get_source().value == ArgSource.HEADER.value:
                continue

            value: typing.Any = value
            if type_def.is_base_type(value):
                self.append_with(f"\"{key}\": {flask_mapping(value)}(")
                with self.with_ident():
                    self.build_common(value)
                self.append_with("),")
            elif type_def.is_enum(value):
                enum_item_type: RpcType = value.rpc_type
                self.append_with(f"\"{key}\": {flask_mapping(enum_item_type)}(")
                with self.with_ident():
                    new_value = copy.copy(enum_item_type)
                    new_value.name = value.name or "EMPTY"
                    new_value.description = \
                        value.description + \
                        f" <a href=\"\"javascript:%24(%22%5bhref%3d%27%23!%2fenum%2fget_" +\
                        f"{split_by_upper_character(value.name, splitter='_').lower()}%27%5d%22).focus();\"\">" +\
                        f"跳转至详情</a>"

                    new_value.default_value = value.default_value
                    self.build_common(new_value)
                self.append_with("),")
            elif type_def.is_dict(value):
                self.append_with(f"\"{key}\": {flask_mapping(value)}(")
                with self.with_ident():
                    field_model_name = pretty_name(f"{prev_key}_{key}")
                    self.append_with(f"model=api.model(\"{field_model_name}\", {{")
                    dict_value: type_def.Dict = value
                    with self.with_ident():
                        self.build_dict(dict_value.get_elem_info(), field_model_name)
                    self.append_with("}),")
                    self.build_common(value)
                self.append_with("),")

            elif type_def.is_list(value):
                self.append_with(f"\"{key}\": {flask_mapping(value)}(")
                list_elem: type_def.List = value
                list_elem = list_elem.get_elem()
                with self.with_ident():
                    self.build_list(list_elem, f"{prev_key}_{key}")
                    self.build_common(value)
                self.append_with("),")

    def build_list(self, elem, prev_key: str):
        if type_def.is_base_type(elem):
            self.append_with(f"{flask_mapping(elem)}(")
            with self.with_ident():
                self.build_common(elem)
            self.append_with("),")
        elif type_def.is_enum(elem):
            new_value = copy.copy(elem.rpc_type)
            new_value.name = elem.name or "EMPTY"
            # new_value.description = elem.description + f" [跳转至详情](#!/enums/{elem.name})"
            new_value.description = \
                elem.description + \
                f" <a href=\"\"javascript:%24(%22%5bhref%3d%27%23!%2fenum%2fget_" + \
                f"{split_by_upper_character(elem.name, splitter='_').lower()}%27%5d%22).focus();\"\">" + \
                f"跳转至详情</a>"

            new_value.default_value = elem.default_value
            elem_type: RpcType = elem.rpc_type
            self.append_with(f"{flask_mapping(elem_type)}(")
            with self.with_ident():
                self.build_common(elem)
            self.append_with("),")
        elif type_def.is_dict(elem):
            self.append_with(f"{flask_mapping(elem)}(")
            with self.with_ident():
                self.append_with(f"model=api.model(\"{prev_key}\", {{")
                with self.with_ident():
                    dict_elem: type_def.Dict = elem
                    self.build_dict(dict_elem.get_elem_info(), prev_key)
                self.append_with("}),")
                self.build_common(elem)
            self.append_with("),")
        elif type_def.is_list(elem):
            self.append_with(f"{flask_mapping(elem)}(")
            with self.with_ident():
                self.build_dict(elem.get_elem(), prev_key)
                self.append_with(",")
                self.build_common(elem)
            self.append_with("),")
        else:
            raise NotImplementedError(f"building elem with unknown type {elem}")

    def build_common(self, value: RpcType):
        self.append_with(f"required={value.required},")
        self.append_with(f"description=\"{value.description}\",")
        if value.default_value is not None:
            self.append_with(f"default={get_default(value)},")

    def build_get_common(self, value: RpcType):
        self.append_with(f"\"required\": {value.required},")
        self.append_with(f"\"description\": \"{value.description}\",")
        if value.default_value is not None:
            self.append_with(f"\"default\": {get_default(value)},")


def get_extra_args(ns: NamespaceInfo) -> typing.List[typing.Tuple[str, RpcType]]:
    result = []
    for k, v in (ns.params or {}).items():
        result.append((k, v))

    return result


def __test_meta_define__():
    resp_model = fields.model("hello", {
        "id": fields.Integer(required=True, description="id"),
        "schools": fields.List(
            fields.Integer(),
            description="list of school"
        ),
        "info": fields.Dict({
            "addr_list": fields.List(fields.Dict({
                "road": fields.String(),
                "no": fields.Integer(description="road no")
            }, description="addr_list"))
        }, description="info"),
        "name": fields.String(required=True, description="user name", default_value="no name"),
        "status": fields.Enum({
            "OK": fields.Integer(description="OK", default_value=0),
            "ERROR": fields.Integer(description="ERROR", default_value=1)
        }, name="TestEnum")
    }, description="response model")

    args_model = fields.model("args", {
        "id": fields.Integer(required=True)
    }, description="request model")

    from ....common import namespace, Arg

    ns = namespace.Namespace("test", description="test ns")

    @ns.add_resource("/hello/<int:token>/login", params={
        "token": fields.Integer(description="token desc")
    })
    class Resource(CommonBase):
        @fields.args(args_model)
        @fields.resp(resp_model)
        def get(self):
            pass

    entry_args = map(lambda kv:  Arg(kv[0], kv[1], None), args_model.fs.get_elem_info().items())
    meta = MetaData(Resource.__name__, Resource, [
        Entry("get", list(entry_args), resp_model.fs)
    ])

    return meta


def __test__():
    meta = __test_meta_define__()
    fd = FlaskDef(meta)
    fd.gen_conf()
    print(fd.get_conf())
