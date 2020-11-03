import typing
from os import path

from .analyser import ModuleScanner, ModelWithVar
from .codegen.service.base import ensure_dir
from .codegen.service.sqlalchemy_def import OrmDef


class ModelWorker(object):
    """
    用于生成新的 RPC 信息，需要指定生成文件的输出目录，对应的 rpc server 及 client 都会
    生成到指定的目录
    """

    def __init__(self, output_path: str, api_path: str, filter_str: str):
        """
        使用得到的 Meta 列表，构建 ORM 接口模板, 按照指定的目录地址构造 model 目录
        """
        self.output_path = output_path
        self.api_path = api_path
        self.models: typing.List[ModelWithVar] = []
        self.filter_str = filter_str

        ensure_dir(self.output_path)

    def start(self) -> bool:
        """
        开始构建
        """
        # 获取所有的 Model 定义，然后检查 column, 得到所有定义了 column 属性的 Model,
        # 然后再生成相关 ORM 代码
        scanner = ModuleScanner()
        scanner.gather()

        models = []

        for model in scanner.get_models():
            cols = model.model.get_columns()
            if cols:
                # 只有满足指定包路径的才会加入 models
                if model.module_name.find(self.filter_str) != -1:
                    models.append(model)

        self.models = models

        # 生成 orm 代码
        model_set: typing.Dict[str, typing.List[OrmDef]] = {}
        extra_packages = set()
        for model in self.models:
            orm_def = OrmDef(model, api_path=self.api_path)
            orm_def.gen_conf()
            extra_packages.update(orm_def.extra_packages)

            index = model.module_name.rfind(".")
            name = model.module_name
            if index != -1:
                name = model.module_name[index + 1:]
            ml = model_set.setdefault(name, [])
            ml.append(orm_def)

        def write_file(file_name, content: typing.List[str], with_meta: bool = False, with_base: bool = False,
                       w_extra_packages: typing.Set[str] = None):
            with open(file_name, "w") as wf:
                header = OrmDef.sqlalchemy_def(
                    self.api_path, sorted(list(col_types)), with_meta=with_meta, with_base=with_base,
                    extra_packages=w_extra_packages
                )
                wf.write(header)
                wf.write("\n".join(content))

        # 保持跟定义的文件结构一样，输出到 output_path 中
        model_names = []
        for name, models in model_set.items():
            col_types = set()
            orm_str = []
            schema_str = []
            for model in sorted(models, key=lambda m: m.model.var_name.lower()):
                col_types.update(model.col_types)
                orm_str.append(model.get_orm_conf())
                schema_str.append(model.get_schema_conf())

            output_orm_file_path = path.join(
                self.output_path,
                name + ".py"
            )
            output_sch_file_path = path.join(
                self.output_path,
                name + "_schema.py"
            )
            write_file(output_orm_file_path, orm_str, with_base=True, w_extra_packages=extra_packages)
            write_file(output_sch_file_path, schema_str, with_meta=True, w_extra_packages=extra_packages)

            model_names.append(f"from .{name} import *")
            model_names.append(f"from .{name}_schema import *")

        with open(path.join(self.output_path, "__init__.py"), "w") as f:
            f.write("\n".join(sorted(model_names)))

        return True


def __test__():
    worker = ModelWorker("/tmp//api_gen", "src.web", "")
    worker.start()
