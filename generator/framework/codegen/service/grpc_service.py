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


class GRPCGenerator(Generator):
    """
    代码生成的 gRPC 实现
    具体的生成逻辑为:
    1. 创建指定的目录结构
    2. 将 GRPCConfig 生成的 proto 保存到 mid_file
    3. 调用 gen_mid_file 生成服务的定义及数据的解码编码器
    4. 引用 rpc_runtime 作为 rpc 通用库
    5. 创建 rpc 服务端及客户端信息
        1. 服务端 作为一个独立的 rpc-server 仓库
            1. 各个独立的 rpc 作为一个子库引入
        2. 客户端 作为一个独立的 rpc-client 仓库
    """

    def generate(self):
        """
        按照指定的目录结构生成具体的代码
        暂定 server 目录结构为:
        + origin_code
        + rpc
        + ---- mid_file               # temporarily dir use for generate codes
        + ---- encode                 # coding: protocol buffer
        - ---- ---- package_name1_pb2.py
        - ---- ---- package_name2_pb2_grpc.py
        + ---- impl                   # implement: grpc
        - ---- ---- package_name1.py
        - ---- ---- package_name2.py
        + ---- runtime                # runtime: common library
        - ---- package_name1.py       # entrance
        - ---- package_name2.py       # entrance


        client 的目录结构为，
        ps: client 的结构最好查看具体的 rpc-client 项目, 应该会调增变更

        + mid_file                          # temporarily dir use for generate protocol files
        + ---- service_name
        - ---- ---- package_name1.proto
        - ---- ---- package_name2.proto
        + encode                            # the coding service def generate by grpc
        + ---- service_name
        + ---- ---- package_name1_pb2.py
        + ---- ---- package_name1_pb2_grpc.py
        + ---- ---- package_name2_pb2.py
        + ---- ---- package_name2_pb2_grpc.py
        + impl
        + ---- service_name1.py
        + ---- service_name2.py
        + runtime                           # the runtime common library
        + package_name1.py                  # the rpc interface
        + package_name2.py
        :return:
        """
        for target_path in self.target_path:
            server_dir_config = ServerDirConfig(target_path)
            server_dir_config.ensure_dir()
            construct_runtime_module(server_dir_config)

            client_dir_config = ClientDirConfig(target_path, self.client_path)
            if config.client_output_path:
                client_dir_config.ensure_dir()
                construct_runtime_module(client_dir_config)

            # 迭代每个 config, 每个 config 代表一个服务
            for cfg in self.configs:
                # 生成服务端定义
                # if config.server_code:
                py_def = GrpcPyServerDef(cfg.meta_data)
                gen_mid_file(cfg, server_dir_config)
                gen_class_def(cfg, py_def, server_dir_config)

                # 生成客户端定义
                if config.client_output_path:
                    py_def = GrpcPyDef(cfg.meta_data)
                    gen_mid_file(cfg, client_dir_config)
                    gen_class_def(cfg, py_def, client_dir_config)

            gen_addition_file(self.configs, server_dir_config, client_dir_config)


def gen_addition_file(configs: typing.List[ConfigBase],
                      server_dir_config: ServerDirConfig,
                      _client_dir_config: ClientDirConfig):
    """
    用于生成全局的，附加文件,
    主要是 __init__ 文件，该文件包括了自动导入服务到 server 的逻辑，
    格式为:
    from .runtime.runtime import reg_servicer
    # project: name
    body
    # end project
    # project: name2
    body
    # end project

    每个项目生成时找到自己那部分进行替换
    :param configs:
    :param server_dir_config:
    :param _client_dir_config:
    :return:
    """
    # 生成服务端的统一服务注册文件
    # head
    cfg = CfgGenerator()
    cfg.append_with("# coding: utf8")
    cfg.append_with("# DONT TOUCH THIS FILE!")
    cfg.append_with()
    cfg.append_with("from .runtime.runtime import reg_servicer")
    cfg.append_with()

    project_reg = re.compile(r"# project: (?P<ProjectName>[^\n]+)(?P<ProjectInfo>[\s\S]+?)# end project")

    # current project info
    project_lines = []
    for c in configs:
        project_lines.append("from .%s import %sServicer, pb2_grpc as %s_pb2_grpc" %
                             (c.meta_data.name.lower(), c.meta_data.name, c.meta_data.name.lower()))
    project_lines.append("")
    for c in configs:
        project_lines.append("reg_servicer(%sServicer, %s_pb2_grpc.add_%sServicer_to_server)" %
                             (c.meta_data.name, c.meta_data.name.lower(), c.meta_data.name))

    # read if exists old __init__ file
    orig_file_content = ""
    init_path = path.join(server_dir_config.root, "__init__.py")
    if path.exists(init_path):
        orig_file_content = "".join(open(init_path, "r").readlines())

    # replace old project info if already exists
    has_old_def = False
    for (project_name, project_def) in project_reg.findall(orig_file_content):
        cfg.append_with(f"# project: {project_name}\n")
        if project_name == config.source_project_name:
            # replace old
            has_old_def = True
            cfg.append_with("\n".join(project_lines))
        else:
            cfg.append_with(project_def.strip())
        cfg.append_with("\n# end project\n")

    # if it's an new project, generate new one
    if not has_old_def:
        cfg.append_with(f"# project: {config.source_project_name}\n")
        cfg.append_with("\n".join(project_lines))
        cfg.append_with("\n# end project")

    # if config.server_code:
    with open(path.join(server_dir_config.root, "__init__.py"), "w") as f:
        s = cfg.to_cfg_string()
        f.write(s)

    cfg = CfgGenerator()
    cfg.append_with("# coding: utf8")
    cfg.append_with()

    if config.outside_server:
        cfg.append_with("import sys")
        # 扫描根目录, 为其存在的路径增加
        for d in os.listdir(config.outside_server_path):
            if d == "rpc":
                # 跳过 rpc runtime
                continue
            if os.path.isdir(d) and os.path.exists(
                    os.path.join(config.outside_server_path, d, "__init__.py")):
                cfg.append_with(f"sys.path.append('./{d}')")

        # cfg.append_with(f"sys.path.append('./{config.source_project_name}')")
        cfg.append_with("\n")

    cfg.append_with("from rpc.runtime.runtime import server")

    # if config.outside_server:
    #     # 引入所有 python package
    #     inject_source_package(server_dir_config.base_dir, cfg)

    cfg.append_with()
    cfg.append_with()
    cfg.append_with("if __name__ == '__main__':")
    with cfg.with_ident():
        cfg.append_with("server.loop()")

    # if config.server_code:
    with open(path.join(server_dir_config.base_dir, "rpc_server.py"), "w") as f:
        s = cfg.to_cfg_string()
        f.write(s)


def inject_source_package(base_dir: str, cfg: CfgGenerator):
    """
    当生成的 rpc 项目是作为 独立项目存在时，为启动程序添加 path 信息，
    """
    base_dir = os.path.join(base_dir, config.source_project_name)
    for f in os.listdir(base_dir):
        d = os.path.join(base_dir, f)
        if os.path.isdir(d) and os.path.exists(os.path.join(f, "__init__.py")):
            cfg.append_with(f"sys.path.append('./{config.source_project_name}/{f}')")


def gen_class_def(cfg: ConfigBase, py_def: GrpcPyDef, dir_config: ClientDirConfig):
    """
    创建 rpc 服务的客户端入口，所有 rpc 服务的调用都将由此入口进入
    :param cfg:
    :param py_def:
    :param dir_config:
    :return:
    """
    # gen_runtime_interface(self, dir_config)
    py_def.gen_conf()
    rpc_content = py_def.get_service()
    type_content = py_def.get_header()
    with open(path.join(dir_config.root, cfg.get_file_name().lower() + ".py"), "w") as f:
        f.write(rpc_content)
    with open(path.join(dir_config.impl, cfg.get_file_name().lower() + ".py"), "w") as f:
        f.write(type_content)


def gen_mid_file(cfg: ConfigBase, dir_config: ClientDirConfig):
    """
    生成 grpc 的中间代码
    :param cfg:
    :param dir_config:
    :return:
    """
    # gen protocol file
    file_name = cfg.get_file_name()
    conf_file_path = path.join(dir_config.mid_file, file_name.lower() + ".proto")
    with open(conf_file_path, "w") as f:
        conf = cfg.get_conf()
        f.write(conf)

    # gen grpc file
    try:
        subprocess.call([
            "python", "-m", "grpc_tools.protoc",
            "-I%s" % dir_config.mid_file,
            "--python_out=%s" % dir_config.encode,
            "--grpc_python_out=%s" % dir_config.encode,
            conf_file_path
        ])

        rename_encode_file(cfg, dir_config.encode)
        rename_encode_file(cfg, dir_config.client_path)
    except FileNotFoundError as fo:
        print("grpc generator tool can not found.")
        raise fo


def rename_encode_file(cfg: ConfigBase, dir_path: str):
    """
    为了减少后续框架做的事情，修改 grpc 生成的文件内容, 将绝对导入改为相对导入
    :param cfg:
    :param dir_path:
    :return:
    """
    name = cfg.meta_data.name.lower()
    file_name = os.path.join(dir_path, "%s_pb2_grpc.py" % name)
    if not os.path.exists(file_name):
        return

    content = open(file_name, "r").readlines()
    content[3] = "from . import %s_pb2 as %s__pb2\n" % (name, name)
    with open(file_name, "w") as f2:
        f2.writelines(content)


def construct_runtime_module(dir_config: ClientDirConfig):
    """
    尝试构建 runtime 公共库
    :return:
    """
    if not path.exists(dir_config.runtime):
        try:
            # 进入 rpc 目录，清除旧依赖，创建 runtime 依赖
            # 尝试清除 cache，如果上一次执行失败过，cache 会导致无法建立 submodule,
            # 除了 cache 还要尝试清除旧的 submodule
            cmd_list = [
                ["git", "rm", "-r", "--cached", "rpc"],
                ["git", "submodule", "deinit", dir_config.runtime, "-f"]
            ]

            for cmd in cmd_list:
                try:
                    subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except FileNotFoundError:
                    pass

            os.chdir(dir_config.root)
            subprocess.check_call([
                "git", "submodule", "add", "-f", "-b",
                config.runtime_repo_branch, config.runtime_repo,
                "runtime"
                # dir_config.runtime
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            os.chdir("./runtime")
            subprocess.call([
                "git", "submodule", "update", "--init", "--remote"
            ])
            os.chdir(dir_config.base_dir)
        except FileNotFoundError as fo:
            print("can not found the %s command for the runtime submodule" % fo.filename)
            # raise fo
        except Exception as e:
            print("error occur while init runtime submodule, error message: ", str(e))

    try:
        os.chdir(dir_config.root)
        subprocess.call(["git", "submodule", "update", "--init", "--remote", "--recursive"])
        os.chdir(dir_config.base_dir)
    except FileNotFoundError as fo:
        print("can not found the %s command for submodule update" % fo.filename)
        raise fo
