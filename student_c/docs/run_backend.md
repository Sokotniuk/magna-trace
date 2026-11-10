# Запуск бэкенда (Windows, PowerShell)

Все команды — в PowerShell, из папки проекта:

```powershell
cd <repo>\student_c
```

`curl` в PowerShell — это другая команда, поэтому везде пишется `curl.exe`.
Активация `.venv\Scripts\Activate.ps1` заблокирована политикой скриптов, поэтому Python из окружения вызывается напрямую: `.venv\Scripts\python.exe`.

## 1. Один раз: окружение и зависимости

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -r harness\requirements.txt
```

## 2. Один раз: пользователь Oracle только для чтения

```powershell
docker cp scripts\create_readonly_user.sql oracle-free:/tmp/create_readonly_user.sql
docker exec -it oracle-free sqlplus "/ as sysdba" "@/tmp/create_readonly_user.sql"
```

Скрипт спросит пароль для `TRACE_RO` (только буквы и цифры) и в конце покажет число строк измерений.

## 3. Один раз: переменные окружения

Сохраняются в профиле пользователя Windows, не в проекте. После этих команд **закрой и открой PowerShell заново**.

```powershell
[Environment]::SetEnvironmentVariable("TRACE_API_KEY", (python -c "import secrets; print(secrets.token_urlsafe(32))"), "User")
[Environment]::SetEnvironmentVariable("ORACLE_USER", "trace_ro", "User")
[Environment]::SetEnvironmentVariable("ORACLE_PASSWORD", "<пароль TRACE_RO>", "User")
```

Необязательные (значения по умолчанию подходят): `ORACLE_DSN` = `localhost:1521/FREEPDB1`, `TRACE_API_KEY_HEADER` = `X-API-Key`.

## 4. Запуск

```powershell
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

В логе каждая строка выглядит так: `request_id=… GET /api/v1/health/echo -> 200 (35 ms)`. Заголовки и ключ не печатаются.

## 5. Проверки (во втором окне PowerShell)

| Команда | Ожидается |
| --- | --- |
| `curl.exe http://127.0.0.1:8000/healthz` | `{"status":"ok"}` |
| `curl.exe -i http://127.0.0.1:8000/api/v1/health/echo` | `401`, код `UNAUTHORIZED` |
| `curl.exe -H "X-API-Key: $env:TRACE_API_KEY" http://127.0.0.1:8000/readyz` | `{"status":"ok"}` |
| `curl.exe -H "X-API-Key: $env:TRACE_API_KEY" http://127.0.0.1:8000/api/v1/health/echo` | `status: ok`, `measurement_rows` = число из шага 2 |

`request_id` из ответа должен совпасть со строкой в логе сервера.
