# Отчёт по минимальной поставке B

2026-11-11. Production OracleSource подключает реальные функции A1/A2/A3/A6. Модули A сохранены побайтно; hashes — A_SOURCE_PROVENANCE.json. B2 model/generated schema/examples сохранены. Реализованы точная проекция NUMBER/Decimal, immutable capture/time/coverage, typed errors и loopback acceptance client.

Полная локальная сборка ранее прошла 93 B tests, 192 A reference tests, 13 optional devtools tests, 35 B2 fixtures и два smoke-сценария. В минимальной ветке python -m student_b.verify запускает 93 B tests, 35 B2 fixtures и два smoke-сценария. Полный handoff A и devtools остаются у команды. B tests включают реальные A2/A3 с подменой только драйвера и настоящий loopback HTTP сервер.

Не проверены здесь: настоящий Oracle, независимая SQL-сверка интегрированной ревизии, провайдер C и frontend D, общий handshake deadline D15. G0–G3/A8/backend DoD требуют командных доказательств. Comparison B8 условен после A7 и стабильного P0; A7 не предоставлен. Explicit conflict review работает внутренним сервисом, внешний flow согласуется с C.

Следующие совместные проверки перечислены в LIVE_ACCEPTANCE.md. Минимальная поставка не содержит историю, devtools, private A live evidence, его SQL reference/копию архива, .env, caches или virtualenv.
