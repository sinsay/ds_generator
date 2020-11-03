from os import path
from typing import List

from ..common import MetaData, type_def
from .codegen.service.base import ensure_dir
from .codegen.service.flask_def import FlaskDef, __test_meta_define__
from .codegen.service.grpc_service import GrpcPyDef
from .enum_worker import EnumWorker
from .analyser.module_scanner import EnumWithVar
from .util.text import split_by_upper_character


class WebWorker(object):
    """
    用于生成新的 RPC 信息，需要指定生成文件的输出目录，对应的 rpc server 及 client 都会
    生成到指定的目录
    """
    def __init__(
            self,
            meta_list: List[MetaData],
            output_path: str,
            runtime_path: str = "runtime",
            api_path: str = "src",
            enums: List[EnumWithVar] = None,
            enum_gen_path: str = "enum.py"
    ):
        """
        使用得到的 Meta 列表，构建 Flask 接口模板, 按照指定的目录地址构造 Api 目录
        """
        self.meta_list = meta_list
        self.output_path = output_path
        self.runtime_path = runtime_path
        self.api_path = api_path
        self.enums = enums or []
        self.enum_gen_path = enum_gen_path

        # 检查 Meta 列表，查找所有局部定义的 Enum
        self.find_enum(self.meta_list.copy())

    def find_enum(self, metas: List[MetaData]):
        if len(metas) == 0:
            return

        m = metas.pop()
        for entry in m.entries:
            for arg in entry.args:
                self.check_rpc_type(arg.arg_type)

            self.check_rpc_type(entry.result)

        self.find_enum(metas)

    def check_rpc_type(self, r):
        if type_def.is_list(r):
            elem = r.get_elem()
            self.check_rpc_type(elem)
        elif type_def.is_dict(r):
            for k, v in r.get_elem_info().items():
                self.check_rpc_type(v)
        elif type_def.is_enum(r):
            self.check_enum(r)

    def check_enum(self, r):
        if type_def.is_enum(r):
            self.enums.append(EnumWithVar("", "", r))

    def start(self) -> bool:
        """
        开始构建
        """
        res_output = path.join(self.output_path, ".")
        arg_output = path.join(self.output_path, ".")

        ensure_dir(res_output, is_package=True)
        ensure_dir(arg_output, is_package=True)

        with open(path.join(res_output, "./api_reg.py"), "w") as init_file:
            init_str_list = []
            for meta in self.meta_list:
                # 生成参数定义
                a = GrpcPyDef(meta, need_servicer=False)
                for entry in meta.entries:
                    a.process_entry_def(entry)
                    a.append_with()

                arg_def = "\n".join([
                    "import typing",
                    f"from {self.runtime_path}.runtime.common import RPCDict",
                    "",
                    "",
                    a.cfg_string()
                ])

                # 生成服务定义
                f = FlaskDef(
                    meta,
                    # f".{meta_file_name(meta, '_def')}",
                    f".{split_by_upper_character(meta.name, '_')}_def".lower(),
                    runtime_path=self.runtime_path,
                    api_path=self.api_path
                )
                f.gen_conf()
                res_conf = "\n\n".join([f.get_header_conf(), f.get_conf()])

                # save resource and arg define to api path
                self.save(
                    meta_file_name(meta, suffix="_def.py", base_path=arg_output, need_ensure=True),
                    arg_def)
                self.save(
                    meta_file_name(meta, suffix=".py", base_path=res_output, need_ensure=True),
                    res_conf)

                init_str_list.append(f"from .{meta_file_name(meta).replace('/', '.')} import *\n")

            init_file.write("".join(sorted(init_str_list)))
            init_file.flush()
            init_file.close()

        enum_worker = EnumWorker(
            res_output, self.runtime_path, self.api_path, gen_path=self.enum_gen_path, enums=self.enums
        )
        enum_worker.start()
        return True

    @staticmethod
    def save(file_path: str, content: str):
        with open(file_path, "w") as f:
            f.write(content)


def meta_file_name(meta: MetaData, suffix: str = "", base_path: str = "", need_ensure: bool = False) -> str:
    name: str = meta.name
    key = "define.api"
    skip_len = len(key) + 1
    index = meta.service_type.__module__.find(key)
    if index != -1:
        name = split_by_upper_character(name, "_")
        m_name_list = meta.service_type.__module__[index + skip_len:].split(".")
        m_name = path.join(base_path, m_name_list[0])
        if need_ensure:
            ensure_dir(m_name)
        for m in m_name_list[1:]:
            m_name = path.join(m_name, m)
            if need_ensure:
                ensure_dir(m_name)
        name = path.join(m_name, name)

    return f"{name.lower()}{suffix}"


def __test__():
    meta = __test_meta_define__()
    worker = WebWorker([meta], "/tmp/api_gen", runtime_path="runtime")
    worker.start()
