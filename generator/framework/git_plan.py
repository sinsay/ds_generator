"""
RPC 生成器入口，包括整个 RPC 生成及更新的计划管理，整个计划过程为

1. 接收生成 rpc 的相关信息
    1. 目标 service 的信息，包括 service 的仓库地址、分支等信息
    2. rpc-client 的目录信息，会将生成的 rpc
2. clone 目标 service 的代码到本机的目录
3. clone rpc-client 的代码到本机的目录
4. 使用 rpc-framework 生成对应的代码调用方式提交到该仓库
    1. 生成的 server 信息提交到 service 仓库中
    2. 生成的 client 信息提交到 rpc-client 中

最终结果
目标 service 在启动时，会在指定的端口启动 rpc 服务
需要使用 rpc 服务的其他 service, 引入 rpc-client 项目，使用其中的 rpc 子类进行调用
"""

from os import path
from .worker import Worker
from generator.framework.util.git import Git


class PlanConfig(object):
    """
    生成 RPC 代码所需的参数信息
    """
    def __init__(self, service_repo: str, service_repo_branch: str, service_repo_name: str,
                 rpc_client_repo: str, rpc_client_repo_branch: str):
        """
        :param service_repo: 需要生成 rpc 服务的目标仓库
        :param service_repo_branch:  需要生成 rpc 服务的目标仓库的指定分支
        :param service_repo_name: rpc 服务的名称，用于生成临时目录
        :param rpc_client_repo:  用于提交 rpc 客户端接口的 仓库
        :param rpc_client_repo_branch: 提交到 rpc 客户端接口仓库的指定分支
        """
        self.service_repo = service_repo
        self.service_repo_branch = service_repo_branch
        self.service_repo_name = service_repo_name
        self.rpc_client_repo = rpc_client_repo
        self.rpc_client_repo_branch = rpc_client_repo_branch


class RpcGitPlan(object):
    """
    Rpc 代码生成计划管理器
    """
    def __init__(self, config: PlanConfig):
        self.config = config

    def execute(self):
        # 创建临时 git 目录
        tmp_dir = "~/rpc_tmp"
        git = Git(tmp_dir)
        # clone 指定 service 的代码
        git.clone(self.config.service_repo, self.config.service_repo_name)
        git.ch_to(self.config.service_repo_name)
        git.checkout(self.config.service_repo_branch)
        git.ch_back()

        # clone rpc-client 的代码
        git.clone(self.config.rpc_client_repo, "rpc_client")
        git.ch_to("rpc_client")
        git.checkout(self.config.rpc_client_repo_branch)
        git.ch_back()

        # 使用 worker 生成 rpc 相关代码
        service_dir = git.next_dir(self.config.service_repo_name)
        worker = Worker(from_current_project=False,
                        source_project_path=service_dir,  # 需要升级的项目目录
                        server_output_path="",  # 生成的 server 端代码，默认保存在该项目中
                        client_output_path=path.join(tmp_dir, "rpc_client")  # 生成的 client 端代码，应该存到统一个 client 仓库中
                        )
        worker.start()
