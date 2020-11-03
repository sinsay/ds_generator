from enum import Enum

from .framework.flask_worker import WebWorker
from .framework.model_worker import ModelWorker
from .framework.meta_worker import MetaWorker


class WorkerType(Enum):
    Api = 1
    Model = 2


class WorkerCombiner(object):
    """
    该类型允许配置目录定义，然后根据目录定义为指定的目录使用指定的 Worker 生成
    代码
    """
    def __init__(
            self,
            project_src_path: str,
            api_output: str,
            model_output: str,
            runtime_path: str,
            api_path: str,
            model_filter_str: str,
            enum_gen_path: str
    ):
        """
        :param project_src_path: 是需要扫描项目的路径
        :param api_output: 是扫描得到的接口输出路径
        :param model_output: 是扫描得到的 ORM 输出路径
        :param runtime_path: runtime 的包路径
        :param api_path: flask api 的路径
        """
        self.project_src_path = project_src_path
        self.api_output = api_output
        self.model_output = model_output
        self.runtime_path = runtime_path
        self.api_path = api_path
        self.enum_gen_path = enum_gen_path

        self.meta_worker = MetaWorker(self.project_src_path)
        self.meta_list = self.meta_worker.start()

        self.model_worker = ModelWorker(self.model_output, self.api_path, model_filter_str)
        self.web_worker = WebWorker(
            self.meta_list,
            self.api_output,
            self.runtime_path,
            self.api_path,
            enum_gen_path=self.enum_gen_path)

    def start(self):
        """
        开始根据配置生成代码
        """
        print("开始构建 Api 服务...")
        self.web_worker.start()

        print("开始构建 ORM 目录...")
        self.model_worker.start()
