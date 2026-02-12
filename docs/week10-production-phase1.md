# Week 10: RBAC, Multi-tenancy, Production Hardening - Phase 1

## Обзор

Phase 1 реализует фундаментальные компоненты безопасности для production deployment:
- JWT authentication
- RBAC (Role-Based Access Control)
- FastAPI middleware для защиты endpoints

## Компоненты

### 1. JWT Authentication (`auth/jwt_handler.py`)

**Функциональность:**
- Генерация JWT токенов с expiration
- Валидация и декодирование токенов
- HS256 algorithm
- Secret key из environment variable

**Поля токена:**
```python
{
    "user_id": str,
    "email": str,
    "role": str,  # admin/operator/viewer
    "tenant_id": str,
    "exp": int  # Unix timestamp
}
```

**Использование:**
```python
from auth.jwt_handler import jwt_handler

# Create token
token = jwt_handler.create_token(
    user_id="user123",
    email="user@example.com",
    role="operator",
    tenant_id="tenant1"
)

# Verify token
payload = jwt_handler.verify_token(token)
```

### 2. FastAPI Middleware (`auth/middleware.py`)

**Функциональность:**
- Проверка Bearer token в Authorization header
- Автоматическая инъекция user в `request.state.user`
- Публичные endpoints bypass (health, static files)

**Публичные пути (без auth):**
- `/api/health`
- `/` (dashboard)
- `/static/*`
- `/docs`, `/openapi.json`

**Защищенные пути:**
- `/api/*` (все кроме health)

**Использование:**
```python
from auth.middleware import AuthMiddleware

app = FastAPI()
app.add_middleware(AuthMiddleware)

@app.get("/api/protected")
async def protected_route(request: Request):
    user = request.state.user
    return {"user_id": user["user_id"], "role": user["role"]}
```

### 3. RBAC Permissions (`auth/permissions.py`)

**Роли:**
- **viewer**: только чтение (3 permissions)
- **operator**: чтение + некоторые write (6 permissions)
- **admin**: все разрешения (9 permissions)

**Permissions:**
```python
class Permission(str, Enum):
    READ_GRAPH = "read:graph"
    READ_DRIFT = "read:drift"
    READ_REPORT = "read:report"
    WRITE_FEEDBACK = "write:feedback"
    WRITE_WHITELIST = "write:whitelist"
    WRITE_POLICY = "write:policy"
    WRITE_GITOPS = "write:gitops"
    WRITE_INTEGRATIONS = "write:integrations"
    DELETE_WHITELIST = "delete:whitelist"
```

**Матрица разрешений:**

| Permission | Viewer | Operator | Admin |
|------------|--------|----------|-------|
| read:graph | ✓ | ✓ | ✓ |
| read:drift | ✓ | ✓ | ✓ |
| read:report | ✓ | ✓ | ✓ |
| write:feedback | ✗ | ✓ | ✓ |
| write:whitelist | ✗ | ✓ | ✓ |
| write:policy | ✗ | ✓ | ✓ |
| write:gitops | ✗ | ✗ | ✓ |
| write:integrations | ✗ | ✗ | ✓ |
| delete:whitelist | ✗ | ✗ | ✓ |

**Использование в FastAPI endpoints:**
```python
from fastapi import Depends
from auth.permissions import require_role, require_permission, Permission

# Require minimum role
@app.post("/api/feedback")
async def submit_feedback(user = Depends(require_role("operator"))):
    return {"message": "Feedback submitted"}

# Require specific permission
@app.post("/api/gitops/sync")
async def sync_gitops(user = Depends(require_permission(Permission.WRITE_GITOPS))):
    return {"message": "GitOps sync started"}
```

## Configuration

### Environment Variables

```bash
# JWT Configuration
JWT_SECRET=your-secret-key-min-32-chars  # REQUIRED
```

⚠️ **Security:** В production используйте криптографически стойкий secret минимум 32 байта.

## Testing

### Запуск тестов:

```bash
pytest tests/test_week10_auth.py -v
```

### Покрытие тестов:
- JWT generation and validation
- Expired token handling
- Invalid token handling
- Viewer permissions (read-only)
- Operator permissions (read + some write)
- Admin permissions (full access)
- RBAC matrix validation
- Unknown role handling

**Результат:** 8/8 tests passed ✓

## API Integration Example

```python
from fastapi import FastAPI, Depends, Request
from auth.middleware import AuthMiddleware
from auth.permissions import require_role, Permission

app = FastAPI()
app.add_middleware(AuthMiddleware)

# Public endpoint (no auth)
@app.get("/api/health")
async def health():
    return {"status": "ok"}

# Protected endpoint (any authenticated user)
@app.get("/api/graph/")
async def get_graph(request: Request):
    user = request.state.user
    tenant_id = user["tenant_id"]
    # Filter by tenant_id for multi-tenancy
    return {"graph": "data", "tenant": tenant_id}

# Role-based endpoint
@app.post("/api/policies/{id}/approve")
async def approve_policy(
    id: str,
    user = Depends(require_role("operator"))
):
    return {"policy_id": id, "status": "approved"}

# Permission-based endpoint
@app.post("/api/gitops/sync")
async def sync_gitops(
    user = Depends(require_permission(Permission.WRITE_GITOPS))
):
    return {"status": "syncing"}
```

## HTTP Responses

### Success (200/201)
```json
{
    "data": "...",
    "status": "ok"
}
```

### Unauthorized (401)
```json
{
    "detail": "Missing Authorization header"
}
```
```json
{
    "detail": "Token has expired"
}
```
```json
{
    "detail": "Invalid token: ..."
}
```

### Forbidden (403)
```json
{
    "detail": "Required role: operator, your role: viewer"
}
```
```json
{
    "detail": "Missing permission: write:gitops"
}
```

## Security Best Practices

1. **JWT Secret**
   - Минимум 32 байта
   - Храните в environment variables
   - Не коммитьте в git

2. **Token Expiration**
   - Default: 24 часа
   - Настраивается при генерации
   - Expired tokens автоматически отклоняются

3. **HTTPS**
   - В production всегда используйте HTTPS
   - Bearer tokens не должны передаваться по HTTP

4. **Token Storage**
   - Client-side: sessionStorage или httpOnly cookies
   - Server-side: не храните токены

## Phase 2 Roadmap

Следующие компоненты (в разработке):
- [ ] Multi-tenancy isolation (`auth/tenants.py`)
- [ ] Structured logging (`core/logging.py`)
- [ ] Rate limiting (`core/rate_limiter.py`)
- [ ] Database migrations (`core/migrations.py`)
- [ ] Enhanced healthcheck
- [ ] Production Dockerfile
- [ ] Helm charts
- [ ] Dashboard login page

## Changelog

**Phase 1** (Current)
- ✅ JWT authentication
- ✅ RBAC permissions system
- ✅ FastAPI middleware
- ✅ 8 comprehensive tests

## Troubleshooting

### "Missing Authorization header"
Добавьте header: `Authorization: Bearer <token>`

### "Token has expired"
Сгенерируйте новый токен. Default expiration: 24h.

### "Required role: operator, your role: viewer"
У пользователя недостаточно прав. Требуется повышение роли.

### "Missing permission: write:gitops"
Endpoint требует admin роль для write:gitops permission.

## Support

Для вопросов и issues см. project README.
