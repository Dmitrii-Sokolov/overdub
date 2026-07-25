# INBOX

Tags: `[bug] [feature] [chore] [?]` — one line per entry, processed weekly.

<!-- processed 2026-07-19: 54 entries → PLAN (roadmap 3/6, backlog, deferred) / already in DECISIONS / deleted -->
<!-- processed 2026-07-20: 6 entries → PLAN roadmap 4 (the two renderer-divergence bugs merged into
     one item; they were one root cause) + PLAN roadmap 5 (repair destroys the anomaly worklist) +
     PLAN deferred (measure n_src precision first) / fixed in place (repair_window_min_sec docs) /
     DECISIONS 2026-07-20 (exit 0 on all-rejected) -->
<!-- processed 2026-07-22: both queue-page entries BUILT the same day (CHANGELOG 2026-07-22) —
     neither needed a roadmap slot: the thumb was a missing yt-dlp flag plus a glob one character
     too narrow, and the «о чём» was a fallback over prose already on disk. -->
<!-- processed 2026-07-24: the STACK.md drift entry FIXED IN PLACE, no roadmap slot — it was pure
     doc-vs-code skew in the Stage-1 skeleton. verify compute_type int8→float16 corrected (code
     ships float16 both roles since the asr role-split), an int8-is-24%-slower gotcha added, and
     the cond skeleton flipped False→True with a dedicated gotcha carrying the _guard mechanic;
     STACK is now internally consistent on both cond and int8. Code was already correct — the
     document was the only thing wrong. -->

## 2026-07-25
- [feature] правила транскрипции для open-class слов: `execute → эксекют` (18 попаданий за батч), `adventures → адвентурс`, `fields → фиелдс`, `open → опен`, `waters → вейтерс`, `buy → буи` (последнее — старое, нашлось попутно) — по уставу `pronounce.WORDS` это работа правил, а не словаря, но правило на `ex-`/`ie`/`-ute` неоднозначно в английском («exit» хочет экс, «execute» — эгз), так что нужен цикл правил С УШНОЙ проверкой и оглядкой на потолок ~55 правил; словарные фиксы 2026-07-25 этот хвост НЕ закрывают
- [?] `neg_loss` дал 19 срабатываний за батч, и все проверенные — корректные переводы с лексическим отрицанием («Hell no» → «Чёрта с два», «no matter what» → «вне зависимости от», «are not equally spaced anymore» → «перестают быть»); DECISIONS 2026-07-19 выносит его из prefer-miss по имени с ценой «одна ложная тревога за батч» — 19 это не одна, решение пересматривать в DECISIONS с этим числом, не в коде
- [bug] разбиение на предложения теряет 166 окончаний из 388 source-аномалий батча (`truncated`, кластеры в живых Q&A, где whisper не ставит терминальную пунктуацию: `2qrzI8YCVgI`, `Tu2cCEMwvHI` — «cut off mid-thought; continues into id 212» подряд); rebuild из word timestamps — наш шаг, значит это наши разрывы, в отличие от 143 `garbled` / 60 `dup_neighbour`, которые действительно whisper'а
- [feature] мерить, какая доля НЕДЕЛЬНЫХ лимитов подписки (Sonnet) уходит на прогон: route B тратит по 2 суб-агента на видео (переводчик + суммаризатор), route C — по одному, и сейчас цена батча в лимитах не видна нигде — ни в `run.json`, ни в дайджесте, ни в отчёте, хотя это ГЛАВНЫЙ дефицитный ресурс route B (машинное время дешевле: 3 ч 16 мин на 24 видео). Нужна хотя бы оценка на видео (число агентов × токены) и доля недельного лимита на батч, чтобы «влезет ли очередь на 100 видео в неделю» был расчётом, а не сюрпризом на 60-м
- [?] эффект Step 1b (`--repair-asr auto` до перевода) НЕ измерен: 17 юнитов с atempo ×1.8..×12.5 — это состояние ДО него, ничего не перезапускалось; первый route-B прогон с этим шагом и есть проверка

## 2026-07-24
- [feature] когда пайплайн станет стабильным — чистить `work/<id>/` после успешного mux: удалять только БИНАРНИКИ (`source.mkv`, `source.wav`, `source_bed.wav`, `dub_ru.wav`, `segments/`) — 99% объёма промежуточного (18.5 из 18.7 GB, json/md = копейки) ценой пересинтеза: транскрипт/перевод/саммари уцелеют в json, но переделать придётся озвучку и весь её хвост — измерено на 36 прогонах: synthesize 52.6% + verify 7.6 + mux 7.4 + separate 4.8 = 72.7% машинного wall (агентские перевод/саммари в run.json не учтены, с ними доля ниже); результат уцелеет сам (`out/` держит второй хардлинк на `output.mkv`), отдельная папка уже есть — но вход mux надо перевести `source.mkv` → `output.mkv`, иначе ре-мукс требует повторной загрузки

## 2026-07-22
- [chore] `work-exp/beam-probe/` cells predate `asr_probe.py`'s naming — `--variant beam1` re-measures instead of reusing the 24 existing cells
- [feature] `asr_probe.py` has no "compare against a git HEAD worktree" mode; the technique that settled the drift question lives only in a session scratchpad now
- [?] `asr_key` is never back-filled: a workdir whose transcribe never re-runs stays unstamped forever, so the warning can only ever cover post-2026-07-22 transcripts
