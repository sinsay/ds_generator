from ....common import MetaData
from ..base import ConfigBase
from .grpc_config import GrpcConfig


def cfg_generator(meta_data: MetaData) -> ConfigBase:
    """
    获取配置生成器
    :param meta_data:
    :return:
    """
    return GrpcConfig(meta_data)
