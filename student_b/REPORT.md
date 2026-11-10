# Отчёт студента B — 2026-11-10

## Результат

Подготовлен runtime в новой папке `student_b/`. Общий контракт и все материалы D (`backend/app/schemas.py`, `contracts/b2/`) сохранены побайтно относительно B2 `145652f917cd8b5ccda40f214a03ba45d490150d`. Новые бизнес-поля, дополнительные error codes и MCP не добавлены.

Принят интерфейс A1: `backend.app.oracle_repo.count_measurements(*, user, password, dsn, call_timeout_ms=5000, connect_timeout_seconds=5) -> int`. Полученный исходник A сохранён в каноническом пути без правок. B использует серверные credentials, вызывает функцию заново на каждом echo и отображает её реальные типизированные ошибки в общий API-конверт. Исторический результат не зашит в runtime; запасных измерений нет.

## Выполнено и статус плана

| Задача | Выполненная часть | Оставшаяся проверка/зависимость |
| --- | --- | --- |
| B1 | FastAPI factory, API key, envelope, request_id/log, process/readiness, dev echo с настоящей функцией A1 | Живой вызов на машине с Oracle и credentials, проверка через новую интеграцию C |
| B2 | Используется исправленная версия, переданная D; пакет D не редактировался | Открытые A/B D12 и будущий контракт C не объявлены решёнными автоматически |
| B3 | Immutable observed/calculated/reported evidence, case-local IDs, ошибки чужих и отсутствующих ссылок | Независимые SQL-проверки реальных измерений после A2/A3 |
| B4 | Изоляция, случайные IDs, абсолютный TTL, bound store, per-case lock, состояния, единый код потерянного кейса | Автоматическая классификация противоречия в свободном тексте не реализована; оба свидетельства сохранены, необходимость reconciliation явно отмечена |
| B5 | Snapshot max 5 findings, один вопрос, фиксированный следующий check, hypotheses и UNDETERMINED, handover | Подключение расчётов A3 и подтверждённого demo scope A4 |
| B6 | Все пять REST-маршрутов реализованы и работают с типизированным source adapter | Производственный источник пока предоставляет только COUNT. Чтение измерений/станций требует A2/A3 |
| B7 | 58 локальных тестов и проверка ответов по B2 schema | Живые source/tenant/tunnel проверки не заменяются этими тестами |
| B8 | Не начат, comparison route выключен | A7 и стабильный P0; расширение не входит в эту поставку |

## Фактические проверки

- `.venv/bin/python -m pytest student_b/tests -q` → **58 passed, 2 warnings**.
- `.venv/bin/python contracts/b2/validate.py` → **PASS, 35 request/response fixtures** и все девять canonical error codes.
- Запущен настоящий loopback uvicorn с одним worker: `/healthz` → **200**, echo без ключа → **401**, echo с ключом и без Oracle settings → **503**, измерения отсутствуют, HTTP `X-Request-ID` совпадает с envelope. Проверочный процесс завершён.
- В B1 использован исходник A с настоящим `oracledb 26.1.0`, синтетическим driver double и counts 7/8/0: фиксированный SELECT, fresh call, передача server credentials и timeout args, driver cleanup и правильное отображение ошибок. Это не live Oracle.
- Проверены: пять B2 responses, immutable captured evidence, независимость range/quality/code, изоляция кейсов, один результат при двух одновременных ответах, TTL/restart, неизвестные IDs, malformed scope/answers, NO_DATA exact scope, SOURCE_UNAVAILABLE/TIMEOUT, body/rate/case/row caps, source failure без cached fallback, redacted logs.
- Два предупреждения относятся к установленным anyio/pytest и Starlette/httpx; тесты не пропускались и не выключались ради зелёного результата.

## Источник живых фактов и ограничения

A сообщил об успешной независимой проверке своего источника. B принял сигнатуру функции и проверил её интеграцию на синтетическом драйвере; живой доступ в этой сессии не выполнялся. Идентификаторы среды, учётной записи и фактические значения source-проверки в публичный отчёт не включаются. Учётные данные в репозиторий не передаются.

В архиве A есть только A1 count; A2/A3 в checkpoint ещё не начаты. Поэтому по умолчанию полноценные `/cases` и `/stations` возвращают явный SOURCE_UNAVAILABLE. Реальный source adapter подключается через factory; синтетические fixtures существуют только в tests.

Проблема total login/handshake deadline из D15 остаётся открытой. TCP timeout и call timeout не обещают общий deadline. Не добавлены притворный asyncio-timeout, неотменяемые фоновые чтения или запасные ответы.

G0–G3 и demo-ready не объявляются пройденными. Новый провайдер C, публичный туннель и любые внешние вызовы модели в эту работу не входят. Main и файлы D не меняются; изменения готовятся в отдельной feature-ветке.

## Следующий шаг

На машине A установить зависимости, передать credentials через серверное окружение, запустить `uvicorn student_b.main:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log` с TRACE_DEV_ROUTES=true. Сопоставить два echo, UTC retrieved_at/request IDs и независимый SQL COUNT. Далее A передаёт A2/A3 для source adapter, а C подтверждает новый способ вызова того же REST API.

## Последующее локальное продолжение

Предыдущие результаты выше относятся к опубликованной поставке runtime. После неё локально добавлены явный conflict review и единый smoke без изменения B2; Изначально изменения проверены локально; по следующему запросу пользователя они подготовлены к публикации в feature/student-b-runtime, без изменения main. Актуальные проверки — 66 passed, синтетический smoke PASS и 35 B2 fixtures PASS. Точный статус, оставшиеся зависимости и ограничения review приведены в LOCAL_PROGRESS.md; входные ожидания для A — в HANDOFF_A.md.
