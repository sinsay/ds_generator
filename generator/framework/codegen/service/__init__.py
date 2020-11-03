import typing
from ..base import ConfigBase
from .base import Generator
from .grpc_service import GRPCGenerator


def service_generator(configs: typing.List[ConfigBase]):
    """
    获取创建 Service 的生成器, 作为对外接口，可用于随时替换具体实现
    config.source_project_path: 项目所在目录
    config.client_output_path: 客户端所在目录
    :param configs:
    :return:
    """
    return GRPCGenerator(configs)
