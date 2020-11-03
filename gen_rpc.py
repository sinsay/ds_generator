# config: utf8

import argparse
import os
import sys
import generator
import generator.config as config
import logging

server_output_path = "."


if __name__ == '__main__':

    logging.disable(logging.ERROR)

    parser = argparse.ArgumentParser(
        usage="\n\tpython gen_rpc.py -spp ../user_service"
              " -osp ../user_service_rpc"
              " -cop ../user_service_client\n\n"
              "表示将在 ../user_service_rpc 目录为 user_service 生成 rpc 服务,\n"
              "并在 ../user_service_client 目录生成调用 user_service_rpc 的客户端"
    )

    parser.add_argument(
        "-spp", "--source_project_path",
        help="需要生成 RPC 服务的项目目录, 当设置了 outside_server 时为需要生成 RPC 服务的 git 地址",
        default="", type=str)

    parser.add_argument(
        "-cop", "--client_output_path",
        help="用于存放 rpc 客户端代码的目录，该目录需要是 git 仓库, 如果不提供该配置，则不会生成调用客户端的代码",
        type=str, default="")

    parser.add_argument(
        "-nsc", "--no_server_code", action="store_true",
        help="是否需要生成服务端代码, 如果该选项为 true, 则不会在 server_project_path 下生成"
             " rpc 相关代码, 该选项默认关闭, 当开启了 osp 选项时，该选项必定为 false"
    )

    parser.add_argument(
        "-ni", "--need_impl", action="store_true",
        help="CommonBase 是否需要对应的 CommonImpl, 为 false 时不会限制 Common Base 一定需要有"
             "对应的 Impl 代码，可用于只生成接口定义的场景,"
             " 该选项默认关闭",
    )

    parser.add_argument(
        "-osp", "--outside_server_path",
        help="设置该参数时，生成的服务端代码将待解析的项目分离，并将待解析的项目作为子模块引入, "
             "source_path 则需要改为填写待解析项目的 git 地址 或本地项目路径"
             "并以设置的 outside_server_path 作为存放生成的服务端项目的目录地址,"
             "在使用该模式时， -nsc 选项不可用",
        type=str
    )

    args = parser.parse_args()
    for k, v in args.__dict__.items():
        setattr(config, k, v)

    config.need_impl = args.need_impl
    config.server_code = not args.no_server_code

    if not config.source_project_path:
        parser.error("项目源代码目录不能为空")
        sys.exit(1)

    if config.outside_server_path:
        config.outside_server = True

    # 当不是 独立服务端 模式时， 处理 source_project_path
    if not config.outside_server:
        if config.source_project_path.startswith("~/"):
            config.source_project_path = os.path.expanduser(config.source_project_path)

        config.source_project_path = os.path.abspath(config.source_project_path)

        if not os.path.exists(config.source_project_path):
            parser.error("项目源代码目录不存在.")
            sys.exit(1)

        generated_path = os.path.join(config.source_project_path, "./rpc/encode")
        if os.path.exists(generated_path):
            sys.path.append(generated_path)
            sys.path.append(config.source_project_path)

    # 如果客户端的输出目录为相对目录，则将其转换为绝对目录
    if config.client_output_path.startswith("~/"):
        config.client_output_path = os.path.expanduser(config.client_output_path)

    if config.client_output_path:
        config.client_output_path = os.path.abspath(config.client_output_path)

    if config.client_output_path and not os.path.exists(config.client_output_path):
        parser.error("客户端代码目录不存在.")

    config.from_current_project = False

    if config.outside_server:
        # 如果开启了 Outside Server, 则不会在原始项目中生成任何东西
        config.server_code = False

    if config.server_code:
        config.server_output_path.append(config.source_project_path)

    if config.outside_server:
        # 如果使用了本地服务路径，则将其转换为绝对路径
        # TODO: 是否要在该路径下查找具体的 git 仓库路径？
        if os.path.exists(config.source_project_path):
            config.source_project_path = os.path.abspath(config.source_project_path)
        if os.path.exists(config.outside_server_path):
            config.outside_server_path = os.path.abspath(config.outside_server_path)
        config.server_output_path.append(config.outside_server_path)

        config.outside_server_name = config.outside_server_path[config.outside_server_path.rfind("/") + 1:]

    config.source_project_name = config.source_project_path[config.source_project_path.rfind("/") + 1:]
    if config.source_project_name.endswith(".git"):
        config.source_project_name = config.source_project_name[:-4]

    if not config.client_output_path:
        print("客户端目录为空，该模式为不输出客户端代码.")

    print("即将生成的项目信息")
    msg = "\n".join([
        f"生成独立项目: {config.outside_server}",
        f"\t独立项目路径: {config.outside_server_path}",
        f"\t独立项目名称: {config.outside_server_name}",
        f"原项目路径: {config.source_project_path}",
        f"原项目名称: {config.source_project_name}",
        f"生成客户端代码: {not not config.client_output_path}",
        f"\t客户端项目路径: {config.client_output_path}"
    ])

    print(msg)

    worker = generator.framework.worker.Worker()
    worker.start()
