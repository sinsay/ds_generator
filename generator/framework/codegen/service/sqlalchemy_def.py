import typing

from .sqlalchemy_mapping import AttrMapping
from ..config import ConfigBase
from ...analyser import ModelWithVar
from ...util.cfg_generator import CfgGenerator
from ....common import RpcType, fields


class OrmDef(ConfigBase, CfgGenerator):
    """
    生成 SQLAlchemy ORM 对象的模板类
    """
    CLASS_PATH = {
        'index': 'sqlalchemy/Index'  # 索引类
    }

    def __init__(
            self,
            model: ModelWithVar,
            runtime_path: str = "runtime",
            api_path: str = "src",
            orm_path: str = "src",
            gen_filter: typing.List[str] = None
    ):
        ConfigBase.__init__(self, None)
        CfgGenerator.__init__(self)

        # 过滤所有的 model, 只保留定义了 columns 的
        self.api_path = api_path
        self.orig_model = model
        self.model = []
        is_orm = False
        for _, value in model.model.fs.get_elem_info().items():
            if value.is_column():
                is_orm = True
                break

        if is_orm:
            self.model = model
        # 导包路径,如果有索引则导入 Index
        self.extra_packages: typing.Set[str] = set()
        self.has_indexes = False
        if model.model.indexes:
            self.has_indexes = True
            self.extra_packages.add(self.__class__.CLASS_PATH['index'])
        # 过滤器，用于指定过滤
        self.filter = gen_filter

        self.schema_conf = CfgGenerator()
        # 用于保存嵌套类型的定义，后续生成时保存到函数定义前
        self.header_def = CfgGenerator()

        self.runtime_path = runtime_path

        self.orm_path = orm_path

        # 该模块所需使用的 column 类型集合
        self.col_types: typing.Set[str] = set()

        self.class_header_def = CfgGenerator()
        self.class_conf = CfgGenerator()

    def gen_conf(self):
        if self.model is None:
            return

        self.conf = self.schema_conf.conf
        self.def_model(self.model, self.col_types)

        self.conf = self.class_conf.conf
        self.def_class_model(self.model)
        self.header_def.append_with(
            self.sqlalchemy_def(
                self.api_path, list(self.col_types), with_base=False, with_meta=True, extra_packages=self.extra_packages
            )
        )
        self.class_header_def.append_with(
            self.sqlalchemy_def(
                self.api_path, list(self.col_types), with_base=True, with_meta=False, extra_packages=self.extra_packages
            )
        )

    def def_class_model(self, model: ModelWithVar):
        """
        生成一个 ORM 定义, 每个 model 使用的 column 类型会添加到 col_type ,
        供最外层根据需要导入 SQLAlchemy 所需的类型
        """
        self.append_with(f"class {model.var_name}(Base):")
        self.append_with()
        with self.with_ident():
            self.append_with(f"__tablename__ = \"{model.model.name}\"")
            self.append_with()
            self.append_with(
                "__table_args__ = (")
            with self.with_ident():
                self.append_with(f"{{ \"comment\": \"{model.model.fs.description}\"}},")
                if self.has_indexes:
                    indexes_temp = self.gen_indexes(model)
                    for i, index_temp in enumerate(indexes_temp):
                        self.append_with(index_temp)

            self.append_with(")")
            self.append_with()

            for col_name, col_def in model.model.fs.get_elem_info().items():
                if not col_def.is_column():
                    continue

                self.gen_column(col_name, col_def, with_separator=False)
                self.append_with()

    @staticmethod
    def sqlalchemy_def(api_path: str, types: typing.List[str], with_base: bool = False, with_meta: bool = False,
                       extra_packages: typing.Set[str] = None) -> str:
        # 暂时先加上 Index
        extra_packages = extra_packages or set()
        sqlalchemy_classnames = [OrmDef.parse_class_path(extra_package)[1] for extra_package in extra_packages if
                                 OrmDef.parse_class_path(extra_package)[0] == 'sqlalchemy']
        return "\n".join([
            "from sqlalchemy import"
            f"{with_meta and ' Table, ' or ''} Column " + (
                    types and ", " + ", ".join(types + sqlalchemy_classnames) or "")
            ,
            with_meta and f"from {api_path} import meta_data" or "",
            with_base and f"from {api_path} import Base" or "",
            ""
        ])

    def def_model(self, model: ModelWithVar, col_types: typing.Set[str]):
        """
        生成一个 ORM Schema 定义, 每个 model 使用的 column 类型会添加到 col_type ,
        供最外层根据需要导入 SQLAlchemy 所需的类型
        """
        self.append_with(f"{model.var_name} = Table(")
        with self.with_ident():
            self.append_with(f"\"{model.model.name}\",")
            self.append_with("meta_data, ")
            for col_name, col_def in model.model.fs.get_elem_info().items():
                if not col_def.is_column():
                    continue

                if col_def.get_column().foreign is not None:
                    col_types.add("ForeignKey")
                col_types.add(col_def.get_column_type())

                self.gen_column(col_name, col_def)
            self.append_with(f"comment = \"{model.model.fs.description}\"")
        self.append_with(")")

    def gen_column(self, col_name: str, col_def: RpcType, with_separator: bool = True):
        """
        生成一个字段的的定义
        """
        if not with_separator:
            self.append_with(f"{col_name} = ", new_line=False)
        self.append_with("Column(")
        with self.with_ident():
            if with_separator:
                self.append_with(f"\"{col_name}\",")

            self.append_with(f"{self.column_type(col_def)},")
            col = col_def.get_column()
            for key, value in AttrMapping.items():
                attr_define: typing.Union[typing.Any, None] = getattr(col, key, None)
                if attr_define is None:
                    continue

                attr_str = value(key, col_def, attr_define)
                if not attr_str:
                    continue

                self.append_with(f"{attr_str},")
            self.append_with(f"comment = \"{col_def.description}\"")
        self.append_with(")" + (with_separator and "," or ""))

    def gen_indexes(self, model: ModelWithVar):

        """生成所有索引的定义,暂时只支持 mysql"""
        return [f"Index(\"{index.index_name}\", " + ", ".join(
            [f"\"{column}\"" for column in index.columns]) + f", mysql_using=\"{index.index_type}\")," for index in
                model.model.indexes]

    @staticmethod
    def column_type(col_def: RpcType):
        col = col_def.get_column()
        if col.length is None:
            return col_def.get_column_type()
        else:
            return f"{col_def.get_column_type()}({col.length})"

    def get_header_conf(self) -> str:
        return "".join(self.header_def.conf)

    def get_conf(self) -> str:
        return "".join(self.conf)

    def get_orm_conf(self) -> str:
        return "".join(self.class_conf.conf)

    def get_schema_conf(self) -> str:
        return "".join(self.schema_conf.conf)

    def to_cfg_string(self):
        return "\n\n".join([
            self.get_header_conf(),
            self.get_conf()
        ])

    @staticmethod
    def parse_class_path(path: str, alias_name: str = '', dirct_import: bool = False,
                         import_all: bool = False) -> tuple:
        """

        :param path: 要解析的路径,例如/sqlalchemy/Index
        :param alias_name: 路径的别名
        :param dirct_import: 是否直接导入,例如 import sqlalchemy
        :param import_all: 是否导入所有,例如 from sqlalchemy import *
        :return: (relative_path:from 的包的相对路径, class_name :类名,函数或变量等, alias_name:别名)

        """
        if path == '':
            raise Exception('path is not block')
        if path.endswith('/') or path.startswith('/'):
            raise Exception('path Prefix and suffix are not "/" ')
        if dirct_import:
            return None, path.replace('/', '.'), alias_name
        if import_all:
            return path.replace('/', '.'), '*', ''
        path_list = path.rsplit('/', maxsplit=1)
        if len(path_list) == 1:
            return None, path_list[0], alias_name
        return path_list[0].replace('/', '.'), path_list[1], alias_name

    @staticmethod
    def gen_import_temp(pathlist: typing.List[tuple]) -> str:
        """
        根据parse_class_path返回的元组,输入多个生成对应的导包模板
        :param pathlist:
        :return:
        todo:未做去重功能
        """
        relative_path_mapping = {}  # {"a.b":[("c","d"),("e","f")]
        dirct_import_list = []  # [("a","b")]

        for relative_path, class_name, alias_name in pathlist:
            if not relative_path:
                dirct_import_list.append((class_name, alias_name))
                continue
            if relative_path not in relative_path_mapping:
                relative_path_mapping[relative_path] = []
            relative_path_mapping[relative_path].append((class_name, alias_name))

        import_template = []
        for class_name, alias_name in dirct_import_list:
            import_template.append(f"import {class_name}" + (f" as {alias_name}" if alias_name else ""))
        for relative_path, class_name_list in relative_path_mapping.items():
            import_template.append(
                f"from {relative_path} import " + (class_name_list and ", ".join(
                    [f"{class_name}" + (f" as {alias_name} " if alias_name else "") for class_name, alias_name in
                     class_name_list]) or "") or "")
        return "\n".join(import_template)


def __test_define_model__():
    user = fields.model("she_user", {
        "id": fields.Integer().column(primary_key=True, index=True),
        "user_id": fields.Integer().column(index=True),
        "phone": fields.String().column(length=11, index=True, unique=True)
    }, description="comment of she_user table",
                        indexes=[fields.index(columns=['id', 'user_id']),
                                 fields.index('ind_id_phone', columns=['id', 'phone'], index_type=fields.index.HASH)])

    profile = fields.model("she_profile", {
        "id": fields.Integer().column(primary_key=True),
        "name": fields.String().column(unique=True),
        "user_id": fields.Integer().column(foreign="she_user.id")
    })

    return [ModelWithVar("User", "user", user), ModelWithVar("Profile", "user", profile)]


def __test__():
    models = __test_define_model__()
    fd = OrmDef(models[0])
    fd.gen_conf()
    print("".join(fd.class_conf.conf))
    print("".join(fd.schema_conf.conf))
    fd.get_conf()
