# Backend Student B

Рабочий код B с подключёнными неизменёнными A1/A2/A3/A6. Python 3.11+, проверено на 3.12. Запускать из корня рядом со student_b, backend и contracts.

```bash
python -m venv .venv
.venv/bin/python -m pip install -r student_b/requirements-test.txt
.venv/bin/python -m student_b.verify
.venv/bin/python -m uvicorn student_b.main:create_app --factory --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
```

Windows PowerShell: используйте .venv\Scripts\python.exe вместо .venv/bin/python. Для сервера без тестов достаточно requirements.txt.

Перед запуском передайте TRACE_API_KEY (32–256 ASCII), ORACLE_USER, ORACLE_PASSWORD и ORACLE_DSN в окружение серверного процесса. ORACLE-переменные задаются вместе; SYS/SYSTEM запрещены. .env автоматически не читается. Секреты не вставлять в Git/чат/VITE_*.

Один worker обязателен: RAM cases теряются после рестарта. Backend должен иметь доступ к Oracle со своей машины. Caps: 200 измерений, 100 кейсов, TTL 7200 секунд, body 16384 байта, 60 tool requests/minute. TRACE_DEV_ROUTES=true временно включает echo/docs/openapi; по умолчанию false. ORACLE_CALL_TIMEOUT_MS=5000 и ORACLE_CONNECT_TIMEOUT_SECONDS=5 не являются общим handshake deadline.

Все /api/v1 маршруты требуют X-API-Key:

- POST /cases — station_number, optional serial_number/from/to.
- GET /cases/{case_id}/evidence/{evidence_id} — immutable captured evidence без requery.
- POST /cases/{case_id}/answers — question_id, answer_text; обновлённый snapshot непосредственно в data.
- GET /cases/{case_id}/handover — сохранённое состояние.
- GET /stations — q и limit (default 20, max 100), case_id=null.

Принятый A interface: full naive timestamps до шести дробных цифр; [from,to), from < to. q — literal substring с учётом регистра, blank q → 422. Decimal/raw NUMBER — exact string/null; deviation=null без breach. Max 5 findings, assessment UNDETERMINED. Схема JSON B2 не расширялась; уточнения mock-семантики описаны в INTEGRATION_NOTES.md.

Для живого HTTP-приёмочного прогона на Oracle host:

```bash
python -m student_b.live_check --station YOUR_VERIFIED_STATION
```

Клиент использует TRACE_API_KEY из окружения и только loopback HTTP. При временно включённом echo можно добавить --check-echo --expected-count со свежим независимым COUNT. Он создаёт два RAM-кейса с явно приёмочными сообщениями; HTTP timeout не отменяет Oracle call. Независимый SQL A4 берётся у команды A. Остальная приёмка — LIVE_ACCEPTANCE.md.

A_SOURCE_PROVENANCE.json содержит hashes runtime-модулей A. Эталонные тесты/live reports A, история и devtools сюда не включены. Для сборки переносите student_b, backend/app и contracts/b2 с сохранением структуры. Перед заменой общих файлов сравните версии команды.
