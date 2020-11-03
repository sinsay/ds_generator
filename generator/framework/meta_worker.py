from typing import List
from ..common import MetaData
from .analyser import DirScanner, Analyser


class MetaWorker(object):
    """
    用于生成新的 RPC 信息，需要指定生成文件的输出目录，对应的 rpc server 及 client 都会
    生成到指定的目录
    """
    def __init__(self, source_project_path: str = None):
        """
        初始化 RPC 代码解析器，提供 server_source_path, 该 Worker 会解析项目中的所有 Class,
        最终得到所以继承了 RPC Base 的类型
        :param source_project_path: 需要扫描源码项目路径, 需要绝对路径
        """
        self.source_project_path = source_project_path
        self.analyse = Analyser()

    def start(self) -> List[MetaData]:
        """
        启动 RPC 检查器
        :return:
        """
        # 获取 rpc 类型
        (rpc_classes, impl_classes) = self.start_from_source()
        # 解析 rpc 元数据
        return self.analyse.analyse(rpc_classes, impl_classes, need_impl=False)

    def start_from_source(self):
        """
        从指定的目录开始检查
        :return:
        """
        scanner = DirScanner(self.source_project_path)
        return scanner.gather()
