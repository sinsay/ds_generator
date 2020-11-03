from ....common import RpcType

base_tags = ["B", "I", "DT", "DTT", "F", "V", "DB", "S"]

Mapping = {
    "V": "",
    "B": "fields.Boolean",
    "I": "fields.Integer",
    "DT": "fields.Date",
    "DTT": "fields.DateTime",
    "F": "fields.Float",
    "DB": "fields.Float",
    "S": "fields.String",
    "D": "fields.Nested",
    "L": "fields.List"
}

MappingLiteral = {
    "V": "",
    "B": "bool",
    "I": "int",
    "DT": "date",
    "DTT": "datetime",
    "F": "float",
    "DB": "float",
    "S": "str",
    "D": "dict",
    "L": "list"
}


def flask_mapping_literal(key: RpcType) -> str:
    return MappingLiteral.get(key.__rpc_tag__, None)


def flask_mapping(key: RpcType) -> str:
    """
    从 RPC_TAG 定义转为 Flask 类型定义
    """
    return Mapping.get(key.__rpc_tag__, None)
