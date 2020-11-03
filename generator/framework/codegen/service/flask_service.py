import os
import re
import os.path as path
import subprocess
import typing

from .... import config
from ...util.cfg_generator import CfgGenerator
from .base import Generator, ServerDirConfig, ClientDirConfig, ConfigBase
from .grpc_py_def import GrpcPyDef
from .grpc_server_def import GrpcPyServerDef


class FlaskGenerator(Generator):
    """
    代码生成的 Flask 实现
    具体的生成逻辑为:
    1. 设定需要检索的目录，该目录输出代码的路径, 该目录元素的具体生成器
    2. 搜索所有继承了指定目录的包，按照配置的输出路径输出生成的代码
    """

    def generate(self):
        """
        根据定义生成 Flask 的 Resource
        """
        # 迭代每个 config, 每个 config 代表一个服务
        for cfg in self.configs:
            # 生成服务端定义
            # if config.server_code:
            py_def = GrpcPyServerDef(cfg.meta_data)
            gen_mid_file(cfg, server_dir_config)
            gen_class_def(cfg, py_def, server_dir_config)

