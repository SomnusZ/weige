# 微格商品展示网站 · 开发日志

> 记录日期：2026-04-21 / 最近更新：2026-04-22
> 技术栈：Django 5.2 + Django REST Framework + MySQL 8
> 项目地址：https://github.com/SomnusZ/weige.git

---

## 目录

1. [项目背景与目标](#1-项目背景与目标)
2. [架构讨论与关键决策](#2-架构讨论与关键决策)
3. [数据库表结构设计](#3-数据库表结构设计)
4. [项目目录结构](#4-项目目录结构)
5. [公共基础设施](#5-公共基础设施)
6. [模块实现详情](#6-模块实现详情)
7. [接口文档](#7-接口文档)
8. [踩坑记录](#8-踩坑记录)
9. [强调与重点](#9-强调与重点)
10. [测试页面](#10-测试页面)
11. [未完成计划](#11-未完成计划)
12. [2026-04-22 改造日志](#12-2026-04-22-改造日志)

---

## 1. 项目背景与目标

仿照 1688.com 商品展示页面，开发一个自己的**商品展示与管理网站**。

核心特点：
- 商品种类繁多，不同品类的商品具有完全不同的属性（大衣有袖长，手机有内存）
- 需要支持按属性**筛选过滤**商品
- 暂不需要用户登录，管理员通过 Django Admin 后台管理数据
- 优先把数据结构和后端接口做扎实，前端展示页面后续再开发

---

## 2. 架构讨论与关键决策

### 2.1 核心问题：如何存储"不同品类有不同属性"

**讨论过程：**

最初的疑问是：大衣有「袖长」属性，手机有「内存」属性，两者完全不同，用一张表无法容纳所有商品的所有属性。

**方案对比：**

| 方案 | 描述 | 缺点 |
|------|------|------|
| 宽表 | 给 product 表加几百个字段 | 大量 NULL，无法扩展 |
| JSON 字段 | 把属性存成 JSON 字符串 | 无法做数据库级筛选过滤 |
| **EAV 模式** ✅ | 用属性定义表 + 属性值表分离存储 | 稍复杂，但灵活且可筛选 |

**最终决策：采用 EAV（Entity-Attribute-Value）模式**

> EAV 的核心思想：不把「大衣的袖长」直接存在 product 表里，而是：
> 1. 在「属性定义表」里记录"大衣这个品类有一个叫袖长的属性，类型是 float"
> 2. 在「属性值表」里记录"大衣A 的袖长值是 82.5"

### 2.2 属性值的类型问题

**讨论过程：**

如果把所有属性值都存成字符串，筛选时无法做 `价格 < 100` 这样的数值比较。

**决策：分列存储，按类型分开字段**

```
value_str   字段  ← 类型为 str  的属性值存这里
value_int   字段  ← 类型为 int  的属性值存这里
value_float 字段  ← 类型为 float 的属性值存这里
value_bool  字段  ← 类型为 bool 的属性值存这里
```

每条记录只有一个字段有值，其余字段强制为 NULL，保持数据干净。

### 2.3 属性一致性问题

**讨论问题：** 大衣A 和大衣B 都属于"大衣"品类，如何保证它们填的属性是一样的（都有袖长，都有材质）？

**决策：** 通过「品类属性定义表」来约束。每个品类预先定义好有哪些属性、哪些必填。商品属性值必须关联到该品类的属性定义，跨品类引用会被后端拦截。

### 2.4 最终四表结构

```
Category（品类表）
    ↓ 1:N
CategoryAttrDef（品类属性定义表）— 定义某品类有哪些属性
    ↓ 1:N
Product（商品表）— 关联品类，存储通用固定字段
    ↓ 1:N
ProductAttrValue（商品属性值表）— 关联商品+属性定义，存储动态值
```

### 2.5 管理员权限讨论

**讨论问题：** `/admin/` 是否任何人都能访问？

**结论：**
- Django Admin 需要登录才能操作，公网用户看到的只是登录页
- 本项目暂不开发普通用户登录，所有管理操作通过 Django Admin 完成
- 生产环境建议限制 `/admin/` 的 IP 访问

### 2.6 RESTful 接口设计规范

**决策：全部采用 ViewSet + `@action` 装饰器**

原因：命名规范、路由自动生成、风格统一。

```python
# 统一命名规范
dir_category()     → GET    /api/categories/dir/
create_category()  → POST   /api/categories/create/
update_category()  → PATCH  /api/categories/<id>/update/
delete_category()  → DELETE /api/categories/<id>/delete/
```

> ⚠️ **关键强调**：本项目基于 Django + RESTful 架构，数据库 MySQL，所有接口严格遵守 RESTful 语义（GET 查询、POST 创建、PATCH 局部修改、DELETE 删除）。PUT 因为要求传全量字段而改用 PATCH。

### 2.7 序列化器设计：Mixin 模式

**讨论问题：** `UpdateSerializer` 继承 `CreateSerializer` 会显得逻辑混乱吗？

**决策：改用 Mixin 模式**

```python
# ❌ 不好：继承关系表达的是"Update 是 Create 的一种"，语义混乱
class ProductUpdateSerializer(ProductCreateSerializer): ...

# ✅ 好：Mixin 表达的是"共享校验逻辑"，语义清晰
class ProductValidationMixin:
    def validate_product_name(self, value): ...

class ProductCreateSerializer(ProductValidationMixin, ModelSerializer): ...
class ProductUpdateSerializer(ProductValidationMixin, ModelSerializer): ...
```

---

## 3. 数据库表结构设计

### 3.1 Category（品类表）

```python
class Category(models.Model):
    category_name = models.CharField(max_length=100)          # 品类名称，全局唯一
    parent        = models.ForeignKey('self',                  # 自引用，支持无限层级树
                        null=True, blank=True,
                        on_delete=models.SET_NULL,
                        related_name='children')
    create_time   = models.DateTimeField(auto_now_add=True)
    is_delete     = models.BooleanField(default=False)         # 逻辑删除标志

    class Meta:
        db_table = 'category'
        ordering = ['id']
```

**树形结构示例：**
```
服装（id=1, parent=None）
  └── 女装（id=2, parent_id=1）
        └── 连衣裙（id=3, parent_id=2）
        └── 大衣（id=4, parent_id=2）
  └── 男装（id=5, parent_id=1）
数码（id=6, parent=None）
  └── 手机（id=7, parent_id=6）
```

**重要设计决策：**
- `parent_name` **不存入数据库**，由序列化器的 `SerializerMethodField` 动态计算，避免数据冗余和不一致
- 品类名称**全局唯一**（任何层级不能重名）
- 逻辑删除时，**直接子品类自动上移**（parent 改为被删品类的 parent）

### 3.2 CategoryAttrDef（品类属性定义表）

```python
class CategoryAttrDef(models.Model):
    category   = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='attr_defs')
    attr_name  = models.CharField(max_length=100)              # 属性名称，如：颜色、袖长
    value_type = models.CharField(max_length=10, choices=[     # 属性值类型
                     ('str','文本'), ('int','整数'),
                     ('float','小数'), ('bool','布尔')])
    is_required = models.BooleanField(default=False)           # 是否必填
    create_time = models.DateTimeField(auto_now_add=True)
    is_delete   = models.BooleanField(default=False)

    class Meta:
        db_table = 'category_attr_def'
        unique_together = [('category', 'attr_name')]          # 同一品类下属性名不重复
```

**重要设计决策：**
- `value_type` 一旦创建不可修改（修改会破坏已有商品属性值数据）
- `category` 一旦创建不可修改（属性定义与品类强绑定）

### 3.3 Product（商品表）

```python
class Product(models.Model):
    product_name  = models.CharField(max_length=200)
    category      = models.ForeignKey(Category,
                        on_delete=models.PROTECT,              # 品类下有商品时禁止删除品类
                        related_name='products')
    product_price = models.DecimalField(max_digits=10, decimal_places=2)
    product_image = models.ImageField(upload_to='products/',   # 上传至 media/products/
                        null=True, blank=True)
    product_stock = models.IntegerField(default=0)
    create_time   = models.DateTimeField(auto_now_add=True)
    is_delete     = models.BooleanField(default=False)

    class Meta:
        db_table = 'product'
        ordering = ['-create_time']                            # 默认按创建时间倒序
```

**重要设计决策：**
- `category` 一旦创建不可修改（修改品类会导致动态属性数据全部错乱）
- `on_delete=models.PROTECT`：品类下有商品时，禁止删除该品类（物理层面的保护）

### 3.4 ProductAttrValue（商品属性值表）

```python
class ProductAttrValue(models.Model):
    product   = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='attr_values')
    attr_def  = models.ForeignKey(CategoryAttrDef, on_delete=models.CASCADE, related_name='attr_values')

    # 分类型存储，根据 attr_def.value_type 决定使用哪个字段，其余为 NULL
    value_str   = models.CharField(max_length=500, null=True, blank=True)
    value_int   = models.IntegerField(null=True, blank=True)
    value_float = models.FloatField(null=True, blank=True)
    value_bool  = models.BooleanField(null=True, blank=True)

    create_time = models.DateTimeField(auto_now_add=True)
    is_delete   = models.BooleanField(default=False)

    class Meta:
        db_table = 'product_attr_value'
        unique_together = [('product', 'attr_def')]            # 同一商品同一属性只能有一条
```

**重要设计决策：**
- `product` 和 `attr_def` 一旦创建不可修改
- 写入时校验：`attr_def` 必须属于该商品的品类（跨品类引用会被拦截）
- 写入时其余值字段强制清空，确保同一记录只有一个字段有值

### 3.5 表关系总览

```
Category ──────────────── CategoryAttrDef
  │  (1:N, attr_defs)         │
  │                           │
  └── Product ────────────── ProductAttrValue
       (1:N, products)    (1:N, attr_values)
                          (1:N, attr_values)
```

---

## 4. 项目目录结构

```
weige/
├── manage.py
├── DEV_LOG.md                      ← 本文件
│
├── weige/                          ← Django 主配置包
│   ├── settings.py                 ← 项目配置（DB、时区、已安装应用）
│   └── urls.py                     ← 主路由（统一注册各模块路由）
│
├── app/                            ← 业务代码根目录
│   ├── dicts.py                    ← 全局枚举/字典项（DeleteStatus、AttrValueType）
│   ├── utils.py                    ← 公共工具函数（统一响应格式）
│   ├── test_views.py               ← 通用测试页面视图
│   │
│   ├── category/                   ← 品类模块
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── admin.py
│   │
│   ├── category_attr_def/          ← 品类属性定义模块
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── admin.py
│   │
│   ├── product/                    ← 商品模块
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── admin.py
│   │
│   └── product_attr_value/         ← 商品属性值模块
│       ├── models.py
│       ├── serializers.py
│       ├── views.py
│       ├── urls.py
│       └── admin.py
│
└── templates/
    └── test/                       ← 测试页面模板目录
        ├── category.html           ✅ 已完成
        └── category_attr_def.html  ✅ 已完成
```

---

## 5. 公共基础设施

### 5.1 统一响应格式（app/utils.py）

所有接口统一返回以下结构，前端可无差别处理：

```python
# 成功响应
{
    "success": True,
    "message": "操作成功",
    "data": { ... }          # 业务数据，失败时为 None
}

# 失败响应
{
    "success": False,
    "message": "创建失败",
    "data": {                # 校验错误详情
        "category_name": ["品类名称已存在"]
    }
}
```

```python
def success_response(data=None, message="操作成功", status_code=200): ...
def error_response(message="操作失败", status_code=400, errors=None): ...
```

### 5.2 全局字典项（app/dicts.py）

> ⚠️ **踩坑**：文件名不能叫 `dict.py`，会与 Python 内置类型 `dict` 命名冲突，改为 `dicts.py`

```python
class DeleteStatus:
    NORMAL  = False   # 未删除
    DELETED = True    # 已删除

class AttrValueType:
    STR   = 'str'
    INT   = 'int'
    FLOAT = 'float'
    BOOL  = 'bool'

# value_type → 对应数据库字段名 的映射，消除各序列化器中的重复代码
ATTR_TYPE_FIELD_MAP = {
    'str':   'value_str',
    'int':   'value_int',
    'float': 'value_float',
    'bool':  'value_bool',
}
```

### 5.3 通用测试页面路由（weige/urls.py）

```python
# 一条路由覆盖所有测试页面，无需为每个页面单独注册
path('test/<str:name>/', test_views.test_page, name='test-page')

# 访问方式：
# http://127.0.0.1:8000/test/category/
# http://127.0.0.1:8000/test/category_attr_def/
# http://127.0.0.1:8000/test/product/
# http://127.0.0.1:8000/test/product_attr_value/
```

```python
# app/test_views.py
def test_page(request, name):
    try:
        return render(request, f'test/{name}.html')
    except Exception:
        raise Http404(f'测试页面 [{name}] 不存在')
```

> 新增测试页面只需在 `templates/test/` 目录下创建对应 HTML 文件，**无需修改任何路由配置**。

### 5.4 主路由配置（weige/urls.py）

```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('app.category.urls')),
    path('api/', include('app.category_attr_def.urls')),
    path('api/', include('app.product.urls')),
    path('api/', include('app.product_attr_value.urls')),
    path('test/<str:name>/', test_views.test_page, name='test-page'),
]
```

---

## 6. 模块实现详情

### 6.1 Category 模块

#### 序列化器设计

**读写分离**：GET 响应和 POST/PATCH 请求使用不同的序列化器：

```python
# 读（GET 响应）
class CategoryListSerializer(ModelSerializer):
    parent_name = SerializerMethodField()          # 动态计算，不入库
    def get_parent_name(self, obj):
        return obj.parent.category_name if obj.parent else None
    fields = ['id', 'category_name', 'parent_id', 'parent_name', 'create_time']

# 写（POST/PATCH 请求）
class CategoryWriteSerializer(ModelSerializer):
    fields = ['category_name', 'parent']
```

#### 校验逻辑

1. **名称非空**：去除首尾空格后不能为空
2. **父级有效性**：父级品类必须存在且未被逻辑删除
3. **全局名称唯一**：所有品类中不能有重名（含不同层级）
4. **防自引用**：不能将自身设为父级
5. **防循环引用**：不能将子孙节点设为父级（递归检查）

```python
def _is_descendant(self, instance, target):
    """递归检查 target 是否是 instance 的子孙节点"""
    children = Category.objects.filter(parent=instance, is_delete=DeleteStatus.NORMAL)
    for child in children:
        if child.id == target.id or self._is_descendant(child, target):
            return True
    return False
```

#### 删除逻辑

```python
# 子品类上移：直接子品类的 parent 改为被删品类的 parent
Category.objects.filter(
    parent=category,
    is_delete=DeleteStatus.NORMAL
).update(parent=category.parent)

category.is_delete = DeleteStatus.DELETED
category.save()
```

**效果示例：**
```
删除前：服装 → 女装 → 连衣裙
删除「女装」后：服装 → 连衣裙（连衣裙上移一级，parent 改为服装）
```

**名称复用：** 已删除品类的名称可以被新品类复用，因为去重查询加了 `is_delete=DeleteStatus.NORMAL` 条件。

### 6.2 CategoryAttrDef 模块

#### 序列化器设计（Mixin 模式）

```python
class CategoryAttrDefValidationMixin:
    def validate_attr_name(self, value): ...         # 公共校验

class CategoryAttrDefCreateSerializer(Mixin, ModelSerializer):
    fields = ['category', 'attr_name', 'value_type', 'is_required']
    def validate_category(self, value): ...          # 品类有效性校验

class CategoryAttrDefUpdateSerializer(Mixin, ModelSerializer):
    fields = ['attr_name', 'is_required']            # 不包含 category 和 value_type
```

> **关键约束**：`value_type` 由 DRF choices 自动校验，无需手动写 `validate_value_type`。

### 6.3 Product 模块

#### 序列化器设计

```python
class ProductValidationMixin:
    def validate_product_name(self, value): ...      # 名称非空
    def validate_product_price(self, value): ...     # 价格 >= 0
    def validate_product_stock(self, value): ...     # 库存 >= 0

class ProductCreateSerializer(Mixin, ModelSerializer):
    fields = ['product_name', 'category', 'product_price', 'product_image', 'product_stock']

class ProductUpdateSerializer(Mixin, ModelSerializer):
    fields = ['product_name', 'product_price', 'product_image', 'product_stock']
    # 不含 category：创建后不可修改品类
```

### 6.4 ProductAttrValue 模块

#### 核心校验函数（模块级公共函数）

```python
def validate_value_by_type(attrs, attr_def, is_partial=False):
    """
    根据属性定义的 value_type，校验对应值字段，其余字段强制清空

    is_partial=False（创建模式）：
      - is_required=True 时对应字段不能为空
      - 非对应类型的值字段一律清空

    is_partial=True（修改模式，PATCH partial）：
      - 用户未传入任何值字段时，跳过整体值校验（保留数据库原值）
      - 只对已传入的字段做校验/清空，不影响未传入字段
    """
    expected_field = ATTR_TYPE_FIELD_MAP.get(attr_def.value_type)
    value_fields   = list(ATTR_TYPE_FIELD_MAP.values())

    if is_partial and not any(f in attrs for f in value_fields):
        return

    if attr_def.is_required:
        if not is_partial or expected_field in attrs:
            if attrs.get(expected_field) is None:
                raise ValidationError({expected_field: '该属性为必填项，不能为空'})

    for field in value_fields:
        if field != expected_field:
            if not is_partial or field in attrs:
                attrs[field] = None
```

> **设计说明（2026-04-22 补充）：** 原函数不区分创建/修改，在 PATCH partial 场景下会误触发"必填项为空"报错。
> 新增 `is_partial` 参数后，`UpdateSerializer` 传入 `is_partial=True`，`CreateSerializer` 不变（默认 False）。
> 详见[改造日志 12.2](#122-product_attr_value--validate_value_by_type-区分创建修改)。

#### 跨字段校验

```python
# 属性定义必须属于该商品的品类
if attr_def.category_id != product.category_id:
    raise ValidationError({'attr_def': '该属性定义不属于此商品的品类'})
```

---

## 7. 接口文档

### 统一说明

- Base URL：`http://127.0.0.1:8000/api`
- 所有响应格式：`{ "success": bool, "message": str, "data": any }`
- 认证：暂无（开发阶段）

---

### 7.1 Category 品类接口

#### GET 查询所有品类

```
GET /api/categories/dir/

入参：无

出参：
{
  "success": true,
  "message": "操作成功",
  "data": [
    {
      "id": 1,
      "category_name": "服装",
      "parent_id": null,
      "parent_name": null,
      "create_time": "2026-04-21T10:00:00"
    },
    {
      "id": 2,
      "category_name": "女装",
      "parent_id": 1,
      "parent_name": "服装",
      "create_time": "2026-04-21T10:01:00"
    }
  ]
}

说明：返回平铺列表，前端通过 parent_id 自行组装树形结构
```

#### POST 新增品类

```
POST /api/categories/create/
Content-Type: application/json

入参：
{
  "category_name": "女装",     // 必填，全局唯一
  "parent": 1                  // 选填，父级品类 ID，不传则为顶级
}

出参（成功 201）：
{
  "success": true,
  "message": "创建成功",
  "data": { "category_name": "女装", "parent": 1 }
}

出参（失败 400）：
{
  "success": false,
  "message": "创建失败",
  "data": { "category_name": ["品类名称已存在"] }
}
```

#### PATCH 修改品类

```
PATCH /api/categories/<id>/update/
Content-Type: application/json

入参（所有字段均为选填，至少传一项）：
{
  "category_name": "新名称",   // 修改名称
  "parent": 2                  // 修改父级，传 null 则提升为顶级
}

出参（成功 200）：
{
  "success": true,
  "message": "修改成功",
  "data": { "category_name": "新名称", "parent": 2 }
}

出参（失败 404）：
{
  "success": false,
  "message": "品类不存在或已被删除",
  "data": null
}
```

#### DELETE 删除品类

```
DELETE /api/categories/<id>/delete/

入参：无（id 在路径中）

出参（成功 200）：
{
  "success": true,
  "message": "删除成功",
  "data": null
}

副作用：直接子品类的 parent 自动改为被删品类的 parent（子品类上移一级）
```

---

### 7.2 CategoryAttrDef 品类属性定义接口

#### GET 查询指定品类的属性定义

```
GET /api/attr-defs/dir/?category_id=<id>

入参（Query Params）：
  category_id  必填，品类 ID

出参：
{
  "success": true,
  "data": [
    {
      "id": 1,
      "category_id": 2,
      "attr_name": "袖长",
      "value_type": "float",
      "is_required": true,
      "create_time": "..."
    }
  ]
}
```

#### POST 新增属性定义

```
POST /api/attr-defs/create/

入参：
{
  "category": 2,         // 必填，所属品类 ID
  "attr_name": "袖长",   // 必填，同一品类下唯一
  "value_type": "float", // 必填，可选值：str / int / float / bool
  "is_required": true    // 选填，默认 false
}
```

#### PATCH 修改属性定义

```
PATCH /api/attr-defs/<id>/update/

入参（只允许修改以下字段）：
{
  "attr_name": "新属性名",   // 选填
  "is_required": false      // 选填
}

注意：value_type 和 category 创建后不可修改
```

#### DELETE 删除属性定义

```
DELETE /api/attr-defs/<id>/delete/
```

---

### 7.3 Product 商品接口

#### GET 查询商品列表

```
GET /api/products/dir/
GET /api/products/dir/?category_id=<id>    // 可按品类筛选

出参：
{
  "data": [
    {
      "id": 1,
      "product_name": "大衣A",
      "category_id": 4,
      "product_price": "299.00",
      "product_image": "products/img.jpg",
      "product_stock": 100,
      "create_time": "..."
    }
  ]
}
```

#### POST 新增商品（含属性值）

```
POST /api/products/create/
Content-Type: multipart/form-data  （有图片时；纯 JSON 时用 application/json）

入参：
{
  "product_name":  "大衣A",   // 必填
  "category":      4,          // 必填，所属品类 ID，创建后不可修改
  "product_price": 299.00,     // 必填，不能为负数
  "product_image": <file>,     // 选填，图片文件
  "product_stock": 100,        // 选填，默认 0，不能为负数
  "attr_values":   "[{\"attr_def\":1,\"value_float\":82.5},{\"attr_def\":2,\"value_str\":\"红色\"}]"
                               // 选填，JSON 字符串（multipart 时）或数组（JSON 时）
                               // 每项 attr_def 对应一条属性定义，只填对应类型的值字段
}

处理流程：
  1. 校验商品基本信息
  2. 在事务内保存商品，获取 product.id
  3. 预校验所有属性值（Create 序列化器）
  4. 有任何属性值校验失败 → 整体事务回滚，返回错误
  5. 全部通过 → 批量保存属性值

出参（成功 201）：
{
  "success": true,
  "message": "创建成功",
  "data": { "id": 1, "product_name": "大衣A", ... }
}
```

#### PATCH 修改商品（含属性值）

```
PATCH /api/products/<id>/update/
Content-Type: application/json 或 multipart/form-data

入参（所有字段均为选填，不含 category）：
{
  "product_name":  "大衣A改",
  "product_price": 399.00,
  "product_stock": 50,
  "attr_values": [
    {"attr_def": 1, "value_float": 85.0},   // 已有记录 → 更新
    {"attr_def": 3, "value_str":  "蓝色"}   // 无记录   → 新建
  ]
}

处理逻辑：
  - 对每条 attr_value，按 (product, attr_def) 查找已有记录
  - 已有记录 → 使用 UpdateSerializer（partial=True）更新值
  - 无记录   → 使用 CreateSerializer 新建
  - 商品字段和属性值在同一事务内保存，任一失败全部回滚
```

#### DELETE 删除商品（级联删除属性值）

```
DELETE /api/products/<id>/delete/

副作用（2026-04-22 新增）：
  同一事务内将该商品的所有 ProductAttrValue 逻辑删除（is_delete=True），
  避免产生孤悬属性值记录，保持数据完整性。
```

---

### 7.4 ProductAttrValue 商品属性值接口

#### GET 查询商品的属性值

```
GET /api/attr-values/dir/?product_id=<id>

入参（Query Params）：
  product_id  必填，商品 ID
```

#### POST 新增属性值

```
POST /api/attr-values/create/

入参：
{
  "product": 1,          // 必填，商品 ID
  "attr_def": 1,         // 必填，属性定义 ID（必须属于该商品的品类）
  "value_str": null,     // 四选一，根据 attr_def.value_type 填对应字段
  "value_int": null,
  "value_float": 82.5,   // 例：袖长 82.5cm
  "value_bool": null
}

校验规则：
  - attr_def 必须属于该商品的品类
  - 若 is_required=true，对应值字段不能为 null
  - 其余三个值字段后端自动清空为 null
```

#### PATCH 修改属性值

```
PATCH /api/attr-values/<id>/update/

入参（只允许修改值字段）：
{
  "value_str": null,
  "value_int": null,
  "value_float": 85.0,
  "value_bool": null
}

注意：product 和 attr_def 创建后不可修改
```

#### ~~DELETE 删除属性值~~（已弃用）

```
[DEPRECATED] DELETE /api/attr-values/<id>/delete/

弃用原因（2026-04-22）：
  update_attr_value（PATCH）已可覆盖属性值的所有修改场景；
  单独的删除入口容易造成数据不完整（商品缺少必填属性值）。
  接口代码保留，HTTP 方法仍为 DELETE，仅通过注释声明弃用状态。
  请改用 PATCH /api/attr-values/<id>/update/ 维护属性值。
```

---

## 8. 踩坑记录

### 8.1 ⚠️ mysqlclient 在 Windows 上安装失败

**问题：** `pip install mysqlclient` 在 Windows 报错，需要 C++ 编译环境。

**解决：** 两种方案：
1. 安装 Visual Studio Build Tools 后重试
2. 改用 `PyMySQL`：
   ```python
   # manage.py 顶部添加
   import pymysql
   pymysql.install_as_MySQLdb()
   ```

### 8.2 ⚠️ Pillow 缺失导致 ImageField 报错

**问题：** Product 模型使用了 `ImageField`，启动时报 `Cannot use ImageField because Pillow is not installed`。

**解决：** `pip install Pillow`

### 8.3 ⚠️ STATICFILES_DIRS 指向不存在的目录

**问题：** settings.py 中 `STATICFILES_DIRS` 指向 `static/` 目录，但该目录不存在，启动时报警告。

**解决：** 注释掉该配置，等实际需要静态文件时再创建目录并开启。

### 8.4 ⚠️ 文件命名：dict.py → dicts.py

**问题：** 文件命名为 `dict.py` 时，`from app.dict import DeleteStatus` 与 Python 内置 `dict` 类型存在命名冲突，导致潜在的导入问题。

**解决：** 改名为 `dicts.py`。

### 8.5 ⚠️ UpdateSerializer 继承 CreateSerializer

**问题：** 最初写成 `ProductUpdateSerializer(ProductCreateSerializer)` 的继承关系，逻辑混乱（Update 并不"是一种" Create）。

**解决：** 改为 Mixin 模式，公共校验提取到 `ProductValidationMixin`，Create 和 Update 各自独立继承 Mixin。

### 8.6 ⚠️ validate_value_type 重复实现

**问题：** 在 `CategoryAttrDefCreateSerializer` 中手动实现了 `validate_value_type` 方法，与 DRF 的 choices 自动校验重复。

**解决：** 删除手动校验，DRF 在字段定义了 `choices` 时会自动校验合法性。

### 8.7 ⚠️ 项目结构问题：模块文件散落在 app 根目录

**问题：** 最初 `models.py`、`views.py`、`urls.py` 直接放在 `app/` 下，多模块混在一起。

**解决：** 每个业务模块独立建子目录（`app/category/`、`app/product/` 等），在 `settings.py` 中分别注册：
```python
INSTALLED_APPS = [
    'app.category',
    'app.category_attr_def',
    'app.product',
    'app.product_attr_value',
]
```

---

## 9. 强调与重点

### 🔑 逻辑删除贯穿全系统

所有表都有 `is_delete` 字段，所有查询都加 `is_delete=DeleteStatus.NORMAL` 条件，永远不做物理删除。已删除的数据名称可以被新数据复用（去重查询只查未删除的数据）。

### 🔑 parent_name 不入库

`parent_name` 是通过 `SerializerMethodField` 动态计算的，数据库中不存储冗余字段。若存入数据库，父级改名时需要同步更新所有子孙记录，造成数据一致性问题。

### 🔑 品类名称全局唯一

经讨论决定采用全局唯一（而非同级唯一），去重查询只过滤未删除的记录：
```python
Category.objects.filter(category_name=name, is_delete=DeleteStatus.NORMAL)
```

### 🔑 三处"创建后不可修改"约束

| 字段 | 所在模型 | 原因 |
|------|---------|------|
| `category` | Product | 修改品类会导致动态属性数据全部错乱 |
| `value_type` | CategoryAttrDef | 修改类型会破坏已有商品属性值数据 |
| `product` / `attr_def` | ProductAttrValue | 属性值与商品和属性定义强绑定 |

### 🔑 CategoryAttrDef.category → on_delete=CASCADE vs Product.category → on_delete=PROTECT

- 属性定义是品类的附属物，品类删除时属性定义一起删除（CASCADE）
- 商品是独立实体，品类下有商品时禁止删除品类（PROTECT），防止孤儿数据

### 🔑 Category.parent → on_delete=SET_NULL

`SET_NULL` 只对物理删除生效。本项目是逻辑删除，所以实际的上移逻辑需要在 `delete_category` 视图中手动处理。

---

## 10. 测试页面

### 访问地址

| 模块 | 地址 | 状态 |
|------|------|------|
| 品类 | http://127.0.0.1:8000/test/category/ | ✅ 已完成 |
| 品类属性定义 | http://127.0.0.1:8000/test/category_attr_def/ | ✅ 已完成 |
| 商品 | http://127.0.0.1:8000/test/product/ | ✅ 已完成（含动态属性字段，2026-04-22 更新） |
| 商品属性值 | http://127.0.0.1:8000/test/product_attr_value/ | ✅ 已完成（DELETE 面板已移除，2026-04-22 更新） |

### 测试页面技术方案

- 暗色主题，三栏布局（侧边导航 / 表单区 / 响应区）
- 下拉选择器替代手填 ID，实时从后端加载数据
- 响应区支持 JSON 视图和专属视图（品类为树形，属性定义为卡片列表）
- 增删改操作后自动刷新相关下拉选项
- Toast 通知、Loading 动画、请求耗时展示
- 通用路由：`test/<name>/` 自动映射 `templates/test/<name>.html`，新增测试页面无需修改路由

---

## 11. 未完成计划

### 近期任务

- [x] ~~完成 `product` 测试页面~~（2026-04-22 完成，含动态属性字段）
- [x] ~~完成 `product_attr_value` 测试页面~~（2026-04-22 完成，DELETE 面板已移除）
- [ ] 各模块接口联调测试
- [ ] 执行数据库迁移：`python manage.py makemigrations && python manage.py migrate`
- [ ] 创建管理员账号：`python manage.py createsuperuser`

### 中期任务

- [ ] 商品展示前端页面（仿 1688 商品列表 + 详情页）
- [ ] 基于品类属性的筛选过滤功能
- [ ] 商品图片上传与展示
- [ ] Django Admin 后台美化与配置

### 待讨论

- [ ] 品类删除后，其下商品如何处理（当前 Product.category 是 `on_delete=PROTECT`，即有商品时品类无法删除）
- [ ] 是否需要商品搜索功能（关键词搜索）
- [ ] 是否需要商品排序功能（按价格、库存等）

---

## 12. 2026-04-22 改造日志

> 本次改造在测试和代码审查阶段发现了若干设计缺陷与功能缺失，逐一修复并补充。
> 涉及文件：`product/views.py`、`product_attr_value/views.py`、`product_attr_value/serializers.py`、
> `category_attr_def/serializers.py`、`templates/test/product.html`、`templates/test/product_attr_value.html`

---

### 12.1 `product_attr_value/views.py` — 弃用 delete_attr_value 接口

**问题来源：** 代码审查时发现 `delete_attr_value` 接口与 `update_attr_value` 存在功能重叠，且单独删除属性值有数据完整性风险。

**问题描述：**
- `update_attr_value`（PATCH）已支持将属性值改为 null，功能上覆盖了"清除值"的诉求。
- 若通过 DELETE 直接删除一条 `ProductAttrValue` 记录，商品将缺少该属性的记录，
  当该属性定义日后被改为必填时会产生数据不一致。
- 直接暴露删除入口，容易在测试或前端调用时误删有效数据。

**改造方式：**
- 保留 `delete_attr_value` 函数和全部业务逻辑代码，**不删除代码**，确保可快速回滚。
- 保留 `methods=['DELETE']`，不改 HTTP 方法（改成 POST 在语义上是错的：POST 代表创建资源）。
- 在函数上方添加 `[DEPRECATED]` 注释块，说明弃用原因、日期和替代方案。

**改造后的作用：**
- 接口仍可正常响应 `DELETE /api/attr-values/<id>/delete/`，不破坏已有调用方。
- 通过注释明确标记，后续开发者不会继续扩展此入口。
- `templates/test/product_attr_value.html` 同步移除 DELETE 侧边栏导航和操作面板，
  从测试台入口层面降低误操作风险（见 12.6）。

**关于"弃用是否应改 HTTP 方法"的讨论：**

> 曾讨论是否应将 `methods=['DELETE']` 改为 `methods=['POST']` 来"移除 DELETE 面板"。
> 结论是**不应该**：
> - 改成 POST 会破坏 RESTful 语义（POST 表示创建，不表示删除）
> - 会立即破坏所有已经在使用 `DELETE` 方法的客户端
> - 正确做法是：保留 DELETE 方法，通过代码注释声明弃用，通过前端测试台移除操作入口

---

### 12.2 `product_attr_value/serializers.py` — `validate_value_by_type` 区分创建/修改

**问题来源：** 在测试 `update_product`（合并属性值修改）时发现，当 PATCH 请求的属性值数据中未包含值字段时，会误报"必填项为空"。

**问题描述：**

原函数签名：
```python
def validate_value_by_type(attrs, attr_def):
```

原函数不区分创建/修改模式，对所有调用一视同仁。在 `ProductAttrValueUpdateSerializer` 使用 `partial=True` 时，
若用户的请求体中包含了某个 `attr_def`，但没有附带该属性的值字段，`attrs` 中将不包含任何值字段（如 `value_str`）。

此时原函数会执行：
```python
if attr_def.is_required and attrs.get(expected_field) is None:
    raise ValidationError(...)   # ← 误报！数据库里明明有值，只是这次 PATCH 没带它
```

**问题根源：** PATCH partial 语义是"只更新传入的字段，未传的字段保持原值"，但原函数完全不知道"当前是 partial 更新"这个上下文。

**改造方式：**

新增 `is_partial=False` 参数，区分两种调用场景：

```python
def validate_value_by_type(attrs, attr_def, is_partial=False):
```

| 场景 | 行为 |
|---|---|
| `is_partial=False`（创建） | 与原来一致：检查必填，清空其他字段 |
| `is_partial=True`，且 `attrs` 中**没有任何值字段** | 直接 return，跳过全部值校验 |
| `is_partial=True`，且 `attrs` 中**有值字段** | 只校验/清空已传入的字段，不触碰未传入的字段 |

- `ProductAttrValueCreateSerializer.validate()` 调用不变（默认 `is_partial=False`）
- `ProductAttrValueUpdateSerializer.validate()` 改为传 `is_partial=True`

**改造后的作用：**
- 修复了 PATCH 更新属性值时，因未传值字段而误触发必填校验的 Bug。
- 保证了 partial update 的语义正确性：未传的字段不被校验，也不被清空覆盖。

---

### 12.3 `category_attr_def/serializers.py` — 必填属性定义的数据一致性保护

**问题来源：** 代码审查时发现，在品类已有商品的情况下，为该品类新增或修改必填属性定义，
会造成现有商品因缺少对应属性值而立即违反约束，但原代码对此没有任何拦截。

#### 12.3.1 Create：新增必填属性定义时检查品类是否有商品

**问题描述：**
- 一个品类下已有商品（如"大衣A"、"大衣B"）时，若新增一个 `is_required=True` 的属性定义（如"袖长"），
  这些已有商品在数据库中没有对应的 `ProductAttrValue` 记录。
- 数据从此处于不一致状态：商品应当具备必填属性，但数据库中根本没有该记录。

**改造方式：**

在 `CategoryAttrDefCreateSerializer` 中新增 `validate()` 方法：

```python
def validate(self, attrs):
    from app.product.models import Product   # 延迟导入，避免循环引用
    if attrs.get('is_required') and attrs.get('category'):
        if Product.objects.filter(category=attrs['category'], is_delete=False).exists():
            raise ValidationError({'is_required': '该品类下已有商品，不能新增必填属性定义...'})
    return attrs
```

**逻辑说明：**
- `is_required=False` 的属性定义可以随时新增，历史商品只是缺省该属性，属于正常的可选字段扩展。
- 只有 `is_required=True` 才需要拦截：因为此时新属性定义一定没有任何对应的属性值记录，
  所有现有商品都必然违反约束。

**关于延迟导入的说明：**
- `product_attr_value/models.py` 已通过 ForeignKey 引用了 `CategoryAttrDef`
- 如果 `category_attr_def/serializers.py` 在模块顶部导入 `Product`，则产生循环引用
- 使用在方法内部的延迟导入（`from app.product.models import Product`）可避免此问题，Django 常见做法

#### 12.3.2 Update：将 is_required 由 False 改为 True 时的精确检查

**问题描述：**
`CategoryAttrDefUpdateSerializer` 允许修改 `is_required` 字段。
若将一个已存在的属性定义从 `is_required=False` 改为 `True`，情况比 Create 更复杂：
- 该属性定义已存在，**部分商品可能已经填写**了该属性值
- 如果照搬 Create 的逻辑（"有商品就拦截"），会阻止一种合理的操作路径：
  先把所有商品的属性值补填完整，再把属性改为必填

**改造方式：**

在 `CategoryAttrDefUpdateSerializer` 中新增 `validate()` 方法，做**精确统计**：

```python
def validate(self, attrs):
    if attrs.get('is_required') is True and self.instance.is_required is False:
        from app.product.models import Product
        from app.product_attr_value.models import ProductAttrValue

        category = self.instance.category
        products_qs = Product.objects.filter(category=category, is_delete=False)
        if products_qs.exists():
            filled_ids = ProductAttrValue.objects.filter(
                attr_def=self.instance, is_delete=False
            ).values_list('product_id', flat=True)

            unfilled_count = products_qs.exclude(id__in=filled_ids).count()
            if unfilled_count > 0:
                raise ValidationError({'is_required': f'有 {unfilled_count} 件商品未填写此属性值...'})
    return attrs
```

**Create vs Update 校验策略对比：**

| | Create | Update |
|---|---|---|
| 触发条件 | 新建时 `is_required=True` | `is_required` 由 `False` 变为 `True` |
| 检查粒度 | 品类下有**任意商品**即拦截 | 精确统计**缺少属性值的商品数量** |
| 放行条件 | 品类下没有任何商品 | 品类下所有商品都已填写该属性值 |
| 原因 | 新属性定义没有任何属性值记录，全部商品必然违反约束 | 属性定义已存在，部分商品可能已填写，需区分对待 |
| 错误提示 | 建议先删除商品再操作 | 告知具体未填写的商品数量，提供两条出路 |

**错误信息设计：**

Update 的错误信息提供了两条明确的操作路径：
> `有 N 件商品尚未填写此属性值，将其改为必填会立即违反约束。`
> `请先为这些商品补填该属性值后再操作；`
> `或删除此品类下的所有商品，重新配置必填属性后再录入商品。`

---

### 12.4 `product/views.py` — 商品创建/修改合并属性值，删除级联

**问题来源：** 原来创建/修改商品和录入属性值是两个独立操作，前端需要先创建商品拿到 ID，再逐条提交属性值，操作割裂，体验差。

#### 12.4.1 create_product / update_product 合并属性值处理

**改造方式：**

新增两个辅助函数，提取重复逻辑：

```python
def _parse_attr_values(request_data):
    """
    从 request.data 中解析 attr_values 列表
    兼容 multipart/form-data（JSON 字符串）和 application/json（直接数组）两种提交方式
    """
    raw = request_data.get('attr_values', [])
    if isinstance(raw, str):
        raw = json.loads(raw)
    return raw if isinstance(raw, list) else []


def _validate_and_collect_attr_value_serializers(product_id, attr_values_raw):
    """
    预校验所有属性值，返回 (通过校验的序列化器列表, 错误字典)
    - 已有记录 → ProductAttrValueUpdateSerializer（partial=True）
    - 无记录   → ProductAttrValueCreateSerializer
    """
```

`create_product` 流程：
1. 校验商品字段
2. 进入事务，保存商品获得 ID
3. 预校验属性值，有误则 `transaction.set_rollback(True)` 回滚
4. 全部通过则批量保存属性值

`update_product` 流程：
1. 校验商品字段
2. 在事务**外**预校验属性值（减少事务持有时间）
3. 有误直接返回错误
4. 进入事务，保存商品字段 + 批量保存属性值

**关于 multipart 传递 attr_values 的说明：**

商品创建需要支持图片上传，必须用 `multipart/form-data`。但 FormData 不支持直接传递 JSON 数组。
解决方案：前端将 `attr_values` 序列化为 JSON 字符串再 `append` 到 FormData，后端用 `json.loads()` 解析。

```javascript
// 前端
fd.append('attr_values', JSON.stringify(attrValues));

// 后端 _parse_attr_values
if isinstance(raw, str):
    raw = json.loads(raw)
```

#### 12.4.2 delete_product 级联删除属性值

**问题描述：** 原来逻辑删除商品时，其关联的 `ProductAttrValue` 记录仍然存在（`is_delete=False`）。
这些孤悬记录无法通过商品列表访问，却占据数据库空间，且会被 `category_attr_def` 的删除保护误判为"有商品使用了该属性定义"。

**改造方式：**

```python
with transaction.atomic():
    ProductAttrValue.objects.filter(
        product=product,
        is_delete=DeleteStatus.NORMAL
    ).update(is_delete=DeleteStatus.DELETED)    # 先级联删除属性值

    product.is_delete = DeleteStatus.DELETED
    product.save()                              # 再删除商品
```

使用事务保证原子性：商品和属性值要么同时删除，要么同时不删除。

---

### 12.5 `templates/test/product.html` — 创建/修改表单加入动态属性字段

**问题来源：** 原测试页面创建/修改商品时，没有属性值输入区，只能通过单独的 product_attr_value 页面录入属性值，与合并接口的改造目标不匹配。

**改造内容：**

**CSS 新增：**
- `.attrs-section` — 属性字段区容器，初始隐藏
- `.type-badge` — 属性类型标签（str/int/float/bool 不同颜色）
- `.toggle-row` / `.toggle` — 布尔值开关样式

**JS 新增函数：**

| 函数 | 作用 |
|---|---|
| `renderAttrFields(containerId, attrDefs, existingMap)` | 根据属性定义列表渲染输入框，支持预填现有值（修改时用） |
| `collectAttrValues(containerId)` | 遍历容器内所有属性输入框，收集并组装成 `attr_values` 数组 |
| `onCreateCategoryChange()` | 品类选择时调用，加载该品类的属性定义并渲染输入框 |
| `onUpdateProductChange()` | 商品选择时调用，并发加载属性定义和现有属性值，预填输入框 |

**创建面板交互流程：**
1. 用户选择品类 → 触发 `onCreateCategoryChange()`
2. 请求 `GET /api/attr-defs/dir/?category_id=<id>`
3. 根据每个属性的 `value_type` 渲染对应输入框（文本/数字/开关）
4. 提交时 `collectAttrValues()` 收集数据，JSON 序列化后附加到 FormData

**修改面板交互流程：**
1. 用户选择商品 → 触发 `onUpdateProductChange()`
2. **并发**请求属性定义列表 + 该商品的现有属性值（`Promise.all`）
3. 构建 `{attrDefId → attrValue}` 映射，预填入输入框（含现有值）
4. 提交时同样收集 `attr_values`，有图片用 multipart，无图片用 JSON

---

### 12.6 `templates/test/product_attr_value.html` — 移除 DELETE 面板

**问题来源：** `delete_attr_value` 接口已弃用，但测试页面仍然显示 DELETE 操作面板，容易误触发。

**改造内容：**

从测试台 UI 层面移除所有 DELETE 相关元素：

| 移除内容 | 位置 |
|---|---|
| DELETE 侧边栏导航项 | `.sidebar` 内 |
| `header-delete` 头部区 | `.form-area` 内 |
| `panel-delete` 表单面板（含商品/属性值下拉、确认删除按钮） | `.form-body` 内 |
| `deleteAttrValue()` JS 函数 | `<script>` 内 |
| `'delete'` 在 `switchPanel` 中的引用 | JS `switchPanel` 函数 |
| `'d-product'` 在 `populateProductSelects` 中的引用 | JS `populateProductSelects` 函数 |

所有移除位置均替换为 HTML 注释，说明移除原因，便于日后追溯。

---

### 12.7 讨论记录：delete 接口弃用的正确方式

**背景：** 在改造过程中，曾讨论"如何正确地弃用一个接口"。

**错误做法（已回滚）：**
将 `methods=['DELETE']` 改为 `methods=['POST']`，理由是"移除 DRF Browsable API 的 DELETE 面板"。

**为什么这样做是错的：**
1. **语义错误**：POST 在 RESTful 语义中代表"创建资源"，用 POST 做删除操作是语义混乱的。
2. **破坏兼容性**：所有已经在使用 `DELETE /api/attr-values/<id>/delete/` 的客户端会立即收到 405 Method Not Allowed，造成不可预期的故障。
3. **治标不治本**：DRF Browsable API 的 DELETE 面板只是一个开发工具，不是真正需要解决的问题。

**正确做法：**
1. **代码层面**：保留全部代码和 HTTP 方法，在函数和 docstring 中添加 `[DEPRECATED]` 注释，注明弃用原因、日期和替代接口。
2. **前端层面**：在测试台中移除 DELETE 操作面板入口，从用户使用路径上消除误操作风险。
3. **不需要**：改 HTTP 方法、返回 410 状态码、修改路由。

**结论：弃用 ≠ 删除；弃用 ≠ 改方法。代码保留，注释标记，前端隐藏入口，是最稳妥的弃用方式。**
