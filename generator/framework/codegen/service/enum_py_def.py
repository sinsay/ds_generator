from ..config import ConfigBase
from ...util.cfg_generator import CfgGenerator
from ..grpc_py_mapping import get_default
from ...analyser.module_scanner import EnumWithVar

from .flask_mapping import flask_mapping_literal


class EnumPyDef(ConfigBase, CfgGenerator):
    """
    生成 枚举 类型定义的模板类
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
        self.gen_enum_define()

    def get_header_conf(self) -> str:
        return "".join(self.header_def.conf)

    def get_conf(self) -> str:
        return "".join(self.conf)

    def gen_enum_define(self):
        """
        根据当前枚举的定义生成 枚举类
        """
        self.append_with(f"class _{self.enum_info.enum.name}(object):")
        with self.with_ident():
            self.append_with('"""')
            self.append_with(self.enum_info.enum.description)
            self.append_with('"""')
            self.append_with()

            self.append_with("enum_description = {")
            with self.with_ident():
                for key, value in self.enum_info.enum.enum_dict.items():
                    self.append_with(f"{get_default(value)}: \"{value.description}\",")
            self.append_with("}")

            for key, value in self.enum_info.enum.enum_dict.items():
                self.append_with("@property")
                self.append_with(f"def {key}(self) -> {flask_mapping_literal(value)}:")
                with self.with_ident():
                    self.append_with('"""')
                    self.append_with(value.description)
                    self.append_with('"""')
                    self.append_with(f"return {get_default(value)}")

                self.append_with()

            self.append_with("@classmethod")
            self.append_with(f"def get_desc(cls, value: {flask_mapping_literal(self.enum_info.enum.rpc_type)}) -> str:")
            with self.with_ident():
                self.append_with("return cls.enum_description.get(value, \"\")")

        self.append_with()
        self.append_with()
        self.append_with(f"{self.enum_info.enum.name} = _{self.enum_info.enum.name}()")
        self.append_with()
        self.append_with()
