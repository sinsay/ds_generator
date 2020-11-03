from os import path
from typing import List

from .codegen.service.base import ensure_dir
from .codegen.service.enum_def import EnumDef
from .codegen.service.enum_py_def import EnumPyDef
from .analyser.module_scanner import ModuleScanner, EnumWithVar


class EnumWorker(object):
    """
    生成 枚举类型的服务及定义
    """
    def __init__(
            self,
            output_path: str,
            runtime_path: str = "runtime",
            api_path: str = "src",
            gen_path: str = "gen",
            enums: List[EnumWithVar] = None,
            filter_str: str = ""
    ):
        """
        创建 Enum 服务接口
        """
        # 生成 Enum 服务的路径
        self.output_path = output_path
        self.runtime_path = runtime_path
        self.api_path = api_path
        # 生成 Enum 类型定义的路径
        self.gen_path = gen_path
        self.enums = enums or []
        self.filter_str = filter_str

    def start(self) -> bool:
        """
        开始构建
        """
        res_output = path.join(self.output_path, ".")

        ensure_dir(res_output, is_package=True)

        header_str: str = ""
        enum_resource: List[str] = []

        scanner = ModuleScanner()
        enums = scanner.get_enums() + self.enums
        # 去重
        enums = self.check_enums(enums)

        enum_py_list = ["\n"]
        with open(path.join(res_output, "./api_reg.py"), "a") as init_file:
            for enum_info in sorted(enums, key=lambda e: e.enum.name.lower()):
                enum_def = EnumDef(enum_info, self.runtime_path, self.api_path)
                enum_def.gen_conf()
                res_conf = enum_def.get_conf()
                enum_resource.append(res_conf)
                if not header_str:
                    header_str = enum_def.get_header_conf()

                enum_py_def = EnumPyDef(enum_info, self.runtime_path, self.api_path)
                enum_py_def.gen_conf()
                enum_py_list.append(enum_py_def.get_conf())

            # 找到 .define. 并用相同的后缀路径来保存创建的枚举服务
            # save resource and arg define to api path
            self.save(
                path.join(res_output, "ss_enum.py"),
                "\n\n".join([header_str] + enum_resource)
            )
            init_file.write(f"from .ss_enum import *\n")

        gen_path = self.gen_path
        self.save(gen_path, "\n".join(enum_py_list))
        return True

    @staticmethod
    def check_enums(enums: List[EnumWithVar]):
        enums = list(set(enums))
        name_dict: dict = {}
        for e in enums:
            name_dict[e.enum.name] = name_dict.get(e.enum.name, 0) + 1

        err = []
        for e, c in name_dict.items():
            if c > 1:
                err.append(e)

        if len(err) > 0:
            raise AssertionError(f"存在重复定义的枚举类型: {''.join(err)}")

        return enums

    @staticmethod
    def save(file_path: str, content: str):
        with open(file_path, "w") as f:
            f.write(content)


def __test__():
    from ..common import fields
    es = [
        EnumWithVar("E1", "hello", fields.Enum(dict(
            OK=fields.Integer(description="Ok Enum", default_value=200),
            FAIL=fields.Integer(description="Fail Enum", default_value=500)
        ), description="测试枚举类型", default_value=200)),
        EnumWithVar("E2", "world", fields.Enum(dict(
            GET=fields.String(description="GET", default_value="GET"),
            POST=fields.String(description="POST", default_value="POST")
        ), description="HTTP 请求枚举"))
    ]
    worker = EnumWorker("/tmp/hello_es", enums=es)
    worker.start()
