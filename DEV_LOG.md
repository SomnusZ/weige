# 微格商品展示网站 · 开发日志

> 最近更新：2026-05-04 ｜ 技术栈：Django 5.2 + DRF + MySQL 8
> 项目地址：https://github.com/SomnusZ/weige.git

---

## 目录

1. [项目背景与目标](#1-项目背景与目标)
2. [架构决策](#2-架构决策)
3. [数据库表结构](#3-数据库表结构)
4. [项目目录结构](#4-项目目录结构)
5. [公共基础设施](#5-公共基础设施)
6. [核心模块实现要点](#6-核心模块实现要点)
7. [接口文档](#7-接口文档)
8. [踩坑记录](#8-踩坑记录)
9. [变更历史](#9-变更历史)
10. [2026-05-03 商品详情弹窗 + 关键词搜索](#10-2026-05-03-商品详情弹窗--关键词搜索)
11. [2026-05-04 按属性动态筛选](#11-2026-05-04-按属性动态筛选)
12. [2026-05-04 商品图片显示修复](#12-2026-05-04-商品图片显示修复)

---

## 1. 项目背景与目标

仿照 1688.com 商品展示页，开发**商品展示与管理网站**。

核心特点：
- 商品种类繁多，不同品类属性完全不同（大衣有袖长，手机有内存）
- 支持按属性**筛选过滤**商品（EAV 动态属性）
- 管理员通过自定义后台管理数据，前台游客无需登录即可浏览

---

## 2. 架构决策

### 2.1 EAV 动态属性模式

**问题：** 不同品类商品的属性完全不同，无法用宽表存储。

| 方案 | 缺点 |
|------|------|
| 宽表（几百字段）| 大量 NULL，无法扩展 |
| JSON 字段 | 无法做数据库级筛选 |
| **EAV** ✅ | 稍复杂，但灵活且可筛选 |

**实现：**
1. `CategoryAttrDef`：定义"大衣这个品类有一个叫袖长的属性，类型是 float"
2. `ProductAttrValue`：存储"大衣A 的袖长值是 82.5"

### 2.2 属性值分列存储

所有属性值按类型分列存储，同一条记录只有一列有值：

```
value_str / value_int / value_float / value_bool
```

原因：存成统一字符串则无法做数值比较筛选（如 `价格 < 100`）。

### 2.3 RESTful 接口规范

全部采用 `ViewSet + @action`，统一命名：

```
GET    /api/categories/dir/
POST   /api/categories/create/
PATCH  /api/categories/<id>/update/
DELETE /api/categories/<id>/delete/
```

### 2.4 序列化器 Mixin 模式

```python
class ProductValidationMixin:          # 公共校验（名称非空、价格>=0 等）
    ...

class ProductCreateSerializer(ProductValidationMixin, ModelSerializer): ...
class ProductUpdateSerializer(ProductValidationMixin, ModelSerializer): ...
```

避免 Update 继承 Create 的语义混乱（Update 并不"是一种" Create）。

### 2.5 三处"创建后不可修改"约束

| 字段 | 所在模型 | 原因 |
|------|---------|------|
| `category` | Product | 修改品类会导致动态属性数据全部错乱 |
| `value_type` | CategoryAttrDef | 修改类型会破坏已有商品属性值数据 |
| `product` / `attr_def` | ProductAttrValue | 属性值与商品和属性定义强绑定 |

### 2.6 权限体系

- 全局默认：`IsAuthenticated`（需登录）
- 前台公开接口单独加：`permission_classes=[AllowAny]`
- JWT 认证（simplejwt）：access token 2小时，refresh token 7天

### 2.7 关键设计原则

- **逻辑删除贯穿全系统**：所有表有 `is_delete`，永不物理删除，已删名称可复用
- **parent_name 不入库**：由 `SerializerMethodField` 动态计算，避免冗余
- **品类名称全局唯一**（任何层级不重名）
- `CategoryAttrDef.category → CASCADE`（属性定义是品类附属物）
- `Product.category → PROTECT`（有商品时禁止删除品类）
- `Category.parent → SET_NULL`（仅对物理删除生效，逻辑删除需在 view 层手动上移子品类）

---

## 3. 数据库表结构

### Category（品类表）

```python
category_name = CharField(max_length=100, unique=True)   # 全局唯一
parent        = ForeignKey('self', null=True, on_delete=SET_NULL, related_name='children')
create_time   = DateTimeField(auto_now_add=True)
is_delete     = BooleanField(default=False)
```

删除时：直接子品类的 `parent` 改为被删品类的 `parent`（子品类上移一级）。

### CategoryAttrDef（品类属性定义表）

```python
category    = ForeignKey(Category, on_delete=CASCADE, related_name='attr_defs')
attr_name   = CharField(max_length=100)
value_type  = CharField(choices=['str','int','float','bool'])
is_required = BooleanField(default=False)
is_delete   = BooleanField(default=False)

unique_together = [('category', 'attr_name')]
```

约束：`value_type` 和 `category` 创建后不可修改。

### Product（商品表）

```python
product_name  = CharField(max_length=200)
category      = ForeignKey(Category, on_delete=PROTECT, related_name='products')
product_price = DecimalField(max_digits=10, decimal_places=2)
product_image = ImageField(upload_to='products/', null=True, blank=True)
product_stock = IntegerField(default=0)
create_time   = DateTimeField(auto_now_add=True)
is_delete     = BooleanField(default=False)

ordering = ['-create_time']
```

约束：`category` 创建后不可修改。

### ProductAttrValue（商品属性值表）

```python
product  = ForeignKey(Product, on_delete=CASCADE, related_name='attr_values')
attr_def = ForeignKey(CategoryAttrDef, on_delete=CASCADE)
value_str   = CharField(max_length=500, null=True, blank=True)
value_int   = models.IntegerField(null=True, blank=True)
value_float = FloatField(null=True, blank=True)
value_bool  = BooleanField(null=True, blank=True)
is_delete   = BooleanField(default=False)

unique_together = [('product', 'attr_def')]
```

写入时校验：`attr_def` 必须属于该商品的品类；非对应类型的字段强制清空为 NULL。

### 表关系总览

```
Category ──(1:N)── CategoryAttrDef
    │
   (1:N)
    │
Product ──(1:N)── ProductAttrValue ──(N:1)── CategoryAttrDef
```

---

## 4. 项目目录结构

```
weige/
├── manage.py
├── DEV_LOG.md
├── weige/
│   ├── settings.py          ← DB、时区、MEDIA、JWT、DRF 配置
│   └── urls.py              ← 主路由（含媒体文件路由）
├── app/
│   ├── dicts.py             ← DeleteStatus / AttrValueType / ATTR_TYPE_FIELD_MAP
│   ├── utils.py             ← success_response / error_response
│   ├── admin_views.py       ← 登录页/dashboard页/登录API
│   ├── test_views.py        ← 通用测试页路由（test/<name>/）
│   ├── user/                ← AbstractBaseUser + JWT，phone 登录
│   ├── category/
│   ├── category_attr_def/
│   ├── product/
│   └── product_attr_value/
├── templates/
│   ├── login.html           ← 管理员登录页
│   ├── dashboard.html       ← 管理后台（品类/属性/商品/属性值四模块）
│   ├── products.html        ← 前台商品展示页（游客可访问）
│   └── test/                ← 开发期测试页（category/product/attr 等）
└── media/
    └── products/            ← 商品图片（首次上传时自动创建）
```

---

## 5. 公共基础设施

### 统一响应格式（app/utils.py）

```python
# 成功
{ "success": True,  "message": "操作成功", "data": {...} }
# 失败
{ "success": False, "message": "创建失败", "data": {"field": ["错误信息"]} }

def success_response(data=None, message="操作成功", status_code=200): ...
def error_response(message="操作失败", status_code=400, errors=None): ...
```

### 全局字典项（app/dicts.py）

```python
class DeleteStatus:
    NORMAL  = False
    DELETED = True

class AttrValueType:
    STR = 'str' / INT = 'int' / FLOAT = 'float' / BOOL = 'bool'

ATTR_TYPE_FIELD_MAP = {
    'str': 'value_str', 'int': 'value_int',
    'float': 'value_float', 'bool': 'value_bool',
}
```

> ⚠️ 文件名不能叫 `dict.py`，会与 Python 内置 `dict` 冲突，改为 `dicts.py`。

### 媒体文件配置（settings.py + urls.py）

```python
# settings.py
MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# urls.py（开发环境）
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

---

## 6. 核心模块实现要点

### 6.1 品类删除：子品类上移

```python
# 直接子品类上移一级
Category.objects.filter(parent=category, is_delete=False).update(parent=category.parent)
category.is_delete = True
category.save()
```

### 6.2 必填属性定义的数据一致性保护

- **新增必填属性定义**：若该品类已有商品，拒绝操作（新属性定义没有任何属性值记录）
- **将 is_required 由 False 改 True**：精确统计未填写该属性的商品数量，若 > 0 则拒绝并给出提示

### 6.3 商品创建/修改合并属性值（事务原子保存）

```python
# 兼容 multipart（图片上传）和 application/json 两种提交方式
def _parse_attr_values(request_data): ...

# 预校验：已有记录→Update序列化器，无记录→Create序列化器
def _validate_and_collect_attr_value_serializers(product_id, attr_values_raw): ...
```

`create_product`：先保存商品拿 ID → 预校验属性值 → 有误则 `set_rollback(True)` 回滚。

`update_product`：事务**外**预校验（减少锁持有时间）→ 事务内一次性保存。

### 6.4 商品删除：级联逻辑删除属性值

```python
with transaction.atomic():
    ProductAttrValue.objects.filter(product=product, is_delete=False).update(is_delete=True)
    product.is_delete = True
    product.save()
```

### 6.5 validate_value_by_type（is_partial 区分创建/修改）

| 场景 | 行为 |
|------|------|
| `is_partial=False`（创建）| 检查必填，清空其他类型字段 |
| `is_partial=True`，未传任何值字段 | 直接 return，不触发校验 |
| `is_partial=True`，传了值字段 | 只校验/清空已传入字段 |

### 6.6 用户认证

- `AbstractBaseUser + PermissionsMixin`，登录字段改为 `phone`
- `authenticate()` 必须传 `phone=phone`（与 `USERNAME_FIELD` 一致），传 `username=` 会返回 None
- JWT 存储在 localStorage，所有管理接口请求通过 `authFetch()` 自动附加 `Authorization: Bearer <token>`

---

## 7. 接口文档

Base URL：`http://127.0.0.1:8000/api` ｜ 响应格式：`{success, message, data}`

### 品类（Categories）

| Method | Path | Auth | 说明 |
|--------|------|------|------|
| GET | `/categories/dir/` | 需登录 | 查询所有品类（平铺列表，含 parent_id） |
| GET | `/categories/public/` | 公开 | 同上，游客可访问 |
| POST | `/categories/create/` | 需登录 | 新增品类，`category_name` 全局唯一 |
| PATCH | `/categories/<id>/update/` | 需登录 | 修改名称或父级，含循环引用校验 |
| DELETE | `/categories/<id>/delete/` | 需登录 | 逻辑删除，子品类自动上移 |

### 品类属性定义（AttrDefs）

| Method | Path | Auth | 说明 |
|--------|------|------|------|
| GET | `/attr-defs/dir/?category_id=<id>` | 公开 | 查询指定品类的属性定义 |
| POST | `/attr-defs/create/` | 需登录 | 新增，必填属性需检查品类是否有商品 |
| PATCH | `/attr-defs/<id>/update/` | 需登录 | 只允许改 `attr_name` / `is_required`，`is_required: F→T` 需精确检查 |
| DELETE | `/attr-defs/<id>/delete/` | 需登录 | 逻辑删除 |

### 商品（Products）

| Method | Path | Auth | 说明 |
|--------|------|------|------|
| GET | `/products/public/` | 公开 | 前台商品列表，支持 `?category_id=&q=&attr_<id>=` |
| GET | `/products/filter-options/?category_id=<id>` | 公开 | 返回品类属性的去重值列表，供筛选面板用 |
| GET | `/products/<id>/detail/` | 公开 | 商品详情（含品类路径、全部属性值） |
| GET | `/products/dir/` | 需登录 | 后台商品列表，支持 `?category_id=` |
| POST | `/products/create/` | 需登录 | 新增商品，multipart，同时提交 `attr_values` |
| PATCH | `/products/<id>/update/` | 需登录 | 修改商品，同时更新/新增属性值 |
| DELETE | `/products/<id>/delete/` | 需登录 | 逻辑删除，级联删除属性值 |

**public 接口筛选参数：**
- `category_id=<id>`：品类筛选，含所有子孙品类
- `q=<keyword>`：商品名称模糊搜索（icontains）
- `attr_<id>=<val>`：属性值筛选，同属性多值 OR，不同属性 AND

### 商品属性值（AttrValues）

| Method | Path | Auth | 说明 |
|--------|------|------|------|
| GET | `/attr-values/dir/?product_id=<id>` | 需登录 | 查询商品的所有属性值 |
| POST | `/attr-values/create/` | 需登录 | 新增属性值（通常通过商品接口合并提交） |
| PATCH | `/attr-values/<id>/update/` | 需登录 | 修改属性值 |
| DELETE | `/attr-values/<id>/delete/` | 需登录 | ⚠️ 已弃用，改用商品接口合并提交 |

### 认证

| Method | Path | Auth | 说明 |
|--------|------|------|------|
| POST | `/api/auth/login/` | 公开 | 手机号+密码登录，返回 access/refresh token |

---

## 8. 踩坑记录

| # | 问题 | 解决方案 |
|---|------|---------|
| 1 | `mysqlclient` Windows 安装失败 | 改用 `PyMySQL`：`pymysql.install_as_MySQLdb()` |
| 2 | `ImageField` 报 Pillow 缺失 | `pip install Pillow` |
| 3 | `STATICFILES_DIRS` 指向不存在目录 | 注释掉，等实际有静态文件再开启 |
| 4 | `dict.py` 与内置 `dict` 冲突 | 改名为 `dicts.py` |
| 5 | `UpdateSerializer` 继承 `CreateSerializer` 语义混乱 | 改为 Mixin 模式 |
| 6 | DRF choices 字段手动写了重复校验 | 删除手动 `validate_value_type`，DRF 自动校验 |
| 7 | 模块文件散落在 app 根目录 | 每个业务模块独立建子目录，`settings.py` 分别注册 |
| 8 | `AUTH_USER_MODEL` 新增导致迁移循环依赖 | 临时注释 `django.contrib.admin`，先跑 `migrate user`，再恢复 |
| 9 | `authenticate()` 传 `username=` 永远返回 None | 必须传 `phone=phone`（与 `USERNAME_FIELD` 一致） |
| 10 | `app_label` 未声明导致嵌套包 App 报错 | 在 `User.Meta` 中显式声明 `app_label = 'user'` |
| 11 | `ProductListSerializer` 返回相对路径，图片 404 | 改为 `SerializerMethodField` 返回绝对 URL，view 层传入 `context={'request': request}` |

---

## 9. 变更历史

| 日期 | 主要内容 |
|------|---------|
| 2026-04-21 | 项目初始化，EAV 四表结构设计，四模块基础 CRUD 接口 |
| 2026-04-22 | 弃用独立 `delete_attr_value` 接口；`validate_value_by_type` 新增 `is_partial` 参数修复 PATCH 校验；品类有商品时拦截新增必填属性定义；商品创建/修改合并属性值（事务原子保存）；商品删除级联删除属性值；测试页面同步更新 |
| 2026-04-27 | 用户模块（`AbstractBaseUser`，phone 登录）；JWT 认证（simplejwt）；登录页 `login.html`；管理后台 `dashboard.html` |
| 2026-04-30 | 全局权限改为 `IsAuthenticated`；前台公开接口加 `AllowAny`；管理后台 dashboard 重设计（三栏布局，支持品类树、属性管理、商品卡片） |
| 2026-05-01 | 管理后台 UI 迭代（品类有商品时拒绝删除，显示明确提示）；前台商品展示页 `products.html`（瀑布流卡片，品类筛选，`ProductPublicSerializer` 含属性值） |
| 2026-05-03 | 商品详情弹窗（小红书风格，左图右文，复用已加载数据）；关键词搜索（`icontains`，`?q=` 参数） |
| 2026-05-04 | 按品类属性动态筛选（`filter-options` 接口 + `public_list` 支持 `attr_<id>=` 参数 + 前端左侧复选框面板）；`ProductListSerializer` 图片 URL 修复 |
| 2026-05-24 | 商品多图改造（新建 `ProductImage` 表，主图指定，拖拽排序，最多 9 张）；前台详情弹窗改为轮播图（圆点指示器，键盘导航） |

---

## 10. 2026-05-03 商品详情弹窗 + 关键词搜索

### 10.1 ProductPublicSerializer 补全价格与库存

在 `Meta.fields` 中加入 `product_price`、`product_stock`，供前台弹窗展示。

### 10.2 商品详情弹窗（Modal）

**方案：** 点击卡片触发 Modal，从 `currentProducts`（已加载数据）中取值，**无额外 API 请求**。

**布局（小红书风格）：**
- 桌面：左侧图片 50% + 右侧信息面板（名称、价格、库存、属性列表）
- 移动端（≤680px）：上图下文堆叠

**关闭方式：** 关闭按钮 / 点击遮罩 / ESC 键

### 10.3 关键词搜索

**后端（`public_list`）：**
```python
keyword = request.query_params.get('q', '').strip()
if keyword:
    queryset = queryset.filter(product_name__icontains=keyword)
```

**前端：**
```javascript
let activeKeyword = '';
// 搜索与品类筛选联合过滤
const params = new URLSearchParams();
if (activeCatId)   params.set('category_id', activeCatId);
if (activeKeyword) params.set('q', activeKeyword);
```

支持 Enter 键触发，与品类筛选独立状态、可同时生效。

---

## 11. 2026-05-04 按属性动态筛选

### 11.1 filter-options 接口

```
GET /api/products/filter-options/?category_id=<id>   （AllowAny）
```

返回该品类下各属性定义及实际存在的去重值：

```json
[
  { "attr_def_id": 1, "attr_name": "颜色", "value_type": "str", "values": ["红色", "蓝色"] }
]
```

实现要点：
- `distinct().order_by()` 查去重值，过滤 `isnull=False`
- `bool` 类型转为 `"是"/"否"` 字符串
- 无商品数据的属性跳过不展示

### 11.2 public_list 属性筛选参数

```
?attr_1=红色&attr_1=蓝色&attr_2=XL
```

- 同属性多值：`getlist(key)` → `__in` → **OR**
- 不同属性：链式 `filter` → **AND**
- 按 `value_type` 路由到对应字段（`ATTR_TYPE_FIELD_MAP`）
- `bool` 类型：前端传 `"是"/"否"` → 后端转 `True/False`

### 11.3 前端左侧筛选面板

**布局：**
```
.page-layout (flex)
├── .filter-sidebar (192px, sticky top:120px)   ← 选中叶子品类时显示
└── .main (flex:1)
```

移动端（≤768px）侧边栏强制隐藏。

**状态：**
```javascript
let activeAttrFilters = {};  // { attr_def_id: Set<string> }
```

**核心函数：**

| 函数 | 职责 |
|------|------|
| `loadFilterOptions(catId)` | 请求接口，有数据则渲染侧边栏，否则隐藏 |
| `renderSidebar(groups)` | 渲染属性分组复选框 |
| `onAttrFilterChange(e)` | 更新 `activeAttrFilters`，触发 `loadProducts()` |
| `clearAllFilters()` | 清空所有筛选，重载商品 |

切换品类时自动重置 `activeAttrFilters = {}`，`loadFilterOptions` 与 `loadProducts` 并发执行。

---

## 12. 2026-05-04 商品图片显示修复

### 问题

`ProductListSerializer` 的 `product_image` 字段直接返回原始相对路径（如 `products/xxx.jpg`），dashboard 前端拼接 `<img src="products/xxx.jpg">` 路径错误，图片 404。

### 修复（方案 A：序列化器统一返回绝对 URL）

**`app/product/serializers.py`：**

```python
class ProductListSerializer(serializers.ModelSerializer):
    product_image_url = serializers.SerializerMethodField()

    def get_product_image_url(self, obj):
        if not obj.product_image:
            return None
        request = self.context.get('request')
        url = obj.product_image.url      # → /media/products/xxx.jpg
        return request.build_absolute_uri(url) if request else url

    class Meta:
        model = Product
        fields = ['id', 'product_name', 'category_id', 'product_price',
                  'product_image_url', 'product_stock', 'create_time']
```

**`app/product/views.py`（dir_product）：**

```python
serializer = ProductListSerializer(queryset, many=True, context={'request': request})
```

**`templates/dashboard.html`：**

```javascript
// 旧：p.product_image（相对路径）
// 新：p.product_image_url（绝对 URL）
const imgHtml = p.product_image_url
  ? `<img src="${p.product_image_url}" ...>` : '📦';
```

与 `ProductPublicSerializer.get_product_image_url` 保持一致设计，换生产域名无需改前端。

### 图片上传链路（当前完整状态）

| 环节 | 状态 |
|------|------|
| `ImageField(upload_to='products/')` | ✅ |
| `MEDIA_URL / MEDIA_ROOT` 配置 | ✅ |
| 开发环境媒体路由（`DEBUG=True`） | ✅ |
| Pillow v12.0.0 | ✅ |
| 创建/修改序列化器接收文件 | ✅ |
| 后台/前台序列化器返回绝对 URL | ✅ |
| `media/` 目录 | 首次上传时自动创建 |

---

*待办：图片存储 OSS 优化（生产环境再做）*
