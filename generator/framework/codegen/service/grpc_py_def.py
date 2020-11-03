"""
生成 rpc 服务的接口定义
"""

import typing
from .. import grpc_py_mapping as mapping

from ....common import MetaData, Entry, Arg, type_def
from ...util.text import upper_first_character, pretty_name
from ...util.cfg_generator import CfgGenerator
from ..base import ConfigBase
from .... import config


class GrpcPyDef(ConfigBase, CfgGenerator):
    """
    根据 MetaData 生成 gRPC 的的代码

    生成对 rpc 调用的二次封装
    1. 按照模块生成 rpc 接口
    2. 生成 rpc 接口的参数及返回值类型
        1. 用于智能提示
        2. 用于类型限制
    3. 生成的类型要能够与 grpc 的类型进行互转
    """

    def __init__(self, meta_data: MetaData, need_servicer: bool = True):
        """
        need_service 为 False 时不需要依赖于 config 的配置
        """
        ConfigBase.__init__(self, meta_data)
        CfgGenerator.__init__(self)

        # 用于保存嵌套类型的定义，后续生成时保存到函数定义前
        self.header_def = CfgGenerator()
        # 用于保存服务定义
        self.service_def = CfgGenerator()

        # 将生成的文件名
        self.file_name = pretty_name(self.meta_data.name)

        # 将生成的模块名
        self.module_name = pretty_name(self.meta_data.name)

        # 当前模块正在处理的层级，如 module、service、arg、sub_arg
        # 用于为嵌套定义的类型生成名称
        self.curr_entry_name = []

        # 是否要生成 Servicer 定义
        self.need_service = need_servicer

    def gen_conf(self):
        """
        生成 gRPC 的配置文件文本，并保存在自身的 conf 中
        :return:
        """
        for entry in self.meta_data.entries:
            try:
                self.process_entry_def(entry)
            except Exception as e:
                print(f"Error occur while generating Entry {entry.name} \
of Meta {self.meta_data.name} with message {str(e)}")

        self.header_def.conf = self.conf
        self.conf = []

        if self.need_service:
            try:
                self.process_servicer()
            except Exception as e:
                print(f"Error {str(e)}occur while generating Meta {self.meta_data.name}'s servicer define")

        self.conf = []

    def process_servicer(self):
        # 最后才实现 RPC Class
        self.append_with("class %s(ServiceClient):" % self.module_name)
        with self.with_ident():
            # 如果生成到单独的项目中，则使用该项目的名称
            if config.outside_server:
                self.append_with("from_project = \"%s\"" % config.outside_server_name)
            else:
                self.append_with("from_project = \"%s\"" % config.source_project_name)
            self.append_with("rpc_name = \"%s\"\n" % self.module_name)

        for entry in self.meta_data.entries:
            self.process_entry(entry)

        # reg client to context
        self.append_with()
        self.append_with("reg_client(%s.rpc_name, %sStub)" % (self.module_name, self.module_name))
        self.service_def.conf = self.conf

    def get_header(self):
        """
        获取参数及返回值定义
        :return:
        """
        self.append_with("# coding: utf-8\n")
        self.append_with("import typing")
        self.append_with("from ..encode import %s_pb2 as pb2" % self.module_name.lower())
        self.append_header_common()
        self.append_with("\n")
        result = "".join(self.conf + self.header_def.conf)
        self.conf = []
        return result

    def append_header_common(self):
        self.append_with("from ...runtime.runtime.common import RPCDict")

    def get_service(self):
        """
        获取服务定义
        :return:
        """
        self.append_with("# coding: utf-8\n")
        self.append_with("import typing")
        self.append_with("from .src.encode.%s_pb2_grpc import %sStub" % (self.module_name.lower(), self.module_name))
        self.append_with("from .src.impl.%s import *" % self.meta_data.name.lower())

        self.append_with("from .runtime.runtime import ServiceClient, reg_client, RPCOption")
        self.append_with("from .runtime.runtime.concurrency.local_trace import TraceContext")

        self.append_with("\n")

        result = "".join(self.conf + self.service_def.conf)
        self.conf = []
        return result

    def to_cfg_string(self) -> str:
        self.conf = self.header_def.conf + self.service_def.conf
        return "".join(self.conf)

    def cfg_string(self) -> str:
        """
        获取 cfg 当前的代码片段
        """
        return "".join(self.conf)

    def process_entry_def(self, entry: Entry):
        """
        预定义一个 rpc 服务
        :param entry:
        :return:
        """
        self.enter_entry(entry.name)
        # process arg list
        args_dict = type_def.Dict(True)
        for arg in entry.args:
            args_dict.add_field(arg.name, arg.arg_type)

        self.enter_entry("Arg")
        # 生成参数的定义, 作为函数的统一入口
        self.def_class(self.get_entry_name(), args_dict, entry.description)
        self.exit_entry()
        self.append_with()

        # 返回值定义
        self.process_return(entry)
        self.exit_entry()

    def process_entry(self, entry: Entry):
        """
        处理一个 rpc 服务
        :param entry:
        :return:
        """
        self.enter_entry(entry.name)
        # 接口定义
        with self.with_ident():
            self.append_with(
                "def %s(self, arg: %s, option: typing.Union[RPCOption, None] = None) -> %s:" %
                (entry.name, self.get_entry_name("Arg"), self.get_entry_name("Result"))
            )

            with self.with_ident():
                self.process_service_body(entry)

        self.exit_entry()
        self.append_with()

    def process_service_body(self, entry: Entry):
        """
        生成 service 的实现定义，默认实现为客户端的，服务端的实现由子类 GrpcPyServerDef 完成
        :param entry:
        :return:
        """
        self.append_with("context = self.get_context(\"%s\")" % entry.name)
        self.append_with("with TraceContext(context):")
        with self.with_ident():
            self.append_with("return_result = context.call(arg, option=option)")
            self.append_with("result = %s()" % self.get_entry_name("Result"))
            self.append_with("result.from_pb2(return_result)")
            self.append_with("return result")

    def process_args_def(self, args: typing.List[Arg]):
        """
        为参数的复杂参数进行类型定义
        :param args:
        :return:
        """
        for arg in args:
            # 跳过基础类型
            if type_def.is_list(arg.arg_type):
                elem_type: typing.Union[type_def.List, None] = None
                if hasattr(arg.arg_type, "get_elem") and callable(arg.arg_type.get_elem):
                    elem_type = arg.arg_type.get_elem()

                if type_def.is_dict(elem_type):  # 先不处理嵌套的 list
                    self.enter_entry(arg.name)
                    self.def_class(self.get_entry_name(), elem_type)
                    self.append_with()
                    self.exit_entry()
            elif type_def.is_dict(arg.arg_type):
                self.enter_entry(arg.name)
                self.def_class(self.get_entry_name(), arg.arg_type, arg.description)
                self.append_with()
                self.exit_entry()

    def process_args(self, args: typing.List[Arg]):
        """
        为函数的参数进行签名
        :param args:
        :return:
        """
        for arg in args:
            self.process_arg(arg)

    def def_class(self, class_name: str, dict_type, description: str = ""):
        """
        生成一个 class 定义, 所有的 Class 定义都会保存到 header 定义中
        :param class_name:
        :param dict_type:
        :param description:
        :return:
        """
        dict_type: type_def.Dict = dict_type
        # 先生成嵌套类型
        args_dict = dict_type.get_elem_info()
        args = [Arg(name, arg_type, arg_type.default_value, arg_type.description, arg_type.required)
                for name, arg_type in args_dict.items()]
        self.process_args_def(args)

        # 再生成当前类型
        self.append_with("class %s(RPCDict):" % class_name)
        with self.with_ident():

            # 添加入口注释
            descriptions = description.split("\n")
            if descriptions:
                self.append_with("\"\"\"")
            for line in description.split("\n"):
                line = line.strip()
                if line:
                    self.append_with(line)

            # 遍历参数，生成 Attribute 注释
            self.append_with()
            if args:
                self.append_with("Properties:")
            with self.with_ident():
                for arg in args:
                    if arg.description is None:
                        print(arg)
                    arg_desc = arg.description.split("\n")
                    if arg_desc:
                        first_line = arg_desc[0]
                        rest_list = arg_desc[1:]
                        self.append_with("%s: %s" % (arg.name, first_line))
                        with self.with_ident():
                            for arg_line in rest_list:
                                self.append_with(arg_line)

            if descriptions:
                self.append_with("\"\"\"")

            # 处理参数的嵌套类型定义
            self.append_with("def __init__(")
            with self.with_ident():
                self.append_with("self,")
                self.process_args(args)
            self.append_with("):")
            with self.with_ident():
                self.process_class_body(args)

        self.append_with()
        self.process_pb2_convert(args)

        self.append_with()

    def process_pb2_convert(self, args: typing.List[Arg]):
        """
        为生成的类型提供转与 Grpc 类型互转的能力,
        以及从 dict 进行转换的能力, 方便旧有代码的升级
        :param args:
        :return:
        """

        with self.with_ident():
            if len(args) == 0:
                self.append_with("def convert_pb2(self):")
                with self.with_ident():
                    self.append_with("return None")
                self.append_with()
                self.append_with("def from_pb2(self, context):")
                with self.with_ident():
                    self.append_with("return None")
                self.append_with()
                self.append_with("def from_dict(self, _d):")
                with self.with_ident():
                    self.append_with("return None")
                return

            # 类型判断加 or 是为了去掉警告
            if self.need_service:
                self.append_with("def convert_pb2(self):")
                with self.with_ident():
                    self.append_with("result = pb2.%s()" % self.get_pb_entry_name())
                    for arg in args:
                        if type_def.is_base_type(arg.arg_type):
                            self.append_with("result.%s = self.%s" % (arg.name, arg.name))
                        elif type_def.is_list(arg.arg_type):
                            elem_type: typing.Union[type_def.List, None] = None
                            if hasattr(arg.arg_type, "get_elem") and callable(arg.arg_type.get_elem):
                                elem_type = arg.arg_type.get_elem()

                            if elem_type is None:
                                raise ValueError(f"the elem_type of {arg.arg_type} is None")

                            if type_def.is_base_type(elem_type):
                                item_name = "item"
                            elif type_def.is_dict(elem_type):
                                item_name = "item.convert_pb2()"
                            self.append_with("for item in self.%s:" % arg.name)
                            with self.with_ident():
                                self.append_with("result.%s.append(%s)" % (arg.name, item_name))
                        elif type_def.is_dict(arg.arg_type):
                            self.append_with("result.%s.MergeFrom(self.%s.convert_pb2())" % (arg.name, arg.name))

                    self.append_with("return result")

            def from_func(
                    name: str,
                    action_start: str = "",
                    action_end: str = "",
                    default_value=None,
                    inject_addition: bool = False
            ):
                self.append_with()
                self.append_with("def %s(self, context, allow_addition: bool = False):" % name)
                with self.with_ident():

                    if default_value is not None:
                        self.append_with("if context is None:")
                        with self.with_ident():
                            self.append_with(f"context = {default_value}")

                    if inject_addition:
                        self.append_with()
                        self.append_with("if allow_addition:")
                        with self.with_ident():
                            self.append_with("# inject all items from dict to entity")
                            self.append_with("for k, v in context.items():")
                            with self.with_ident():
                                # 增加跳过复杂类型的处理
                                self.append_with("if hasattr(self, k):")
                                with self.with_ident():
                                    self.append_with("continue")
                                self.append_with("setattr(self, k, v)")
                            self.append_with()

                    for f_arg in args:
                        if type_def.is_base_type(f_arg.arg_type) or type_def.is_enum(f_arg.arg_type):
                            # 处理基础类型
                            value_str = self.value_str(action_start, action_end, f_arg)
                            self.append_with(f"self.{f_arg.name} = {value_str}")
                        elif type_def.is_list(f_arg.arg_type):
                            # 处理列表类型
                            self.append_with("self.%s = []" % f_arg.name)
                            f_elem_type: typing.Union[type_def.List, None] = None
                            if hasattr(f_arg.arg_type, "get_elem") and callable(f_arg.arg_type.get_elem):
                                f_elem_type = f_arg.arg_type.get_elem()

                            if f_elem_type is None:
                                raise ValueError(f"elem of arg_type {f_arg.arg_type} is None")

                            if type_def.is_base_type(f_elem_type):
                                self.append_with("for item in context.%s%s%s or []:" % (action_start, f_arg.name, action_end))
                                with self.with_ident():
                                    self.append_with("self.%s.append(item)" % f_arg.name)
                            elif type_def.is_dict(f_elem_type):
                                self.append_with("for item in context.%s%s%s or []:" % (action_start, f_arg.name, action_end))
                                self.enter_entry(f_arg.name)
                                with self.with_ident():
                                    self.append_with("new_item = %s()" % self.get_entry_name())
                                    self.append_with("new_item.%s(item)" % name)
                                    self.append_with("self.%s.append(new_item)" % f_arg.name)
                                self.exit_entry()
                        elif type_def.is_dict(f_arg.arg_type):
                            # 处理字典类型
                            self.append_with("self.%s.%s(context.%s%s%s)" %
                                             (f_arg.name, name, action_start, f_arg.name, action_end))

            if self.need_service:
                from_func("from_pb2")
            from_func("from_dict", "get(\"", "\")", "{}", True)

    def value_str(self, action_start: str, action_end: str, f_arg: Arg) -> str:
        result = []
        if f_arg.arg_type.default_value is not None:
            result.append("self.choose_default(")
            with self.with_ident():
                result.append(self.str_with_ident(f"context.{action_start}{f_arg.name}{action_end},"))
                result.append(self.str_with_ident(f"{mapping.get_default(f_arg.arg_type)})"))
        else:
            result.append(f"context.{action_start}{f_arg.name}{action_end}")

        return "\n".join(result)

    def process_class_body(self, args: typing.List[Arg]):
        if len(args) == 0:
            self.append_with("pass")
            return

        for arg in args:
            if type_def.is_base_type(arg.arg_type) or type_def.is_enum(arg.arg_type):
                self.append_with("self.%s = %s" % (arg.name, arg.name))
            elif type_def.is_list(arg.arg_type):
                self.append_with("self.%s = %s or []" % (arg.name, arg.name))
            elif type_def.is_dict(arg.arg_type):
                self.enter_entry(arg.name)
                self.append_with("self.%s = %s or %s()" % (arg.name, arg.name, self.get_entry_name()))
                self.exit_entry()

    def process_return(self, entry: Entry):
        """
        处理 Entry 的返回值类型
        :param entry:
        :return:
        """
        if type_def.is_base_type(entry.result):
            self.enter_entry("Result")
            r = type_def.Dict(True)
            r.add_field("data", entry.result)
            self.def_class(self.get_entry_name(), r)
            self.exit_entry()
        elif type_def.is_list(entry.result):
            elem_type = entry.result.get_elem()
            if type_def.is_base_type(elem_type):
                self.append_with(
                    "class %s(%s):" % (self.get_entry_name("ResultElement"), mapping.mapping_revert(elem_type))
                )
                self.append_with("pass")
            elif isinstance(elem_type, type_def.Dict):
                self.def_class(self.get_entry_name("ResultElement"), elem_type)

            self.append_with(
                "class %s(typing.List[%s]):" % (self.get_entry_name("Result"), self.get_entry_name("ResultElement")))
            with self.with_ident():
                self.append_with("pass")
        elif type_def.is_dict(entry.result):
            self.enter_entry("Result")
            self.def_class(self.get_entry_name(), entry.result)
            self.exit_entry()

        self.append_with()

    def process_arg(self, arg: Arg):
        """
        处理单个参数
        :param arg:
        :return:
        """
        name = arg.name
        arg_type = arg.arg_type

        mapping_arg_type = mapping.mapping_revert(arg_type)
        default_value = mapping.get_default(arg_type)

        # 处理基础类型
        if type_def.is_base_type(arg_type):
            conf = "%s: %s = %s," % (name, mapping_arg_type, default_value)
            self.append_with(conf)
        elif type_def.is_enum(arg_type):
            # 暂时将 Enum 处理为普通类型
            enum_arg_type: type_def.RpcType = getattr(arg_type, "rpc_type", None)
            enum_mapping_arg_type = mapping.mapping_revert(enum_arg_type)
            enum_default_value = mapping.get_default(enum_arg_type)

            conf = f"%s: %s = %s," % (name, enum_mapping_arg_type, enum_default_value)
            self.append_with(conf)
        # 处理列表
        elif type_def.is_list(arg_type):
            # 生成列表元素的信息
            elem_type: typing.Union[type_def.List, None] = None
            if hasattr(arg_type, "get_elem") and callable(arg_type.get_elem):
                elem_type = arg_type.get_elem()

            if elem_type is None:
                raise ValueError(f"elem of arg_type {arg_type} is None")

            elem_type_name = mapping.mapping_revert(elem_type)
            if not type_def.is_base_type(elem_type):
                self.enter_entry(name)
                elem_type_name = self.get_entry_name()
                self.exit_entry()

            self.append_with("%s: typing.List[%s] = None," % (arg.name, elem_type_name))

        elif type_def.is_dict(arg_type):
            self.enter_entry(name)
            elem_type_name = self.get_entry_name()
            self.exit_entry()
            self.append_with("%s: %s = None," % (name, elem_type_name))

    def enter_entry(self, name: str):
        """
        进入一个类型定义，没生成一个嵌套类型，都会进入一次, 用于生成嵌套类型的名称
        :param name:
        :return:
        """
        self.curr_entry_name.append(pretty_name(name))

    def exit_entry(self):
        if self.curr_entry_name:
            self.curr_entry_name.pop()

    def get_entry_name(self, name: str = "") -> str:
        return "".join(self.curr_entry_name) + upper_first_character(name)

    def get_pb_entry_name(self) -> str:
        if len(self.curr_entry_name) != 0:
            # module、method、type, type 可能是 Arg 或 Result, 当是 Result 时，需要添加一层 Data
            module = self.meta_data.name
            method = self.curr_entry_name[0]
            method_type = self.curr_entry_name[1]
            # if method_type == "Result":
            #     method_type = method_type + ".Data"
            method = "%s%s%s" % (module, method, method_type)
            return ".".join([method] + self.curr_entry_name[2:])

        return self.meta_data.name
