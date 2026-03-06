Step1：ERP Kernel（最关键）

目标：

构建 永远不会轻易改变的系统基座。

Kernel 提供：

company isolation
RBAC permission
document state machine
audit logging
system configuration
document numbering

这些全部来自你的 spec 的核心基础功能。 

需求单

Step1 目录结构（backend）
backend/
  apps/
    core/
    company/
    auth/
    doc/
    audit/
    config/

  shared/
    models/
    querysets/
    services/
    constants/
    exceptions/

  api/
  config/
Step1 Node Graph

Step1 可以拆为 6 个 node_spec。

STEP1_KERNEL
 ├── NODE1_BASE_INFRA
 ├── NODE2_COMPANY_SCOPE
 ├── NODE3_AUTH_RBAC
 ├── NODE4_DOCUMENT_STATE_ENGINE
 ├── NODE5_AUDIT_SYSTEM
 └── NODE6_SYSTEM_CONFIG
NODE1_BASE_INFRA
目标

构建所有模块共享的 基础设施层。

目录
shared/
  models/
  querysets/
  services/
  exceptions/
  constants/
功能

BaseModel

统一字段：

id
company_id
created_at
created_by
updated_at
updated_by
is_deleted

这与你的数据模型规范一致。 

spec

QuerySet Layer

CompanyQuerySet

职责：

for_company()
active()

自动过滤：

company_id
is_deleted
BaseService

统一：

transaction
logging
error handling
常量
DOC_STATUS
PERMISSIONS
MODULES
NODE2_COMPANY_SCOPE
目标

实现 多公司隔离机制。

模型
Company
CompanyMembership
CompanyModule

关系：

User
 ↓
CompanyMembership
 ↓
Company
 ↓
Role
Company Scope 机制

每个请求必须确定：

current_company

来源：

X-Company-ID

验证：

User ∈ CompanyMembership

否则：

403
Middleware
resolve_company_scope

流程：

request
 ↓
auth
 ↓
company scope
 ↓
permission guard
NODE3_AUTH_RBAC
目标

实现权限系统。

RBAC 模型：

User
Role
Permission
RolePermission

权限格式：

module.resource.action

例子：

purchase.po.create
purchase.po.confirm
sales.order.submit
inventory.stock.adjust
权限检查

Permission Guard

统一入口：

check_permission(user, action, resource)

检查：

role permissions
company module enabled
NODE4_DOCUMENT_STATE_ENGINE

ERP 所有单据必须遵守：

DRAFT
SUBMITTED
CONFIRMED
COMPLETED
CANCELLED

你的 spec 已明确统一生命周期。 

spec

状态机核心模型
DocumentStateMachineDef
DocumentTransitionLog

状态迁移：

DRAFT → SUBMITTED
SUBMITTED → CONFIRMED
CONFIRMED → COMPLETED
ANY → CANCELLED
State Engine

统一处理：

validate transition
check permission
write transition log
update state
NODE5_AUDIT_SYSTEM

审计系统负责记录：

who
did what
to which resource
when

模型：

AuditEvent
AuditFieldDiff

来自你的 spec。 

spec

审计记录范围
CRUD
state transitions
login
export
configuration changes
NODE6_SYSTEM_CONFIG

系统配置模块。

模型：

SystemConfig

字段：

key
value
scope
description

配置示例：

inventory.allow_negative
default_currency
production.scrap_rate
Step1 完成后系统能力

完成 Kernel 后系统拥有：

multi company ERP
RBAC
document lifecycle
audit trail
configurable rules

此时 ERP 已具备：

Framework-level foundation
Step2 预告（下一阶段）

完成 Kernel 后，下一步是：

Step2 Master Data

模块：

material
warehouse
uom
category

因为：

inventory
purchase
sales
production

全部依赖这些主数据。