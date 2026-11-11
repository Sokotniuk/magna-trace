# Приёмка интерфейса A → B

2026-11-11. Основание — переданный пользователем A-to-B-integration.zip. Проверены 20 payload hashes и канонические runtime-копии; A_SOURCE_PROVENANCE.json фиксирует hashes установленных модулей A. A-модули не редактировались.

## Принято на границе B

| Пункт | Реализация |
| --- | --- |
| A1 | Свежий count на каждый echo/readiness, серверные credentials |
| A2 | read_measurements keyword args и неизменяемый MeasurementPage |
| A3 | Реальный analyze_measurement, без повторных расчётов B |
| Caps | B default/max 200 измерений; station default 20/max 100; A internal default 100/max 500 сохранён |
| Scope | Алиасы from/to → from_time/to_time; A нормализует full naive ISO timestamp до шести дробных цифр |
| Time | Принято [from,to), from < to. Date-only, offset и >6 дробных цифр отклоняются с 422 до подключения драйвера |
| Search | Принят case-sensitive literal substring; % и _ — обычные символы; blank q → 422 |
| Nullable deviation | null без breach/при невозможности оценки; согласуется с D27 и существующим nullable B2 |
| Raw NUMBER | int/Decimal → точная string, None → null; не утверждается исходное текстовое написание Oracle NUMBER |
| Evidence | IDs выдаёт B; OBSERVED и CALCULATED запоминают source retrieval time, raw timestamp/strings, A3 rule/result |
| Private capture | A page и evaluations остаются в кейсе: полная coverage, temporary rowid, context, ordinals. Не публикуются новыми JSON-полями |

Структура схем/JSON B2 и прежние fixtures сохранены побайтно. Однако ранний README B2 предлагал включительный конец, регистронезависимый prefix и deviation=0; они не описывают подключённый A backend. D21 принимает A2 internal contract, D27 принимает A3 nullable deviation (записи D21/D27 предоставлены A в исходном handoff; они доступны у команды). B в этой поставке принимает эти интерфейсы; C/D должны сверить свои фильтры и mocks при сборке. Их новую внешнюю приёмку эта работа не заявляет. s.OpenCaseRequest содержит более общий формат JSON; точные source constraints дополнительно проверяет A и возвращает согласованный INVALID_SCOPE, не меняя тип wire-поля.

## Ошибки

- InvalidScopeError.code=INVALID_SCOPE → HTTP 422, без driver call.
- OracleTimeoutError/TimeoutError → TIMEOUT, HTTP 504.
- SourceUnavailableError, некорректные source results, ошибки проекции → SOURCE_UNAVAILABLE, HTTP 503.
- Пустая успешная measurement page → NO_DATA, HTTP 404, исходный точный input scope в error.scope. Пустой список станций → успешный stations=[].
- Неожиданные ошибки самой HTTP-обработки по-прежнему дают безопасный 500/SOURCE_UNAVAILABLE.
- ORA-01013 без доказанного timeout → SOURCE_UNAVAILABLE; DPY-4024 → TIMEOUT. Секреты, текст driver errors, phase/driver_code и traceback в response не передаются.

TCP и post-login per-call timeout не являются total deadline; D15 остаётся открытым. В этой поставке не создаётся ложная гарантия через asyncio.wait_for или неотменяемый фоновой поток.

## Остальные зависимости

Подтверждение конфликтов поддерживает внутренний answers.record_answer(reviewed_conflicts=...). REST принимает только question_id/answer_text; свободный текст не классифицируется автоматически. Новому провайдеру C нужен согласованный способ получить явное подтверждение от техника. Внешнее review-поле без B/C/D соглашения не добавлено.

A7/comparison отсутствует в полученном архиве и разрешается только после стабильного P0/G1. B8 comparison не объявляется выполненным; интеграционная часть B8 по приёму A2/A3 выполнена локально. Непроверенные joins, stronger assessment labels, persistence и дополнительные вопросы не добавлялись.
