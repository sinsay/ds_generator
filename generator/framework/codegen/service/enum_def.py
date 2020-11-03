from ..config import ConfigBase
from ...util.cfg_generator import CfgGenerator
from ...util.text import pretty_name
from ..grpc_py_mapping import get_default
from ...analyser.module_scanner import EnumWithVar

from .flask_mapping import flask_mapping


class EnumDef(ConfigBase, CfgGenerator):
    """
    生成 枚举 服务的模板类
    """
    def __init__(
            self,
            enum_info: EnumWithVar,
            runtime_path: str = "runtime",
            api_path: str = "src"
    ):
        ConfigBase.__init__(self, None)
        CfgGenerator.__init__(self)

        # 用于保存嵌套类型的定义，后续生成时保存到函数定义前
        self.header_def = CfgGenerator()
        # 用于保存服务定义
        self.service_def = CfgGenerator()

        self.runtime_path = runtime_path

        self.api_path = api_path

        self.enum_info = enum_info

    def gen_conf(self):
        header = self.header_def
        header.append_with("from flask_restplus import fields, Resource")
        header.append_with(f"from {self.api_path} import api")
        header.append_with()
        header.append_with()
        header.append_with(f"ns = api.namespace(\"enum\", description=\"枚举定义信息\")")
        header.append_with()
        header.append_with()

        self.gen_resource_define()

    def gen_enum_model(self, name: str):
        # TODO: 太丑了，考虑增加一个新的格式化接口
        self.append_with(f"{pretty_name(name)}EnumResultModel = ns.response(")
        with self.with_ident():
            self.append_with("200,")
            self.append_with(f"\"{self.enum_info.enum.description}<br/>\"")
            for key, value in self.enum_info.enum.enum_dict.items():
                self.append_with(f"\"{value.default_value}: {key} - {value.description}<br/>\"")
            self.append_with(",")
            self.append_with(f"api.model(\"{pretty_name(name)}EnumResultDefine\", {{")
            with self.with_ident():
                self.append_with("\"info\": fields.List(")
                with self.with_ident():
                    self.append_with("fields.Nested(")
                    with self.with_ident():
                        self.append_with(f"model=api.model(\"{pretty_name(name)}EnumResultInfoDefine\", {{")
                        with self.with_ident():
                            self.append_with("\"key\": fields.String(description=\"枚举名称\"),")
                            self.append_with(f"\"value\": {flask_mapping(self.enum_info.enum.rpc_type)}(")
                            with self.with_ident():
                                self.append_with("description=\"枚举值\",")
                                if self.enum_info.enum.rpc_type.default_value is not None:
                                    self.append_with(f"default={get_default(self.enum_info.enum.rpc_type)}")
                            self.append_with("),")
                        self.append_with("}),")
                        # self.append_with(f"\"description\": \"{self.enum_info.enum.description}")
                    self.append_with(")")
                self.append_with(")")
            self.append_with("})")
        self.append_with(")")

    def get_header_conf(self) -> str:
        return "".join(self.header_def.conf)

    def get_conf(self) -> str:
        return "".join(self.conf)

    def gen_resource_define(self):
        """
        根据当前枚举的定义生成 Flask 的接口
        """
        self.append_with()
        self.append_with()
        # 优先使用枚举名，当没定义时使用变量名
        name = self.enum_info.enum.name or self.enum_info.var_name
        if not name:
            raise ValueError("枚举类型必须有确定的名称")

        self.gen_enum_model(name)
        self.append_with()
        self.append_with()

        self.append_with(f"@ns.route(\"/{name}\")")
        self.append_with(f"class {pretty_name(name)}(Resource):")
        with self.with_ident():
            self.append_with(f"@{pretty_name(name)}EnumResultModel")
            self.append_with("def get(self):")
            with self.with_ident():
                self.gen_enum_result()

    def gen_enum_result(self):
        """
        生成枚举接口的返回值
        """
        self.append_with("return {")
        with self.with_ident():
            self.append_with("\"info\": [")
            with self.with_ident():
                for key, value in self.enum_info.enum.enum_dict.items():
                    self.append_with("{")
                    with self.with_ident():
                        self.append_with(f"\"key\": \"{key}\",")
                        self.append_with(f"\"value\": {get_default(value)},")
                        self.append_with(f"\"description\": \"{value.description}\",")
                    self.append_with("},")
            self.append_with("]")
        self.append_with("}")
