# Student B — FastAPI, cases и evidence

Актуальный статус перед интеграцией и Definition of Done: [LOCAL_DOD.md](LOCAL_DOD.md).
Единая локальная проверка из корня: `python -m student_b.verify` — 75 тестов, 35 B2 fixtures и два синтетических сценария.

Новая папка runtime B. Импортирует общий `backend/app/schemas.py` из B2, не содержит второй копии контракта и не изменяет пакет D. Основание B2: `145652f917cd8b5ccda40f214a03ba45d490150d`. Copilot/MCP отложены по указанию пользователя; новую интеграцию C этот пакет не реализует.

## Принят интерфейс A1

```python
backend.app.oracle_repo.count_measurements(
    *, user, password, dsn,
    call_timeout_ms=5000,
    connect_timeout_seconds=5,
) -> int
```

Файл A из `magna-trace-student-a.zip` добавляется в его канонический путь `backend/app/oracle_repo.py` **без изменения содержимого**. Внутри выполняется фиксированный SELECT COUNT. Файл импортируется адаптером `student_b.source.OracleSource`; B не создаёт собственный SQL.

Ошибки A `SourceUnavailableError.code=SOURCE_UNAVAILABLE` и `OracleTimeoutError.code=TIMEOUT` преобразуются в HTTP 503/504 и общий B2 error-envelope. Учётные данные поступают только из серверных переменных. Историческое число в runtime не зашито, кэширования и запасных измерений нет.

**Подтверждение A, а не новая проверка B:** A сообщил о совпадении независимых SQL и Python COUNT. Параметры среды и фактическое значение в публичном пакете не приводятся. В этой облачной среде нет credentials источника; живое чтение здесь не заявляется.

**Ограничение D15 сохранено:** TCP connect timeout и post-login call timeout не задают полный deadline Oracle login/handshake. Не обещается ответ за 5 секунд при зависшем handshake. Это открытая зависимость A и бюджета нового коннектора C, а не исправленная этой обёрткой проблема. Обычные FastAPI `def` routes выполняют синхронное чтение в thread pool, не на event-loop thread.

## Установка и запуск

Запускать **из корня репозитория**, с Python 3.11+ и в среде, где доступен Oracle. Виртуальное окружение из Windows-архива не копировать в Linux; зависимости устанавливаются из официальных пакетов.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r student_b/requirements.txt
```

Серверные переменные:

| Переменная | Назначение |
| --- | --- |
| `TRACE_API_KEY` | Обязательный ключ 32–256 ASCII-символов; тот же серверный ключ использует proxy D |
| `ORACLE_USER` | SELECT-only пользователь из серверной конфигурации A |
| `ORACLE_PASSWORD` | Пароль только в окружении процесса/секрет-хранилище, не в Git |
| `ORACLE_DSN` | Реальный DSN A; 127.0.0.1 означает машину backend, а не удалённый компьютер A |
| `TRACE_DEV_ROUTES` | `true` временно включает echo, docs и openapi; по умолчанию `false` |
| `ORACLE_CALL_TIMEOUT_MS` | По умолчанию 5000; provisional, после login, на round trip |
| `ORACLE_CONNECT_TIMEOUT_SECONDS` | По умолчанию 5; provisional TCP timeout, не общий handshake deadline |

Все три ORACLE-переменные задаются вместе. Без них процесс может запуститься для разработки, но `/readyz` и echo возвращают SOURCE_UNAVAILABLE. Частичная конфигурация, SYS/SYSTEM, отсутствующий API key или некорректные положительные лимиты не принимаются.

Передать секреты в окружение через утверждённый механизм среды. Например, Bash может прочитать уже выданные секреты скрыто, не сохраняя их в командной истории:

```bash
read -rs -p 'Backend API key: ' TRACE_API_KEY; export TRACE_API_KEY
read -rs -p 'Oracle password: ' ORACLE_PASSWORD; export ORACLE_PASSWORD
# ORACLE_USER и ORACLE_DSN установить из серверной конфигурации A.
export TRACE_DEV_ROUTES=true
.venv/bin/python -m uvicorn student_b.main:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

Windows/PowerShell: использовать `.venv\Scripts\python.exe`; секреты можно вводить через `Read-Host -AsSecureString` и передавать серверному процессу через approved secret mechanism. Не вставлять значение пароля или API key в команды, Git, скриншоты и логи. Импортировать Windows `.venvs` из архива не требуется.

**Один worker обязателен:** cases хранятся в RAM. Проверяется WEB_CONCURRENCY, но также нельзя вручную запускать uvicorn с несколькими workers. После рестарта кейсы теряются. Публичный HTTPS/tunnel настраивает C; Oracle listener не публикуется.

## B1: проверка на машине A

- `GET /healthz` → HTTP 200, process=running; запрос к Oracle не делается.
- `GET /readyz` → HTTP 200 только после успешного живого COUNT; иначе 503/504.
- `GET /api/v1/health/echo` с X-API-Key, при TRACE_DEV_ROUTES=true → новый COUNT в `data.measurement_rows` (**целое количество строк**, не измерение Decimal).
- Тот же echo без/с неверным ключом → 401 до обращения к Oracle.
- `X-Request-ID` ответа совпадает с envelope.request_id и логом `magna_trace.student_b`.
- retrieved_at — UTC после завершения чтения/cleanup; BOOK_STAMP измерений не конвертируется.

Синтетический пример структуры с количеством 7, не результат живого запроса:

```json
{"request_id":"SYNTHETIC-REQUEST","retrieved_at":"2026-11-10T12:00:00Z","status":"ok","case_id":null,"data":{"measurement_rows":7},"error":null}
```

Два свежих вызова и независимый COUNT A нужны для живой проверки B1. После неё отключить TRACE_DEV_ROUTES и перезапустить: echo/docs/openapi перестают существовать. Логи выводят только request_id, шаблон route, HTTP status и длительность. Access-log uvicorn выключен, чтобы не записывать произвольные URL.

## B3–B7: что уже реализовано

- POST `/api/v1/cases` → snapshot, максимум 5 findings; остальные captured evidence доступны по IDs.
- GET `/api/v1/cases/{case_id}/evidence/{evidence_id}` → immutable OBSERVED/CALCULATED/TECHNICIAN_REPORTED без повторного чтения Oracle.
- POST `/api/v1/cases/{case_id}/answers` принимает `question_id`, `answer_text`; ответ.data — обновлённый snapshot напрямую, плюс report_evidence_id и change_summary.
- GET `/api/v1/cases/{case_id}/handover` → фактическое сохранённое состояние, отчёты техника, пробелы и следующий шаг.
- GET `/api/v1/stations` → станции; case_id всегда null.
- Случайные case IDs, TTL 7200 секунд от открытия, ёмкость 100, lock на кейс. Активный кейс не вытесняется при заполнении.
- Один вопрос из фиксированного списка, затем data-check. P0 label всегда UNDETERMINED. Причины и ремонтные процедуры не изобретаются.
- Ответ добавляет report, не меняет наблюдения/вычисления. Неоднозначное свободное сообщение не считается автоматически доказанным противоречием: warnings содержат REPORT_CONFLICT_NOT_AUTOMATICALLY_ASSESSED. Для явно проверенного конфликта теперь есть внутренний сервис student_b.answers.record_answer с reviewed_conflicts; он сохраняет ссылки и выбирает escalation. REST по B2 не принимает это поле: получение явного подтверждения от техника/C ещё нужно интегрировать. Исходная запись и ответ сохраняются рядом для проверки.
- X-API-Key на всех tool routes; нет bypass/CORS wildcard. Максимум 200 captured rows, body 16384 байта, ответ 2000 символов из B2; 60 авторизованных tool requests в минуту на общий connector key.

**Живое чтение измерений и станций пока не подключено.** Архив A содержит только A1; A2/A3 в его progress ledger имеют NOT_STARTED. Поэтому production `OracleSource.fetch_measurements` и `list_stations` явно возвращают SOURCE_UNAVAILABLE. Тестовый источник находится исключительно в tests, фабрика production никогда его не выбирает.

Для A2/A3 есть внутренняя граница `DataSource`:

```python
count_measurements() -> int
fetch_measurements(scope: OpenCaseRequest, *, limit: int) -> Batch
list_stations(q: str | None, limit: int) -> Stations
```

`Batch` содержит tuple `AnalyzedRow`, total matching rows до cap, truncated и coverage warnings. `AnalyzedRow` содержит measurement, неизменённые `RawFields`, уже вычисленный A `CalculationResult`, правило расчёта. B не повторяет Decimal-анализ. Сигнатуры из A plan (`read_measurements`, `analyze_measurement`) остаются у A: маленький адаптер может объединить их в эту внутреннюю структуру без изменения публичного B2.

Для подключения готового адаптера в своей factory вызвать `create_app(settings=..., source=adapter)`. Здесь DataSource — typing Protocol для Python, а не новый публичный endpoint. Адаптер применяет реальные SQL row limits, ordering и cursor timeouts; выбрасывает `Failure` с безопасным сообщением. Подтверждение D12, G1 и полный live journey остаются отдельными проверками.

## Ошибки

Все ответы используют B2 envelope. 401 UNAUTHORIZED; 422 INVALID_SCOPE для валидации; 409 INVALID_SCOPE для чужого/устаревшего/повторного вопроса; 404 NO_DATA с exact error.scope; 404 CASE_NOT_FOUND_OR_EXPIRED; 404 EVIDENCE_NOT_FOUND / EVIDENCE_NOT_IN_CASE; 503 SOURCE_UNAVAILABLE; 504 TIMEOUT.

Эксплуатационные лимиты не меняют схемы: 413 INVALID_SCOPE для body cap, 429 INVALID_SCOPE с Retry-After=60 для rate cap, 503 INVALID_SCOPE при заполнении store. Непредвиденный сбой backend — HTTP 500 с безопасным SOURCE_UNAVAILABLE и без exception text. Дополнительный INTERNAL_ERROR не вводится. Error-path никогда не содержит измерений.

## Проверки

```bash
.venv/bin/python -m pip install -r student_b/requirements-test.txt
.venv/bin/python -m pytest student_b/tests -q
.venv/bin/python contracts/b2/validate.py
.venv/bin/python -m student_b.tests.smoke
```

Фактические результаты и ограничения — в REPORT.md. Не коммитить виртуальные среды, .git-файл worktree из архива, pyc, пароли, дампы и полные реальные строки Oracle.

## Последняя локальная доработка

Подробный checkpoint — LOCAL_PROGRESS.md; handoff для A2/A3 — HANDOFF_A.md. Доработка подготовлена к публикации по отдельному запросу пользователя в feature/student-b-runtime; main не меняется. Команда smoke запускает только синтетический test source и не подтверждает live Oracle/интеграцию C. Текущий результат: 66 тестов, smoke и 35 fixtures B2 прошли. Публичные схемы и материалы D сохранены.
