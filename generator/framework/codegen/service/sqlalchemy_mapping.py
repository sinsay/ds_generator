import typing

from ....common import RpcType

base_tags = ["B", "I", "DT", "DTT", "F", "V", "DB", "S"]

Mapping = {
    "V": "",
    "B": "fields.Boolean",
    "I": "Integer",
    "DT": "fields.Date",
    "DTT": "fields.DateTime",
    "F": "fields.Float",
    "DB": "fields.Float",
    "S": "String",
    "D": "fields.Nested",
    "L": "fields.List"
}


def sqlalchemy_mapping(key: RpcType) -> str:
    return key.get_column_type()


def bool_key_mapping(value: typing.Any):
    return not not value


def primary_key_mapping(_key: str, _col: RpcType, value: typing.Any):
    value = bool_key_mapping(value)
    if not value:
        return ""
    return f"primary_key = {value}"


def index_key_mapping(_key: str, _col: RpcType, value: typing.Any):
    """
    TODO: index 需要支持更多的定义方式，而不是只有 True or False
    """
    value = bool_key_mapping(value)
    if not value:
        return ""
    return f"index = {value}"


def unique_key_mapping(_key: str, _col: RpcType, value: typing.Any):
    value = bool_key_mapping(value)
    if not value:
        return ""
    return f"unique = {value}"


def nullable_key_mapping(_key: str, _col: RpcType, value: typing.Any):
    return f"nullable = {bool_key_mapping(value)}"


def foreign_key_mapping(_key: str, _col: RpcType, value: typing.Any):
    if not value:
        return ""
    return f"ForeignKey(\"{value}\")"


AttrMapping: typing.Dict[str, typing.Callable[[str, RpcType, typing.Any], typing.Any]] = {
    "foreign": foreign_key_mapping,
    "primary_key": primary_key_mapping,
    "nullable": nullable_key_mapping,
    "index": index_key_mapping,
    "unique": unique_key_mapping,
}


def orm_attr_mapping(key: str, col: RpcType, value: typing.Any):
    """
    处理 fields 的 ORM 属性定义与 SQLAlchemy 定义转换
    """
    func = AttrMapping.get(key, None)
    if not func:
        return ""
    return func(key, col, value)
