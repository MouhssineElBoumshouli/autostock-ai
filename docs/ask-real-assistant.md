# Ask becomes a real assistant — measured (8 November 2026)

The owner asked 10 questions in his trial shop and said: "This is not AI at all." 2 good, 5 "Je n'ai pas
compris", 1 wrong (6 281 oil filters instead of about 550). This page says why, what changed, and how the new
assistant scored. Self-written questions, self-scored: read the scores as optimistic.

## Why the local AI was off in the shop

The AI program (Ollama) was running and had the model, but **a Windows Update installed a new NVIDIA graphics
driver on 8 Nov at 14:01–14:04 UTC while Docker was running**. From then on every attempt to load the model on
the graphics card crashed. The app's health check only asked "is the model downloaded?" (yes), so the 5
questions the keyword rule didn't know went to a model that crashed, and came back as "Je n'ai pas compris".
Restarting the AI container now fails too (NVIDIA's Docker hook crashes): **Windows must be restarted** to load
the new driver. Fixed in the app: a model that can't start now counts as off, so Ask says "AI is off" instead
of "not understood".

## The wrong sum

"filtres à huile pour Dacia Logan à Rabat" matched 112 parts: every Dacia Logan part and every oil filter
(parts matching 2 of the 3 ideas were kept). Now a part question keeps only the parts matching every word
when some do: 551 (3 brands of "Filtre à huile - Dacia Logan"). A test reproduces it (1 055 without the fix).

## What the assistant is now

Groq's free model thinks; the app's 10 READ-ONLY tools give the facts (find parts, stock, sales grouped and
compared over any period, stock-out days, forecasts, order suggestions, purchase orders, alerts, suppliers,
prices). Tools are scoped to the asker's shop, staff never get money, and they run in a read-only database
transaction. A part must match every field given (type, car, brand). Every number in the answer must come from
a tool result; otherwise the model is told which and writes again once, then the app's own answer is shown.
Comparisons carry their "why" facts (stock-out days, average price, the same dates last year). A period that
runs past the last imported sale is counted up to it and the answer says so.

## Scores on the 50 new questions

Written and committed before the assistant (`backend/app/ask/real_shop_questions.py`), asked on a copy of
the owner's shop, today pinned to 8 Nov. "Right" = says the number the plain-SQL truth gives (or refuses
properly); answers without a truth were read by me.

| | gpt-oss-120b, 1st run | gpt-oss-120b, 2nd run | qwen3.8-27b |
|---|---|---|---|
| Answered (Groq allowance) | 48 of 50 | 36 of 37 asked | 30 of 36 asked |
| Right, checked automatically | 24/39 | 22/30 | 24/26 |
| Right after reading every answer | — | 32/36, 3 partial, **1 wrong** | 28/30, 2 partial, 0 wrong |
| Numbers no tool gave, shown | 0 (2 blocked) | 0 (1 blocked) | 0 |
| Right language | 45/48 | 36/36 | 30/30 |
| Short and plain (≤ 3 sentences) | 46/48 | 34/36 | 28/30 |
| Seconds per answer (median / max) | 1.1 / 6.3 | 1.2 / 3.7 | 1.5 / 22.5 |
| Tokens per answer (median) | 2 730 | 3 870 | 5 520 |

- **1st run → fixes:** real wrong answers came from the app's side: the model read one row as the total
  ("51 batteries" for 657), "the period before" October was 31 days ending 30 Sep ("‑0 %" instead of +3 %),
  it worked out "last week" itself and got the dates wrong, "Peugeot" went in the brand field. Fixed: totals
  are named `total_…`, whole months compare with whole months, the app gives the exact dates of common
  periods, the shop's part types and brands are in the instructions.
- **The 1 wrong answer of the 2nd run:** "Why did battery sales go up?" was answered with Batterie 60Ah only
  (732) as if it were all batteries (1 389). Fixed after the run (a general word counts every type starting
  with it, and the answer says what was counted); qwen answered the same question right (1 389, down 5 %).
  **This fix is not yet re-measured** on gpt-oss-120b.
- **Not finished:** the 2nd gpt-oss-120b run stopped at 37 questions and qwen at 36 because each model's
  free daily allowance (about 200 000 tokens) ran out — my measuring used it. Run again tomorrow, it goes on
  where it stopped: `docker compose exec api python -m app.ask.check_real_assistant openai/gpt-oss-120b`.
- "busy" (6 qwen answers): Groq's 8 000 tokens a minute, from asking questions back to back. One person asking
  waits up to 20 s and gets the answer; two people at once may get the app's simpler answer.

**Model:** gpt-oss-120b stays the default (the owner's choice, ~30 % fewer tokens, so more answers a day);
qwen3.8-27b gave fuller "why" and open answers and is one line in `.env` (`GROQ_MODEL`).
llama-3.3-70b-versatile no longer exists on this Groq account, so it could not be compared.

**Questions a day on the free tier:** about 200 000 ÷ 3 900 ≈ **50 answers a day** with gpt-oss-120b, about
35 with qwen (1 000 requests a day is not the limit). Settings shows what is left today.

## The owner's 10 questions, old vs new

Old: what his shop answered on 8 Nov. New: gpt-oss-120b on the copy of his shop — only the first could be
asked before the allowance ran out; the other 9 are pending (`… check_real_assistant --owner`).

| Question | Old answer | New answer |
|---|---|---|
| Combien il nous reste de filtres à huile pour Dacia Logan à Rabat ? | Il reste 6 281 pièces … (WRONG: every Logan part) | Il reste 551 filtres à huile pour Dacia Logan à Rabat - Agdal. |
| Qu'est-ce qui s'est le mieux vendu en octobre à Marrakech ? | Je n'ai pas compris la question. | pending |
| Comment va le magasin cette semaine ? | 20 674 pièces vendues, une semaine normale c'est 20 668 … | pending |
| Et le mois dernier ? | 92 032 pièces vendues, en hausse de 3 % … | pending |
| Pourquoi les ventes de plaquettes de frein ont baissé ? | Je n'ai pas compris la question. | pending |
| Quelles pièces ne bougent plus depuis longtemps ? | Je n'ai pas compris la question. | pending |
| Compare Casablanca et Rabat sur les batteries. | Casablanca vend plus : 613 … devant Rabat (459) … | pending |
| chhal ba9i 3andna mn amortisseur dyal clio f casa | لم أفهم السؤال | pending |
| ما هي القطع الأكثر مبيعا في أكتوبر؟ | لم أفهم السؤال | pending |
| Who is our biggest customer? | I can't do that … nothing about customers. | pending |

Close equivalents among the 50, from the 2nd runs: best seller of a branch last month (both), October vs
September +3 % (both), dead stock 294 parts / 238 087,50 MAD (both), the top 5 of October with their pieces
(qwen). The actions, "best customer" and the Arabic/Darija questions were only reached in the 1st run: the 7
refusals were right; the Arabic top 5 was right; the Arabic stock (one row read as the total, 521 for 4 989) and
the Darija sales (money instead of pieces) were wrong — the kind of mistake fixed after that run, not re-measured.
