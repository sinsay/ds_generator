"""
生成 rpc 服务的接口定义
"""

from .grpc_py_def import GrpcPyDef
from .... import config
from ....common import Entry
from ...util.text import pretty_name


class GrpcPyServerDef(GrpcPyDef):
    def prepend(self):
        pass

    def get_service(self):
        """
        获取服务定义
        :return:
        """
        self.append_with("# coding: utf-8\n")
        self.append_with("import typing")
        self.append_with("from .encode import %s_pb2_grpc as pb2_grpc" % self.meta_data.name.lower())
        self.append_with("from .impl.%s import *" % self.meta_data.name.lower())
        self.append_with("from .runtime.runtime import Context, TraceInfo, reg_servicer")
        self.append_with("from .runtime.runtime.concurrency.local_trace import TraceContext")
        if config.need_impl:
            self.append_with(
                "from %s import %s" %
                (str(self.meta_data.impl_type.__module__), self.meta_data.service_type.__name__))

        self.append_with("\n")

        result = "".join(self.conf + self.service_def.conf)
        self.conf = []
        return result

    def gen_conf(self):
        """
        生成 gRPC 的配置文件文本，并保存在自身的 conf 中
        :return:
        """
        for entry in self.meta_data.entries:
            self.process_entry_def(entry)

        self.header_def.conf = self.conf
        self.conf = []

        # 最后才实现 RPC Class
        self.append_with("class %sServicer(pb2_grpc.%sServicer):" % (self.module_name, self.module_name))

        with self.with_ident():
            self.append_with("from_project = \"%s\"" % (
                    config.outside_server and config.outside_server_name or config.source_project_name))
            self.append_with("rpc_name = \"%s\"\n" % self.module_name)
        for entry in self.meta_data.entries:
            self.process_entry(entry)

        # self.append_with()
        # self.append_with(
        #     f"reg_servicer({self.module_name}Servicer, pb2_grpc.add_{self.module_name}Servicer_to_server)")

        self.service_def.conf = self.conf
        self.conf = []

    def process_service_body(self, entry: Entry):
        """
         生成 service 的实现定义，默认实现为客户端的，服务端的实现由子类 GrpcPyServerDef 完成
         :param entry:
         :return:
         """
        self.append_with("arg = %s()" % self.get_entry_name("Arg"))
        self.append_with("arg.from_pb2(request)")
        self.append_with("ctx = Context(TraceInfo(\"%s.%s\"), impl_context=context)" % (self.module_name, entry.name))
        self.append_with("with TraceContext(ctx):")
        with self.with_ident():
            # 具体调用的名称要使用实现了 impl 的类型名
            if config.need_impl:
                self.append_with("impl = %s(ctx)" % pretty_name(self.meta_data.impl_type.__name__))
                self.append_with("result = impl.%s(arg)" % entry.name)
                self.append_with("return result.convert_pb2()")
            else:
                self.append_with(f"# 在此处实现具体的业务逻辑，返回的类型必须为 {self.get_entry_name('Result')}")
                self.append_with("raise NotImplementedError()")

    def process_entry(self, entry: Entry):
        """
        处理一个 rpc 服务
        :param entry:
        :return:
        """
        self.enter_entry(entry.name)
        # 接口定义
        with self.with_ident():
            self.append_with("def %s(self, request, context):" % entry.name)
            with self.with_ident():
                self.process_service_body(entry)

        self.exit_entry()
        self.append_with()

    def append_header_common(self):
        self.append_with("from ..runtime.runtime.common import RPCDict")
