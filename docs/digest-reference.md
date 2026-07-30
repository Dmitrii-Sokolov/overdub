# The route-D reference digest

User-supplied, 2026-07-30 — the document route D's format was taken from, and the ONE case where a
digest can be scored against something rather than admired. Read it before changing anything in
`.claude/workflows/digest-videos.js`.

**What it is.** A hand-written Russian digest of `work/fGKNUvivvnc` — "Interpretability:
Understanding how AI models think", Anthropic, 59.0 min, 691 sentences, upload 2025-08-15. The
transcript is on disk, so the whole measurement is reproducible offline: run the read+compress chain
on that id and compare.

**How to score it — count FINDINGS, not words.** The six the reference carries:

1. generalization over memorization — the "6+9" circuit firing on the 1959-journal volume-6 year
2. a language of thought — "big" shared across English/French/Japanese, separate subnets in small models
3. forward planning — the rhyme picked before the second line, and the rabbit→green substitution
4. unfaithful reasoning — the hinted "answer is 4" and the model working backwards
5. hallucination mechanics — "best guess" and "do I know this" as two weakly connected circuits
6. Plan A / Plan B — predictable on familiar requests, other machinery on hard ones

Opus scored **5 of 6** on its first read pass (2026-07-30), missing (6); the run after that found all
six, and a blind character cap then deleted (6) out of the tail of its point — which is how the cap's
damage was discovered. Do not read a perfect match as the target: the reference was written by someone
who WATCHED the video, while the pipeline reads an ASR transcript, and the digests have twice produced
caveats the reference does not carry (the 20% microscope figure, and that this is Anthropic's own
podcast about Anthropic's own paper with no external skeptic).

**Do not paste any of this into a prompt.** Route D's prompt examples are deliberately about an
invented video: the first draft used this document's headline and two of its bullet titles as examples,
i.e. handed the agent two of the six answers on exactly the video used to judge the prompt.

---

**Подкаст Anthropic, ~59 мин: трое исследователей interpretability (экс-нейробиолог, ML-инженер, математик) о том, что происходит внутри Claude.**

Центральный тезис: «предсказание следующего слова» — технически верное, но бесполезное описание. Модель не запрограммирована, а выращена обучением, поэтому её изучают как организм — «биология нейросетей». Внутри находят переиспользуемые концепты и вычисления, а не базу заготовленных ответов.

Ключевые находки:

- **Обобщение вместо запоминания.** Контур «6+9» срабатывает и в арифметике, и при вычислении года выпуска шестого тома журнала, основанного в 1959-м: модель хранит факт и считает на лету.
- **Язык мысли.** Концепт «большой» общий для английского, французского, японского. В маленьких моделях языки — отдельные подсети; с ростом масштаба они сливаются в универсальное ядро с переводом на выходе.
- **Планирование вперёд.** В рифмованном двустишии модель выбирает финальную рифму до начала второй строки. Подменяешь внутренний концепт «rabbit» на «green» — она связно перестраивает всю строку.
- **Неверность рассуждений.** На сложной задаче с подсказкой «ответ вроде 4» модель пишет правдоподобное «решение», а внутри работает задом наперёд — подгоняет шаги под желаемый ответ. Видимый chain-of-thought — «мысли вслух», не реальный процесс.
- **Механика галлюцинаций.** Контуры «дай лучшую догадку» и «знаю ли я это вообще» почти не связаны; второй иногда ошибается, когда модель уже закоммитилась отвечать.
- **Plan A / Plan B.** На привычных запросах поведение предсказуемо, на трудных модель молча переключается на другие механизмы — доверие, наработанное на Plan A, не переносится.

Зачем: детектировать намерения (обман, шантаж) до их реализации и обосновать доверие к агентам, чей код никто не читает построчно. Честная оговорка: «микроскоп» работает ~20% времени, изучали пока Claude 3.5 Haiku. Графы схем — на Neuronpedia.

**Стоит смотреть, если** нужны детали экспериментов и живая дискуссия «думает ли модель» — в дайджест не вошла аргументация обеих позиций.
