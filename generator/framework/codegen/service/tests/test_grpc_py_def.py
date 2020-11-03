from generator.common import fields, CommonBase, CommonImpl
from generator.common.base_util import impl_name
from generator.framework.analyser import Analyser
from generator.framework.codegen.service.grpc_py_def import GrpcPyDef


Args = fields.args(fields.model("DemoArgs", dict(
    name=fields.String(description="name of user", required=True, default_value=""),
    info=fields.Dict(dict(
        age=fields.Integer(description="age info", default_value=0),
        height=fields.Float(description="height of user", default_value=170.0)
    ), description="user info")
), description="Args of demo"))


Resp = fields.resp(fields.model("DemoResp", dict(
    status=fields.Bool(description="calling status", default_value=False),
    message=fields.String(description="if error occur, this is the description of error")
)))


@impl_name("DemoImpl")
class DemoBase(CommonBase):
    @Args
    @Resp
    def hello(self):
        """demo hello api"""
        pass


class DemoImpl(CommonImpl):
    def hello(self):
        pass


class TestGrpcPyDef(object):
    def test_def(self):
        metas = Analyser.analyse([DemoBase], [DemoImpl])
        gen = GrpcPyDef(metas[0])
        gen.gen_conf()
        _cfg = gen.to_cfg_string()
        # code = compile(cfg, "test", "exec")
        # exec(code, globals(), locals())
        # assert(HelloArg is not None)
