# Student C — Copilot/агент, MCP и полный путь диагностики

Папка C, по образцу `student_b/`: самодостаточная, запускается **из `student_c/`**. Общие файлы репозитория (`backend/app/*` студента A, `student_b/`, `contracts/`, `docs/`) **не изменены**.

## Что здесь

| Папка | Содержимое |
| --- | --- |
| `backend/app/` | FastAPI + MCP-сервер (`/mcp`) поверх одних и тех же сервисных функций; Oracle только SELECT; расчёты `Decimal`; доказательства, случаи в памяти, сводка |
| `copilot/` | Инструкции агента и описания инструментов (для Copilot Studio и временного клиента) |
| `harness/` | Временный чат-клиент: модель через OpenAI-совместимый API ↔ наш `/mcp` |
| `scripts/` | `create_readonly_user.sql` — пользователь Oracle `TRACE_RO` только с SELECT |
| `tests/` | 51 unit-тест (ожидаемые значения посчитаны вручную) |
| `docs/` | Журнал решений C, инструкции запуска, настройка модели, сценарий демо, план C |

**Пересечение с A и B.** Студент C какое-то время работал один и собрал весь путь сам, поэтому `backend/app/oracle_repo.py`, `schemas.py` и логика случаев здесь — **отдельная реализация C**, не правка кода A или B. Импортируется собственный пакет `student_c/backend/app` (проверено при запуске из `student_c/`). Объединение с кодом A/B — решение интегратора; контракт ответов (конверт, коды ошибок, формат evidence ID) соответствует общей архитектуре.

## Что проверено

- **Oracle:** `COUNT(*)` четырёх таблиц совпал с базой (29 / 150 / 1524 / 58); все 1524 значения и пределы разбираются (формат Oracle `.5`, `-.575` учтён).
- **API на живых данных:** `open_case`, `get_evidence`, `record_answer`, `get_handover`, `list_stations` — через REST и MCP.
- **ST3003:** 4 превышения у изделия `1000000203` в 10:55:13 (Angle, Vibration, Position Accuracy, Motor Speed) и Screw Count в допуске с кодом 1001. Оценка `UNDETERMINED`.
- **Агент в диалоге:** весь сценарий (случай → источник числа → ответ техника → сводка) пройден временной моделью; `record_answer` модель вызывает **сама**; ход без ожидания.

Не проверено: вызов из **Microsoft Copilot Studio** — в среде `tuke.sk (default)` нет кредитов (`EnforcementUsageCredits`), подробности в `docs/decisions.md`.

## Ключевые решения (полностью — `docs/decisions.md`)

1. **MCP вместо импорта REST в Copilot Studio** — в тенанте доступны только MCP и Workflow.
2. **Временная модель вместо Copilot** (согласовано с организаторами): `gpt-oss-120b`, `gpt-oss-20b`, `qwen3.8-27b` на Groq через локальный маршрутизатор FreeLLMAPI. Подписывается как замена Copilot.
3. **Отправка данных HACKATON в Groq** разрешена организаторами.
4. **Смысл кода 1001, пределов вмешательства/брака, часового пояса** неизвестен — показываем как есть, не интерпретируем.
5. **Один вызов модели на ход:** бэкенд отдаёт готовый текст (`message`), клиент показывает его без пересказа — ни одно число не меняется по дороге.

## Запуск

Подробно: `docs/run_backend.md` (бэкенд) и `docs/llm_router_setup.md` (модель). Коротко, из `student_c/`:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend\requirements.txt -r harness\requirements.txt
# переменные окружения: TRACE_API_KEY, ORACLE_USER, ORACLE_PASSWORD (+ OPENAI_* для чата) — см. docs
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
.venv\Scripts\python.exe harness\chat_openai.py
.venv\Scripts\python.exe -m unittest discover -s tests -t .
```

## Безопасность

- Секреты только в переменных окружения; `.gitignore` исключает `.env`, ключи, дампы, `.venv`.
- Каждый маршрут, кроме `/healthz`, требует заголовок `X-API-Key`; в логах нет заголовков и ключей.
- Временный клиент принимает ответы только от разрешённых маршрутов модели и пропускает данные MAGNA к модели только при `TRACE_ALLOW_REAL_DATA=1`.
