import sys
import os
from .. import config
from .analyser import DirScanner, ModuleScanner, Analyser
from .codegen.config import cfg_generator
from .codegen.service import service_generator
from ..framework.util.git import Git


class Worker(object):
    """
    用于生成新的 RPC 信息，需要指定生成文件的输出目录，对应的 rpc server 及 client 都会
    生成到指定的目录
    """
    def __init__(self):
        """
        初始化 RPC 代码生成器
        :param config.from_current_project: 从引用了当前库的项目开始检查
        :param config.source_project_path: 如果不是从当前库开始, 则指定需要升级 rpc 的项目路径 需要绝对路径,
        :param config.server_output_path: RPC 服务端代码的输出地址, 一般与该项目保存在一起, 要绝对路径
        :param config.client_output_path: RPC 客户端代码的输出地址, 需生成的 client 端代码，保存到统一的 client 项目中, 要绝对路径
        """
        self.from_current_project = config.from_current_project
        self.source_project_path = config.source_project_path
        self.server_output_path = config.server_output_path
        self.client_output_path = config.client_output_path
        self.analyse = Analyser()
        self.meta_list = []
        self.generators = []

        if not config.from_current_project and not config.source_project_path:
            raise Exception("在没有配置从当前目录进行检查时，需要配置需要检查的项目目录。")

        if not config.server_output_path and not config.client_output_path:
            raise Exception("没有配置 RPC 代码的输出目录")

    def start(self):
        """
        启动 RPC 检查器
        :return:
        """
        # 获取 rpc 类型
        (rpc_classes, impl_classes) = self.gather_classes()

        # 过滤所有不在目标项目中的类型
        # if config.outside_server:
        #     rpc_classes = [rpc for rpc in rpc_classes if rpc.__module__.startswith(config.source_project_name)]
        #     impl_classes = [rpc for rpc in impl_classes if rpc.__module__.startswith(config.source_project_name)]

        print("-" * 30)
        print("got rpc class: ")
        for r in rpc_classes:
            print(" " * 4, r)
        print("and rpc impl: ")
        for i in impl_classes:
            print(" " * 4, i)
        print("-" * 30)

        # 解析 rpc 元数据
        meta_list = self.analyse.analyse(rpc_classes, impl_classes, config.need_impl)
        self.meta_list = meta_list

        # 生成 rpc 相关代码
        configs = []
        for m in self.meta_list:
            # 生成 接口配置信息
            cfg_config = cfg_generator(m)
            cfg_config.gen_conf()
            configs.append(cfg_config)

        # 生成实际配置文件及代码文件
        service = service_generator(configs)
        service.generate()
        self.generators.append(service)

    def gather_classes(self):
        """
        解析出所有符合 CommonBase 条件的 Class
        :return:
        """
        if self.from_current_project:
            return self.start_from_current()
        else:
            return self.start_from_source()

    @staticmethod
    def start_from_current():
        """
        从当前的运行环境进行检查
        :return:
        """
        scanner = ModuleScanner()
        scanner.gather()
        return scanner.types, scanner.impls

    def start_from_source(self):
        """
        从指定的目录开始检查, 如果配置的是独立的服务端，则这里会先尝试把代码拉取到指定目录
        :return:
        """
        if config.outside_server:
            # 增加一个注意的点，如果是外部项目，需要为其添加其项目路径到 sys
            git = Git(config.outside_server_path)
            git.ch_to()
            # 保存待生成服务的名称, 用于后续生成 path 目录
            git.submodule_add(config.source_project_path, config.source_project_name)
            git.submodule_update(True, True, config.source_project_name)

            sys.path.append(os.path.join("./", config.source_project_name))

            scanner = DirScanner(config.outside_server_path)
            info = scanner.gather()
            git.ch_back()
            return info
        else:
            scanner = DirScanner(self.source_project_path)
            return scanner.gather()
