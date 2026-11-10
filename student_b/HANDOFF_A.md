# B → A: что необходимо для следующего этапа

Это внутренняя граница Python для A2/A3. Публичные модели B2 и файлы D не меняются. Сигнатура A1 принята и уже подключена; её credentials по-прежнему предоставляет серверная конфигурация.

## Готово со стороны B

`student_b.source.DataSource` — объект, который передаётся в `student_b.main.create_app(settings=..., source=adapter)`:

```python
count_measurements() -> int
fetch_measurements(scope: OpenCaseRequest, *, limit: int) -> Batch
list_stations(q: str | None, limit: int) -> Stations
```

Это не требование переименовать функции A. Адаптер может вызывать `read_measurements(...)` и `analyze_measurement(...)` под согласованными A именами. Их реальные сигнатуры и shape ещё нужны; до их получения B не пишет SQL и не угадывает их API.

`Batch` содержит:

- `rows: tuple[AnalyzedRow, ...]` — ограниченные и детерминированно упорядоченные результаты;
- `total_rows: int` — общее число совпадающих строк **до** применения cap;
- `truncated: bool` — true только если совпадающие строки действительно пропущены;
- `coverage_warnings: tuple[str, ...]` — ограничения доступной выборки.

`AnalyzedRow` содержит:

- `measurement: str`;
- `raw_fields: backend.app.schemas.RawFields` — исходные поля и source-local BOOK_STAMP без догадки о timezone;
- `calculation: backend.app.schemas.CalculationResult` — уже вычисленные A Decimal/None, deviation, range_status и quality_flags;
- `rule: str` — какое правило применено, чтобы B мог сохранить CALCULATED evidence с входным OBSERVED ID.

B сохраняет оба результата и создаёт IDs. Повторный get_evidence не обращается к источнику.

## Что передать от A

1. Исходники A2/A3 и точные Python-сигнатуры с безопасными синтетическими примерами результата.
2. Подтверждённую связь возвращаемого raw row с его анализом и порядок строк; source timestamps не объединяют записи в инцидент.
3. Обработку нулевой выборки, exact total перед cap, ниже/ровно/выше cap и query timeout.
4. Классы source/timeout errors. На границе B они преобразуются в `Failure` с безопасным public message; exception text драйвера не передавать в API.
5. Подтверждение пунктов D12 ниже на реальных данных и независимых примерах.

## D12: предложения B, а не подтверждённые факты Oracle

| Пункт | Предложение текущего B2 | Нужна проверка A |
| --- | --- | --- |
| Временные границы | from/to независимы, при наличии обеих from ≤ to; исходное ISO local-время без offset; границы включительны | Реальная семантика timestamp, строки на обеих границах, NULL source time |
| Row cap | default/max 200 captured rows; total до cap | Exact count, truncation и deterministic tie-break |
| Поиск станций | q — регистронезависимый префикс, default limit 20, max 100 | Реальные SQL semantics и ordering по station ID |
| Deviation | Для отсутствия breach строка 0; для невозможной оценки null | Совпадение A3 с B2; округление не вводится |
| Raw code | JSON string/null, отдельно от диапазона; SEMANTICS_UNKNOWN сохраняется | Явное представление исходного Oracle-типа без приписывания PASS/FAIL |
| Время выполнения | Ограничение TCP и отдельный post-login call timeout | Общий login/handshake deadline и бюджет нового коннектора остаются открытыми |

Если результат A отличается от предложения B2, согласовать решение до live-подключения. Не расширять молча numeric parser, не делать неподтверждённых joins и не подменять несовместимость исправленным sample.

## Что проверять вместе

Живой echo, независимые значения/границы выбранного scope, весь API-сценарий на настоящих результатах, ошибки Oracle и общий timeout-бюджет. Секреты и реальные экспорты в этот handoff не включаются. Локальный smoke из `student_b.tests.smoke` подтверждает только работу на синтетическом DataSource.
