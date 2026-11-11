# Статус B перед общей сборкой

- [x] B1: auth, envelope, request IDs, health/readiness/echo и real A1 interface.
- [x] B2: canonical schemas/examples и drift checks; JSON shape сохранён.
- [x] B3: immutable evidence, private full A capture, unknown/foreign IDs, no requery.
- [x] B4: isolation, TTL/caps/locks/states, atomic updates, explicit internal conflict review.
- [x] B5: actual A3 output, max 5 findings, UNDETERMINED, один следующий шаг и handover.
- [x] B6: все пять production routes подключены к A2/A3.
- [x] B7: локальные API/driver/HTTP checks, python -m student_b.verify.
- [ ] Реальный Oracle и независимая SQL-сверка интегрированной ревизии A/D.
- [ ] C/D подтверждают API/spec/proxy/mocks и принятые time/search/null semantics.
- [ ] C интегрирует record_answer и explicit conflict flow.
- [ ] Два живых пользовательских сценария, live negatives и общая приёмка.
- [ ] D15/connector budget, A8 и G0–G3 по командным доказательствам.

B8 integration fixes выполнены локально; comparison — условный P1 после A7 и стабильного P0. Общий backend DoD не закрывается одними локальными тестами.
