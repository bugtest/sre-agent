# API 文档 - {项目名称}

**版本**: 1.0.0  
**最后更新**: YYYY-MM-DD  
**状态**: draft/review/published

---

## 1. 概述

### 1.1 基础信息
- **Base URL**: `/api/v1`
- **认证方式**: Bearer Token / API Key
- **数据格式**: JSON
- **字符编码**: UTF-8

### 1.2 通用响应格式
```json
{
  "code": 0,
  "message": "success",
  "data": {},
  "timestamp": 1234567890
}
```

### 1.3 错误码定义
| 错误码 | 描述 | HTTP 状态码 |
|--------|------|-------------|
| 0 | 成功 | 200 |
| 40001 | 参数错误 | 400 |
| 40101 | 未授权 | 401 |
| 40301 | 禁止访问 | 403 |
| 40401 | 资源不存在 | 404 |
| 50001 | 服务器错误 | 500 |

---

## 2. 认证

### 2.1 获取 Token
```http
POST /api/v1/auth/login
Content-Type: application/json

{
  "username": "string",
  "password": "string"
}
```

**响应**:
```json
{
  "code": 0,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "expires_in": 3600
  }
}
```

### 2.2 使用 Token
```http
GET /api/v1/resource
Authorization: Bearer {token}
```

---

## 3. API 端点

### 3.1 {资源名称}

#### GET /{resource}
获取资源列表

**查询参数**:
| 参数 | 类型 | 必填 | 描述 | 示例 |
|------|------|------|------|------|
| page | int | 否 | 页码 | 1 |
| size | int | 否 | 每页数量 | 20 |
| sort | string | 否 | 排序字段 | created_at |

**响应**:
```json
{
  "code": 0,
  "data": {
    "items": [],
    "total": 100,
    "page": 1,
    "size": 20
  }
}
```

#### GET /{resource}/{id}
获取单个资源

**路径参数**:
| 参数 | 类型 | 描述 |
|------|------|------|
| id | string | 资源 ID |

**响应**:
```json
{
  "code": 0,
  "data": {
    "id": "123",
    "name": "example"
  }
}
```

#### POST /{resource}
创建资源

**请求体**:
```json
{
  "name": "string",
  "description": "string"
}
```

**响应**:
```json
{
  "code": 0,
  "data": {
    "id": "123",
    "created_at": "2026-03-14T08:00:00Z"
  }
}
```

#### PUT /{resource}/{id}
更新资源

**请求体**:
```json
{
  "name": "string",
  "description": "string"
}
```

#### DELETE /{resource}/{id}
删除资源

**响应**:
```json
{
  "code": 0,
  "message": "deleted"
}
```

---

## 4. 速率限制

| 端点 | 限制 |
|------|------|
| 默认 | 100 次/分钟 |
| /auth/login | 10 次/分钟 |

---

## 5. 版本控制

API 版本通过 URL 路径控制：
- `/api/v1/` - 当前版本
- `/api/v2/` - 下一版本（规划中）

---

## 6. 变更日志

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| 1.0.0 | 2026-03-14 | 初始版本 |
