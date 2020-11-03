import typing

from ...common import MetaData


class ConfigBase(object):
    def __init__(self, meta_data: typing.Union[MetaData, None]):
        self.meta_data = meta_data

    def gen_conf(self):
        """生成配置文件"""
        raise NotImplemented("未实现该接口")

    def get_conf(self) -> str:
        """
        获取生成好的配置文件
        :return:
        """
        raise NotImplemented("未实现该接口")

    def get_file_name(self) -> str:
        """
        获取该配置文件使用的文件名
        :return:
        """
        raise NotImplemented("未实现该接口")
