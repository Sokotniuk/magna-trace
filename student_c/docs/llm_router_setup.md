# FreeLLMAPI для временного чата — подробный гайд

> **Зачем:** Copilot Studio без кредитов, у OpenAI-ключа нет баланса. Наш временный чат `harness/chat_openai.py` получает модель из локального маршрутизатора FreeLLMAPI, который использует бесплатные лимиты провайдеров на **твоих** ключах.
> **Это временный клиент**, не Copilot и не доказательство G0.
> **Способ запуска:** Docker. У тебя Node.js 26, а проект требует Node 20.18–24 (`package.json`, `.nvmrc` = 22) — при запуске без Docker нативный модуль базы данных, скорее всего, не соберётся. Docker уже работает (в нём Oracle), поэтому версия Node не важна.
> Сведения о FreeLLMAPI взяты из его документации в скачанной папке (`docs/en/install`, `docs/en/api`); код маршрутизатора не проверялся.

## Как закрыты оговорки

| Оговорка | Как закрыта | Где |
| --- | --- | --- |
| Маршрутизатор открыт в сеть | В его `docker-compose.yml` порт по умолчанию привязан к `127.0.0.1`. Проверяем в шаге 5 | Шаг 5 |
| `auto` / `fusion` меняют модель от запроса к запросу | Чат **не запустится** с такой моделью | `check_model()` |
| Маршрутизатор может тихо подменить модель, если у выбранной кончился лимит | Чат читает заголовок `X-Routed-Via` у каждого ответа. Ответила другая модель — **ответ отбрасывается**, и чат пишет об этом | `served_model()`, `is_pinned_model()` |
| Настоящие данные MAGNA уйдут провайдеру | Пока не задано `TRACE_ALLOW_REAL_DATA=1`, модели передаётся только результат `health_echo`; остальные инструменты блокируются | `TOOLS_WITHOUT_MAGNA_DATA` |
| Ключи провайдеров получать самому | Нужен **один** провайдер | Шаг 7 |
| Ключ шифрования маршрутизатора | Создаётся случайно, хранится только в `.env` рядом с маршрутизатором | Шаг 3 |

Все команды ниже — в **PowerShell**. `curl` в PowerShell — другая команда, поэтому везде пишется `curl.exe`.

---

## Шаг 1. Перенести папку маршрутизатора

Сейчас проект лежит в `Downloads\freellmapi-main\freellmapi-main` (двойная папка после распаковки). Перенесём его в `Documents\freellmapi`, рядом с `magna-trace`, но **не внутрь** него.

```powershell
Move-Item "$HOME\Downloads\freellmapi-main\freellmapi-main" "$HOME\Documents\freellmapi"
cd $HOME\Documents\freellmapi
dir docker-compose.yml
```

**Должно получиться:** строка с файлом `docker-compose.yml`.

Пустую папку `Downloads\freellmapi-main` и архив `freellmapi-main.zip` можно потом удалить.

## Шаг 2. Проверить Docker

```powershell
docker compose version
```

**Должно получиться:** `Docker Compose version v2.…`.

Если команда не найдена — запусти Docker Desktop и подожди, пока он загрузится (Oracle ведь уже работает в Docker, так что он установлен).

## Шаг 3. Создать файл настроек `.env`

Маршрутизатору нужен ключ шифрования: им он шифрует сохранённые ключи провайдеров. Создаём случайный ключ и файл `.env`.

Выполни **всё одним блоком** (находясь в `Documents\freellmapi`):

```powershell
$Bytes = New-Object Byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($Bytes)
$Key = -join ($Bytes | ForEach-Object { "{0:x2}" -f $_ })
[IO.File]::WriteAllText("$HOME\Documents\freellmapi\.env", "ENCRYPTION_KEY=$Key`nPORT=3001`n")
Remove-Variable Key, Bytes
```

Почему не как в README: там файл пишется через `Out-File -Encoding utf8`. В Windows PowerShell 5.1 это добавляет в начало файла невидимый символ (BOM), и тогда Docker может не увидеть `ENCRYPTION_KEY`. `WriteAllText` пишет файл без него.

Проверь (сам ключ не печатается, только длина первой строки):

```powershell
(Get-Content .env)[0].Length
```

**Должно получиться:** `79`.

**Правила для этого ключа:**
- Не меняй его после того, как добавишь ключи провайдеров, — иначе маршрутизатор не сможет их расшифровать.
- Никуда не копируй. `.env` уже указан в `.gitignore` проекта FreeLLMAPI.

## Шаг 4. Запустить маршрутизатор

```powershell
docker compose up -d
```

Docker скачает готовый образ `ghcr.io/tashfeenahmed/freellmapi:latest` (несколько сотен МБ) и запустит контейнер.

**Должно получиться** в конце:

```
✔ Container freellmapi-freellmapi-1  Started
```

**Если скачать образ не удалось** (ошибка `denied`, `not found`, `unauthorized`) — собери его из скачанных исходников. Это дольше, 5–10 минут:

```powershell
docker compose up -d --build
```

## Шаг 5. Проверить, что маршрутизатор работает и закрыт от сети

Подожди 30 секунд, затем:

```powershell
docker compose ps
```

**Должно получиться:** в колонке `STATUS` — `Up … (healthy)`. Если `(health: starting)` — подожди ещё 30 секунд и повтори.

Проверка доступа из сети:

```powershell
netstat -ano | findstr ":3001"
```

| Видишь | Значит |
| --- | --- |
| `127.0.0.1:3001 … LISTENING` | Правильно: доступно только с этого ноутбука |
| `0.0.0.0:3001` или `[::]:3001` | Открыто в сеть. Останови (`docker compose down`), проверь, что в `.env` нет строки `HOST_BIND`, и запусти снова |

Туннель на порт 3001 **никогда** не открывай.

## Шаг 6. Открыть панель и создать локальный аккаунт

1. Открой в браузере: `http://localhost:3001`
2. Серверная версия просит **email и пароль** — это аккаунт только этой панели на твоём ноутбуке, не регистрация на внешнем сайте. Придумай пароль и сохрани его в менеджере паролей.
3. Войди в панель.

**Должно получиться:** панель FreeLLMAPI с разделами, среди которых есть **Keys** и **Fallback Chain**.

Если забудешь пароль — в документации `docs/en/install/01-install.md` есть раздел «FAQ: passwords, logs, uninstall».

## Шаг 7. Получить ключ одного провайдера

Нужен **один** провайдер с бесплатным API, OpenAI-совместимым адресом и моделями с вызовом инструментов (tool calling). Предлагаю **Groq**: в списке поддерживаемых платформ FreeLLMAPI он подключается стандартным OpenAI-совместимым адресом, без особенностей.

1. Открой консоль Groq (`console.groq.com`) и зарегистрируйся **сам**.
2. Найди раздел **API Keys** и создай ключ. Скопируй его — он показывается один раз.
3. **Проверь условия по данным:** найди в документации или настройках Groq, используются ли запросы API для обучения моделей и можно ли это выключить. Если есть такой переключатель — выключи. Запиши себе, что там сказано: это понадобится в шаге 13.

Ключ Groq никуда не копируй, кроме панели FreeLLMAPI.

**Не подключай** провайдеров без ключа (keyless) вроде `kilo`: по документации FreeLLMAPI его бесплатные запросы и ответы записываются для обучения.

## Шаг 8. Добавить ключ в панель и взять ключ маршрутизатора

1. В панели открой **Keys**.
2. Добавь ключ Groq из шага 7. Других провайдеров **не добавляй**.
3. Убедись, что Groq отмечен как подключённый или проверенный.
4. В **заголовке страницы Keys** найди **unified API key** — ключ, начинающийся с `freellmapi-`. Это ключ маршрутизатора, его использует наш чат. Скопируй его.

Сохрани ключ маршрутизатора во временную переменную этого окна, чтобы не вставлять его в каждую команду:

```powershell
$R = "ВСТАВЬ_КЛЮЧ_freellmapi"
```

## Шаг 9. Выбрать одну модель

Посмотри, какие модели доступны:

```powershell
curl.exe -s -H "Authorization: Bearer $R" http://localhost:3001/v1/models | python -c "import sys, json; [print(m['id']) for m in json.load(sys.stdin)['data']]"
```

**Должно получиться:** список идентификаторов моделей.

Как выбрать:
- **С поддержкой вызова инструментов (tool calling).** На странице Fallback Chain у моделей бывают отметки возможностей; в документации Groq указано, какие модели поддерживают tool use.
- **Крупная instruct-модель**, а не маленькая: маленькие хуже соблюдают правила агента.
- **Не `auto`, не `auto:…`, не `fusion`** — с ними наш чат не запустится.

Скопируй **точный идентификатор** выбранной модели из списка.

Необязательно, но полезно: на странице **Fallback Chain** выключи все модели, кроме выбранной (там есть «Disable all»). Даже если этого не сделать, наш чат отбросит ответ чужой модели — но так он будет реже упираться в отказ.

## Шаг 10. Проверить модель одним запросом

```powershell
curl.exe -s -i http://localhost:3001/v1/chat/completions -H "Authorization: Bearer $R" -H "Content-Type: application/json" -d '{\"model\": \"ИДЕНТИФИКАТОР_МОДЕЛИ\", \"messages\": [{\"role\": \"user\", \"content\": \"Say OK\"}]}'
```

Подставь идентификатор модели вместо `ИДЕНТИФИКАТОР_МОДЕЛИ`.

**Должно получиться:**
- в начале `HTTP/1.1 200 OK`;
- среди заголовков `X-Routed-Via: groq/<твоя модель>` — значит, ответила именно она;
- внизу JSON с текстом ответа.

Если `X-Routed-Via` показывает другую модель — выбранная сейчас недоступна; возьми другую из списка.

## Шаг 11. Подключить наш чат к маршрутизатору

Четыре постоянные переменные. `TRACE_EXPECTED_ROUTE` — это **точное** значение `X-Routed-Via` из шага 10: оно закрепляет и модель, и провайдера (а значит, и его правила по данным).

```powershell
[Environment]::SetEnvironmentVariable("OPENAI_BASE_URL", "http://localhost:3001/v1", "User")
[Environment]::SetEnvironmentVariable("OPENAI_API_KEY", $R, "User")
[Environment]::SetEnvironmentVariable("OPENAI_MODEL", "gpt-oss-120b", "User")
[Environment]::SetEnvironmentVariable("TRACE_EXPECTED_ROUTE", "groq/openai/gpt-oss-120b", "User")
Remove-Variable R
```

Проверено 2026-11-10: `gpt-oss-120b` маршрутизируется как `groq/openai/gpt-oss-120b` и вызывает инструменты.

`TRACE_ALLOW_REAL_DATA` и `TRACE_ALLOW_MODEL_FALLBACK` **не задавай**: обе защиты должны быть включены.

**Закрой Windows Terminal целиком** (все вкладки) и открой заново.

## Шаг 12. Запустить и проверить

**Вкладка 1 — бэкенд:**

```powershell
cd <repo>\student_c
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

**Вкладка 2 — чат:**

```powershell
cd <repo>\student_c
.venv\Scripts\python.exe harness\chat_openai.py
```

**Должно получиться:**

```
MAGNA TRACE harness (OpenAI stand-in for Copilot). Not the product interface.
Tools: health_echo
Model: gpt-oss-120b via http://localhost:3001/v1
Pinned route: groq/openai/gpt-oss-120b
Real MAGNA data to model: BLOCKED (only health_echo)
Type /quit to exit.

technician>
```

Напиши:

```
Run the health_echo tool and show me the request_id.
```

**Должно получиться:**
- `[tool] health_echo({})`
- `[tool] -> status=ok request_id=…`
- ответ модели с этим `request_id` и числом `1524`;
- во вкладке 1 строка `request_id=… POST /mcp -> 200` с **тем же** ID.

Это закрывает шаг 3 маршрута: модель → MCP → Oracle работает. Выход из чата — `/quit`.

## Если что-то пошло не так

| Симптом | Причина | Что делать |
| --- | --- | --- |
| `docker compose ps` показывает `Restarting` или `Exited` | Чаще всего не прочитан `ENCRYPTION_KEY` | `docker compose logs --tail 50` и пришли вывод; проверь шаг 3 (длина `79`) |
| Чат сразу пишет `OPENAI_MODEL='auto' switches models…` | Указан `auto` или `fusion` | Задай конкретный ID (шаг 11) |
| `[guard] answer came from …, not the pinned model …` | У выбранной модели кончился лимит, маршрутизатор подставил другую | Подожди (лимиты сбрасываются в полночь UTC) или закрепи другую модель того же класса |
| `[model error] AuthenticationError` | Неверный ключ маршрутизатора | Скопируй `freellmapi-…` заново (шаг 8), повтори шаг 11 |
| `[model error] NotFoundError` | Неверный ID модели | Сверь со списком из шага 9 |
| `[model error] APIConnectionError` | Маршрутизатор не запущен | `cd $HOME\Documents\freellmapi`, затем `docker compose up -d` |
| Модель отвечает, но не вызывает инструмент | Слабая модель или без tool calling | Возьми модель крупнее. Инструкции под модель **не переписывай** — они общие с Copilot |
| `[guard] blocked: real MAGNA data…` | Модель вызвала инструмент с данными MAGNA | Так и задумано до шага 13 |

## Управление маршрутизатором

Из папки `Documents\freellmapi`:

| Действие | Команда |
| --- | --- |
| Остановить | `docker compose stop` |
| Запустить снова | `docker compose start` |
| Посмотреть логи | `docker compose logs --tail 50` |
| Удалить контейнер (ключи и настройки сохранятся в томе Docker) | `docker compose down` |

Автообновление (`--profile autoupdate`) **не включай**: ему нужен доступ к Docker-сокету, то есть полный контроль над Docker, включая контейнер с Oracle.

## Шаг 13. Перед настоящими данными (шаг 4 маршрута)

`open_case` будет возвращать реальные измерения MAGNA. Предохранитель их не пропустит, пока ты сознательно его не выключишь.

1. Отправь организаторам:

```text
Hi, team MAGNA TRACE. While Copilot Studio has no credits, we test our agent
with a free-tier model from <провайдер> through a local router. Measurement
values from the HACKATON schema would be sent to that provider's API.
Is that allowed during development? Their data policy: <кратко из шага 7>.
```

2. **Ответ «да»** → запиши его в `docs/decisions.md` и включи передачу:

```powershell
[Environment]::SetEnvironmentVariable("TRACE_ALLOW_REAL_DATA", "1", "User")
```

Затем закрой терминал целиком и открой заново.

3. **«Нет» или ответа нет** → предохранитель остаётся. Разработку `open_case` и остальных инструментов продолжаем и проверяем через `curl` и тесты бэкенда, без модели.

## Что записать в `docs/decisions.md`

```text
2026-11-10 · Interim model via FreeLLMAPI (Docker)
- Router: FreeLLMAPI from GitHub source, image ghcr.io/tashfeenahmed/freellmapi:latest (or local build)
- Listens on 127.0.0.1:3001 only (netstat checked): yes/no
- Provider: <…>; training on API data: <да/нет/выключено>
- Model (pinned): <ID>; harness discards answers whose X-Routed-Via differs
- Real data guard: ON (only health_echo) until organizers approve
- health_echo via model: request_id <…> matched backend log: yes/no
```
