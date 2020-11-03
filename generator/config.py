from typing import List

# 将作为 rpc 子库的 runtime git 地址
runtime_repo: str = "ssh://git@192.168.10.174:10022/rpc/rpc_runtime.git"

# master 分支默认会放最新的稳定代码
runtime_repo_branch: str = "master"

# 以下配置信息，在程序执行时将从 command line args 获取

# from_current_project 指示是否从当前项目开始扫描
from_current_project: bool = False

# source_project_path 是需要扫描代码的目录
source_project_path: str = ""

# source_project_name 是将要将要引入 rpc 的服务名
source_project_name: str = ""

# server_output_path 是服务端代码的输出目录
server_output_path: List[str] = []

# client_output_path 是客户端代码的输出目录
client_output_path: str = ""

# server_code 指示要不要输出服务端的代码，这个标识只用于控制是否在
# 原项目生成 RPC 的服务端代码，对于 Outside Server 类型服务端代码是必须要生成的
server_code: bool = True

# need_impl 指示是否需要生成 RPC 的实现类,
# 只有服务端才需要生成实现类，所以该选项只对服务端有效
need_impl: bool = True

# 该选项为 True 时，生成的服务端将作为独立的项目，并将原本依赖的
# http 项目作为子模块引入
outside_server: bool = False

# 当将服务端作为独立项目时，用于保存 rpc 服务端代码的地址
outside_server_path: str = ""

# 独立项目的名称
outside_server_name: str = ""
