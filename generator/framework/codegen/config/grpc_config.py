from ....common import MetaData, Entry, Arg, type_def
from ...util.text import upper_first_character, pretty_name
from ...util.cfg_generator import CfgGenerator
from ...codegen.grpc_py_mapping import mapping
from ..base import ConfigBase


class GrpcConfig(ConfigBase, CfgGenerator):
    """
    根据 MetaData 生成 gRPC 的的配置文件
    """

    def __init__(self, meta_data: MetaData):
        ConfigBase.__init__(self, meta_data)
        CfgGenerator.__init__(self)

        # self.meta_data = meta_data
        # 将生成的文件名
        self.file_name = pretty_name(self.meta_data.name)
        # 将生成的模块名
        self.module_name = pretty_name(self.meta_data.name)
        # 当前模块正在处理的服务入口名称列表
        self.curr_entry_name = [self.module_name]

    def get_file_name(self):
        """
        获取文件名
        :return:
        """
        return self.file_name

    def get_conf(self) -> str:
        return self.to_cfg_string()

    def gen_conf(self):
        """
        生成 gRPC 的配置文件文本，并保存在自身的 conf 中
        :return:
        """
        self.append_with("syntax = 'proto3';", new_line=True)
        for entry in self.meta_data.entries:
            self.process_entry(entry)

        self.process_service()

    def process_entry(self, entry: Entry):
        self.enter_entry(entry.name)
        self.append_with("message %s {" % self.get_entry_name("Arg"))
        with self.with_ident():
            for (index, arg) in enumerate(entry.args):
                self.process_arg(arg, index + 1)

        self.append_with("}", new_line=True)
        self.append_with("", new_line=True)
        self.process_return(entry)

        self.exit_entry()

    def process_return(self, entry: Entry):
        # 特殊处理 return 类型的第一层
        # 所有的 return 类型，都会将具体的返回值包装到 data 字段中
        self.append_with("message %s {" % self.get_entry_name("Result"), new_line=True)
        # self.enter_entry("Result")
        with self.with_ident():
            if type_def.is_base_type(entry.result):
                # t = type_def.Dict(True)
                # t.add_field("data", entry.result)
                conf = "%s %s = %d;" % (mapping(entry.result), "data", 1)
                self.append_with(conf)
            elif type_def.is_list(entry.result):
                # 生成列表元素的信息
                elem_type = entry.result.get_elem()
                # 简单类型直接处理
                if type_def.is_base_type(elem_type):
                    self.append_with("repeated %s %s = %d;" % (mapping(elem_type), "data", 1))
                else:
                    # 复杂类型需要递归处理
                    with self.with_ident():
                        self.process_type("Data", elem_type.get_elem(), 1)
                        self.conf.pop()  # pop last empty line
                        self.conf.pop()  # pop last field define
                        # then add the correct field define
                        self.append_with("repeated %s %s = %d;" % ("Data", "data", 1))

            elif type_def.is_dict(entry.result):
                for (new_index, (key, value)) in enumerate(entry.result.get_elem_info().items()):
                    if type_def.is_base_type(value):
                        self.append_with("%s %s = %d;" % (mapping(value), key, new_index + 1))
                    else:
                        self.process_type(key, value, new_index + 1)

        # self.exit_entry()
        self.append_with("}", new_line=True)
        self.append_with("", new_line=True)

    def process_arg(self, arg: Arg, index: int):
        """
        处理单个参数
        :param arg:
        :param index:
        :return:
        """
        self.process_type(arg.name, arg.arg_type, index)

    def process_type(self, name: str, arg_type: type_def.RpcType, index: int):
        """
        处理单个类型
        :param name
        :param arg_type:
        :param index:
        :return:
        """
        mapping_arg_type = mapping(arg_type)
        # 处理基础类型
        if type_def.is_base_type(arg_type):
            conf = "%s %s = %d;" % (mapping_arg_type, name, index)
            self.append_with(conf)
        # 处理列表
        elif type_def.is_list(arg_type) or isinstance(arg_type, type_def.List):
            # 生成列表元素的信息
            elem_type = arg_type.get_elem()
            # 简单类型直接处理
            if type_def.is_base_type(elem_type):
                self.append_with("repeated %s %s = %d;" % (mapping(elem_type), name, index))
            else:
                # 复杂类型需要递归处理
                elem_type_name = pretty_name(name)
                self.process_type(elem_type_name, arg_type.get_elem(), 1)
                self.conf.pop()  # pop last empty line
                self.conf.pop()  # pop last field define
                # then add the correct field define
                self.append_with("repeated %s %s = %d;" % (elem_type_name, name, index))

        elif type_def.is_dict(arg_type) or isinstance(arg_type, type_def.Dict):
            elem_type_name = pretty_name(name)
            self.append_with("message %s {" % elem_type_name)
            for (new_index, (key, value)) in enumerate(arg_type.get_elem_info().items()):
                with self.with_ident():
                    if type_def.is_base_type(value):
                        self.append_with("%s %s = %d;" % (mapping(value), key, new_index + 1))
                    else:
                        self.process_type(key, value, new_index + 1)

            self.append_with("}", new_line=True)
            self.append_with("%s %s = %d;" % (elem_type_name, name, index))

    def process_service(self):
        """
        :return:
        """
        self.append_with("service %s {" % self.module_name)

        with self.with_ident():
            for entry in self.meta_data.entries:
                self.enter_entry(entry.name)
                self.append_with(
                    "rpc %s (%s) returns (%s) {}" %
                    (entry.name, self.get_entry_name("Arg"), self.get_entry_name("Result"))
                )
                self.exit_entry()

        self.append_with("}")

    def enter_entry(self, name: str):
        self.curr_entry_name.append(pretty_name(name))

    def exit_entry(self):
        if self.curr_entry_name:
            self.curr_entry_name.pop()

    def get_entry_name(self, name: str) -> str:
        return "".join(self.curr_entry_name) + pretty_name(name)
