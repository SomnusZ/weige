"""
全局字典项配置
集中维护项目中所有枚举值，避免魔法数字散落在各处
使用方式：from app.dicts import DeleteStatus
"""


class DeleteStatus:
    """删除状态"""
    NORMAL  = False   # 未删除
    DELETED = True    # 已删除


class AttrValueType:
    """商品动态属性值类型（EAV 模式）"""
    STR   = 'str'     # 文本
    INT   = 'int'     # 整数
    FLOAT = 'float'   # 小数
    BOOL  = 'bool'    # 布尔


# value_type 到对应数据库字段的映射，供序列化器校验时统一使用
ATTR_TYPE_FIELD_MAP = {
    AttrValueType.STR:   'value_str',
    AttrValueType.INT:   'value_int',
    AttrValueType.FLOAT: 'value_float',
    AttrValueType.BOOL:  'value_bool',
}
