# B2 v1 — пакет API-контракта для B, C и D

**Уточнение интеграции 2026-11-11:** структура моделей, schemas.json и examples.json сохранена. Подключённый A backend использует принятые D21/D27 half-open [from,to), case-sensitive literal substring и deviation=null без breach. Старые предложения inclusive/prefix/zero ниже — исторический контекст mock-пакета, не поведение текущего source adapter. См. student_b/INTEGRATION_NOTES.md; C/D должны сверить фильтры и fixtures при сборке. Нулевой deviation в старом синтетическом примере остаётся допустимым значением схемы, но не генерируется A3 для within-bounds.

**Статус:** подготовлено B для mock-разработки и согласования A/C/D; D подтвердил пригодность пакета для D1.2, формат record_answer.data и server-side X-API-Key; окончательный contract freeze и подтверждение C/A не заявляются. Это контракт, не работающий backend.

Основание: корневые `product.md`, `architecture.md`, `plan.md`, `decisions.md`, `AGENTS.md`, `tips.md` из `main` на ревизии `2cbfd41223bdb12ea29b795f0ef7335af6cdcab7`. На этой ревизии репозиторий содержит только эти шесть документов. Ссылки документов на `docs/` описывают будущую структуру; оригиналы здесь не перемещаются и не переписываются.

В разговоре пользователь отложил Copilot/MCP: C выберет другой API. Эта интеграция не реализуется пакетом B2. REST-контракт dashboard остаётся самостоятельным; выбор нового провайдера и изменение старой Copilot-документации команда фиксирует отдельно.

## Что брать студенту D

| Файл | Назначение |
| --- | --- |
| `backend/app/schemas.py` | Единственный исходник Pydantic-моделей запросов и ответов для последующей реализации B |
| `contracts/b2/schemas.json` | JSON Schema Draft 2020-12: `$defs/<ModelName>`, отдельно запросы и сериализованные ответы |
| `contracts/b2/examples.json` | 21 синтетический сценарий: пять инструментов, все evidence выбранного кейса, девять кодов ошибок и stale-question |
| `contracts/b2/vite.proxy.example.ts` | Образец серверной настройки Vite для D; не изменение чужого frontend |
| `contracts/b2/export.py` | Перегенерация JSON Schema из исходных моделей |
| `contracts/b2/validate.py` | Проверка примеров, ссылок и неизменности observations |

Не копировать отдельную вторую версию моделей в frontend. D может использовать JSON Schema и fixtures из этой папки; при изменении контракта B обновляет модели, экспорт и примеры вместе.

Все примеры **SYNTHETIC**, не Oracle-export. Строки `SYNTHETIC-STATION`, timestamps, IDs и числа предназначены для mock-сервера. Они не являются результатом живого тестирования или подтверждением gates. `request.body` в примерах GET — контейнер path/query-параметров для валидатора, не тело реального HTTP GET.

## Маршруты и модели

Базовый префикс: `/api/v1`. Все пять маршрутов требуют авторизацию.

| Операция | HTTP | Где параметры | Запрос → response.data |
| --- | --- | --- | --- |
| `open_case` | `POST /cases` | JSON body | `OpenCaseRequest` → `Snapshot` |
| `get_evidence` | `GET /cases/{case_id}/evidence/{evidence_id}` | path | `EvidenceRequest` → OBSERVED / CALCULATED / TECHNICIAN_REPORTED |
| `record_answer` | `POST /cases/{case_id}/answers` | case_id в path, question_id и answer_text в JSON | `RecordAnswerRequest` → `AnswerSnapshot` |
| `get_handover` | `GET /cases/{case_id}/handover` | path | `CaseRequest` → `Handover` |
| `list_stations` | `GET /stations` | q и limit в query | `StationsRequest` → `Stations` |

Успех всех операций: HTTP **200**. В `schemas.json` полный ответ называется `OpenCaseResponse`, `GetEvidenceResponse`, `RecordAnswerResponse`, `GetHandoverResponse`, `ListStationsResponse`. Любая описанная API-ошибка использует `ErrorResponse`.

`list_stations` не открывает кейс: успешный ответ всегда содержит **`case_id: null`**, что закреплено и в Pydantic, и в JSON Schema, и в примере.

`compare_case` — P1, не обещан в этом пакете и не нужен для начала dashboard. Его канонический код отказа `NOT_COMPARABLE` приведён для будущего UI.

## Envelope и отображение

Во всех ответах: `request_id`, `retrieved_at`, `status`, `case_id`, `data`, `error`. При успехе `status=ok`, `error=null`; при ошибке `status=error`, `data=null`. Системное время получения — UTC ISO-8601. Исходный `BOOK_STAMP` остаётся строкой без преобразования или догадки о timezone.

`open_case.data` — сам snapshot: `scope`, максимум пять `findings`, `additional_evidence_ids`, `technician_reports`, `assessment`, `next_action`, `warnings`, время исходного чтения `observations_retrieved_at`.

**`record_answer.data` также сам обновлённый snapshot**, с двумя дополнительными полями `report_evidence_id` и `change_summary`. Не искать его в `data.snapshot`. Это следует формулировке snapshot-раздела архитектуры и задаёт однозначный путь для React.

`assessment.label` в P0 только `UNDETERMINED`. `next_action.kind` — ровно один из `question`, `data_check`, `escalation`. Только question содержит `question_id`. После ответа сохраняются прежние findings, создаётся TECHNICIAN_REPORTED и меняется следующий шаг. Хранить активные case_id/question_id из API; устаревший или повторный ответ — 409.

Числовые результаты `parsed_value`, `deviation` — **строки или null**, не JSON numbers. D не пересчитывает их через Number/parseFloat для диагностики. `raw_value`, границы, `raw_fail_code` сохраняются отдельно; код `1001` и null не означают PASS/FAIL. Внутри границ в этой версии deviation="0"; при невозможности оценки — null. Точность сохраняется, экспоненциальная строковая запись вычисленных Decimal допустима (например, "1E-21", "1e+3"); JSON Schema и Pydantic serialization согласованы. Это правило wire-формата результата, а не разрешение экспоненты в строгом парсере исходных Oracle-строк A.

Каждый finding содержит `evidence_id` наблюдения и `calculation_evidence_id` расчёта. Оба доступны через get_evidence. Примеры включают все шесть evidence трёх findings и отдельное evidence ответа техника. Дополнительные findings раскрываются через `additional_evidence_ids`.

## Ошибки и HTTP-коды

| HTTP | error.code | Поведение D |
| --- | --- | --- |
| 401 | UNAUTHORIZED | Показать ошибку конфигурации server-side proxy; не просить ввести ключ в React |
| 422 | INVALID_SCOPE | Неверные поля/формат/интервал scope; исправить ввод |
| 409 | INVALID_SCOPE | Вопрос чужой, устарел или уже отвечен; не отправлять ответ повторно автоматически |
| 404 | NO_DATA | Показать точный `error.scope`; не выводить, что станция исправна |
| 503 | SOURCE_UNAVAILABLE | Сообщить о недоступном источнике; не подставлять mock-измерения |
| 504 | TIMEOUT | Показать timeout без запасных измерений |
| 404 | EVIDENCE_NOT_FOUND | Неизвестная ссылка на evidence |
| 404 | EVIDENCE_NOT_IN_CASE | Evidence относится к другому кейсу |
| 404 | CASE_NOT_FOUND_OR_EXPIRED | Предложить открыть новый кейс; не восстанавливать его из frontend-memory |
| 422 | NOT_COMPARABLE | P1: показать конкретную причину отказа сравнения |

`error.scope` — optional nullable дополнение для точного запроса при NO_DATA. Новых error.code не вводится. Проблема сети или неожиданный не-JSON/500 ответ отображается D общей технической ошибкой; не превращать его в диагностическое заключение. Полное поведение непредвиденных серверных ошибок и эксплуатационных лимитов уточняется B1/B6 до live-подключения.

## Авторизация и Vite proxy

Предлагаемый формат B2: **`X-API-Key: <server-side secret>`** на каждом `/api/v1` запросе. Нет ключа/неверный ключ → 401 UNAUTHORIZED. Конкретную настройку ключа в backend и новом API C ещё нужно подтвердить; реальный секрет в этом пакете отсутствует.

React вызывает относительные URL:

```ts
const response = await fetch('/api/v1/cases', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ station_number: 'SYNTHETIC-STATION' }),
});
const envelope = await response.json();
```

Браузер не добавляет API key. Vite proxy на стороне Node читает `TRACE_API_KEY`, добавляет/перезаписывает X-API-Key и пересылает запрос backend. Префикс `/api/v1` не переписывается. По умолчанию target — `http://127.0.0.1:8000`; server-only переменная `TRACE_API_TARGET` может указывать mock или реальный backend. Если target внешний, использовать доверенный HTTPS endpoint.

Ключ не хранится в `VITE_*`, define/envPrefix, React-коде, localStorage/sessionStorage или ответе mock-сервера. Не коммитить `.env`, токены или дампы. Vite-пример работает в локальной разработке, не является production-прокси; backend auth и CORS ради него не ослабляются.

Сохранение snapshot в UI при сетевой ошибке допустимо только как явно прежние данные с `observations_retrieved_at`. Нельзя выдавать прежние значения за свежий ответ на ошибочный запрос.

## Проверка и что ещё согласовать

В окружении с Pydantic 2 и jsonschema:

```bash
python contracts/b2/export.py
python contracts/b2/validate.py
```

Проверено: 35 request/response fixtures, все девять error codes, строковые Decimal в JSON Schema, разрешимость evidence-ссылок, независимая арифметика 10.5−10.0=0.5, сохранение findings после ответа, появление report в handover. Это проверки контракта; API/Oracle/Vite в реальном приложении не запускались.

До freeze B2 участники подтверждают:

1. D/C — `answer_text`, `data` обновлённого snapshot без дополнительной обёртки, поля и статусы; заголовок X-API-Key.
2. A/B по открытому D12 — включительность временных границ, грамматику временного scope, nullable deviation и лимиты. Предложение этой версии: исходное local ISO-время без offset; обе временные границы включительны; q — регистронезависимый префикс station_number; limit по умолчанию 20, максимум 100; max findings 5; max answer_text 2000. Реальная совместимость с Oracle не подтверждена.
3. Совместный статус freeze и соответствующую датированную запись decisions.md. Эта папка не выдаёт отсутствие ответа участников за согласие.

D может начинать mock/React на этой версии сейчас. Следующая задача B после согласования — B1/B3, с реализацией тех же схем в основной структуре проекта. Отдельный второй backend для D не создаётся.

## Проверка D и статус версии

Замечания D исправлены: schema допускает экспоненциальные строки вычисленных Decimal; EVIDENCE_NOT_FOUND и EVIDENCE_NOT_IN_CASE привязаны к GET evidence с path-параметрами; list_stations.case_id строго null. Также исправлен маршрут примера неизвестного кейса. Добавлены проверки этих условий, недопустимых Decimal и round-trip сериализации.

Эта ревизия остаётся **кандидатом B2 v1**, не frozen. D подтвердил пригодность для D1.2 и два указанных формата, но не окончательный freeze. Открыты D12 с A и подтверждение C. Для воспроизводимости D должен использовать commit SHA, переданный вместе с этой ревизией; после всех подтверждений будет отдельно назван SHA замороженной версии.
