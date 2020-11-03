import typing
import os.path as path

from .... import config
from ...util.fs import mkdir_without_exception
from ...codegen.base import ConfigBase


class Generator(object):
    """
    负责与第三方 RPC 框架进行对接的类型
    用于生成 Service 的 Server 跟 Client 代码,
    最终按照预定义的目录格式，将文件保存到指定的位置
    """

    def __init__(self, configs: typing.List[ConfigBase]):
        """
        生成 cfg 定义的服务信息到 output 定义的位置
        :param configs:
        """
        self.configs = configs
        self.target_path = config.server_output_path
        self.client_path = config.client_output_path

    def generate(self):
        """
        使用 generate_config 生成的配置文件，调用第三方引擎生成其编码及解码器
        :return:
        """
        raise NotImplemented()


class ClientDirConfig(object):
    """
    Rpc client 的目录结构,
    所有生成的目录，都在自身的模块名下
    """
    def __init__(self, base_path, client_path: str):
        """
        client 的 root 是 base_dir 之外的 rpc-client 的地址
        :param base_path:
        """
        self.base_dir = path.abspath(base_path)
        self.client_path = path.abspath(client_path)
        # 接口生成目录
        self.root = self.client_path

        # client 的代码默认放在 src 目录下
        root = "./src"
        # 第三方工具生成代码的目录, 如 proto buf 的配置
        self.mid_file = path.join(self.client_path, root, "./mid_file")
        # 编码及解码信息的目录
        self.encode = path.join(self.client_path, root, "./encode")

        self.impl = path.join(self.client_path, root, "./impl")

        # 通用 rpc 运行时的目录
        self.runtime = path.join(self.client_path, "./runtime")

    def ensure_dir(self):
        """
        初始化 rpc 目录
        :return:
        """
        ensure_dir(self.root, self.mid_file, self.encode, self.impl)
        # ensure_dir(self.runtime, is_package=False)

    def join(self, *sub_paths: str):
        """
        返回 DirConfig.root 跟 path 路径的拼接结果
        :param sub_paths:
        :return:
        """
        return path.join(self.root, *sub_paths)


def ensure_dir(*dirs: str, is_package: bool = True):
    """
    确认目录结构的正确性
    :param dirs:
    :param is_package:
    :return:
    """
    for d in dirs:
        mkdir_without_exception(d)
        if is_package and not path.exists(path.join(d, "./__init__.py")):
            open(path.join(d, "./__init__.py"), "w")


class ServerDirConfig(ClientDirConfig):
    """
    rpc server 目录结构,
    跟 client 唯一的区别是多了一层 rpc 目录
    """
    def __init__(self, base_path: str):
        ClientDirConfig.__init__(self, base_path, "")
        self.root = path.join(self.base_dir, "./rpc")

        # 第三方工具生成代码的目录, 如 proto buf 的配置
        self.mid_file = path.join(self.root, "./mid_file")
        # 编码及解码信息的目录
        self.encode = path.join(self.root, "./encode")
        # 具体 grpc 服务的目录
        self.impl = path.join(self.root, "./impl")
        # 通用 rpc 运行时的目录
        self.runtime = path.join(self.root, "./runtime")

    def ensure_dir(self):
        """
        初始化 rpc 目录
        :return:
        """
        # 具体 grpc 服务的目录
        # ClientDirConfig.ensure_dir(self)
        # 构建 server 自己的目录
        ensure_dir(self.mid_file, self.encode, self.impl)
        # ensure_dir(self.runtime, is_package=False)
