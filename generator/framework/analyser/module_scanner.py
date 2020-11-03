import sys
import typing

from types import ModuleType
from ...common import CommonAbs, CommonImpl, CommonBase
from ...common.type_def import Model, is_enum, Enum


class ModelWithVar(object):

    def __init__(self, var_name: str, module_name: str, model: Model, ):
        """
        增加了一个定义时的变量名信息, 并且重写了比较函数，用于去重
        保存了 model 的变量名称，model 所在的模块名称，及 model 定义
        """
        self.model = model
        self.module_name = module_name
        self.var_name = var_name

    def __eq__(self, other: 'ModelWithVar'):
        """
        去重的标准为变量名及表名都相同
        """
        return self.model.name == other.model.name

    def __hash__(self):
        return hash((self.model.name, self.module_name))


class EnumWithVar(object):

    def __init__(self, var_name: str, module_name: str, enum: Enum):
        """
        保存 枚举 定义
        """
        self.enum = enum
        self.module_name = module_name
        self.var_name = var_name

        if not self.enum.name:
            self.enum.name = self.var_name

    def __eq__(self, other: 'EnumWithVar'):
        """
        去重的标准为枚举名称
        """
        result = self.enum.name == other.enum.name or\
            (self.enum.description == other.enum.description and
             self.enum.enum_dict.keys() == other.enum.enum_dict.keys())

        if result:
            name = self.enum.name or other.enum.name
            self.enum.name = name
            self.var_name = name

        return result

    def __hash__(self):
        return hash((self.enum.description, tuple(self.enum.enum_dict.keys())))


class ModuleScanner(object):
    """
    给定指定的 module, 解析该 module 中是否有继承了 CommonBase 类的类型，如果有则返回该类型
    如果 module 没有传递，则搜索全局的模块信息
    """
    def __init__(self, module=None):
        """
        递归查找 module 中，所有继承了 base_class 类的对象
        增加了 models 字段，用于存放所有扫描得到的 Model 实例
        :param module:
        """
        self.modules = module and [module] or [m for m in sys.modules.values()]
        self.types = []
        self.impls = []
        self.models: typing.Set[ModelWithVar] = set()
        self.enums: typing.Set[EnumWithVar] = set()
        self.gather()

    def get_models(self) -> typing.List[ModelWithVar]:
        return list(self.models)

    def get_enums(self) -> typing.List[EnumWithVar]:
        return list(self.enums)

    def gather(self):
        types = set()
        impls = set()
        cached = set()
        for module in iter(self.modules):
            self.check(module, types, impls, 0, cached)

        return list(types), list(impls)

    def check(self, module, types, impls, depth, cached):
        if module in cached:
            return

        # 避免循环引用模块造成的无限递归
        if depth > 10:
            return

        attr_names = dir(module)
        for attr_name in attr_names.copy():
            attr = None
            try:
                attr = getattr(module, attr_name)
            except Exception as e:
                if "_tkinter" not in str(e) and "six.moves" not in module.__name__:
                    print("获取 module %s 的 %s attribute 时出错，应是该包在导入时会运行不支持的其他包, 错误信息为: %s" % (module, attr_name, e))

            attr_type = type(attr)
            if attr_type is ModuleType:
                self.check(attr, types, impls, depth + 1, cached)

            if issubclass(attr_type, type) and attr and CommonAbs.same_rpc_thing(attr):
                if CommonBase.same_rpc_thing(attr) and getattr(attr, "__name__", None) != "CommonBase":
                    types.add(attr)
                if CommonImpl.same_rpc_thing(attr) and getattr(attr, "__name__", None) != "CommonImpl":
                    impls.add(attr)

            try:
                if attr_type != type and getattr(attr, "__model_tag__", None) == "MT":
                    self.models.add(ModelWithVar(attr_name, module.__name__, attr))
                if attr_type != type and is_enum(attr):
                    self.enums.add(EnumWithVar(attr_name, module.__name__, attr))
            except:
                # maybe some flask global variable will cause error raise
                pass

        cached.add(module)
