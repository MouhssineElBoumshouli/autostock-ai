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

| | gpt-oss-120b, 1st run | gpt-oss-120b, final (2nd run + 9 Nov) | qwen3.8-27b |
|---|---|---|---|
| Answered (Groq allowance) | 48 of 50 | 49 of 50 (1 blocked by the check) | 30 of 36 asked |
| Right, checked automatically | 24/39 | 31/40 | 24/26 |
| Right after reading every answer | — | 42/49, 6 partial, **1 wrong** | 28/30, 2 partial, 0 wrong |
| Numbers no tool gave, shown | 0 (2 blocked) | 0 (1 blocked) | 0 |
| Right language | 45/48 | 47/49 | 30/30 |
| Short and plain (≤ 3 sentences) | 46/48 | 47/49 | 28/30 |
| Seconds per answer (median / max) | 1.1 / 6.3 | 1.2 / 3.7 | 1.5 / 22.5 |
| Tokens per answer (median) | 2 730 | 3 860 | 5 520 |

- **1st run → fixes:** real wrong answers came from the app's side: the model read one row as the total
  ("51 batteries" for 657), "the period before" October was 31 days ending 30 Sep ("‑0 %" instead of +3 %),
  it worked out "last week" itself and got the dates wrong, "Peugeot" went in the brand field. Fixed: totals
  are named `total_…`, whole months compare with whole months, the app gives the exact dates of common
  periods, the shop's part types and brands are in the instructions.
- **The 1 wrong answer (2nd run):** "Why did battery sales go up?" counted Batterie 60Ah only (732) as if it were
  all batteries (1 389). Fixed: a general word counts every type starting with it (test added).
- **Re-checked on 9 Nov (1 Groq answer):** the total is now right (1 389, both types), but the model said sales
  "rose 75 (+5 %)" when they fell 75 (−5 %). The number check accepted it because a change is allowed without its
  sign. Fixed after: each comparison carries its direction, and an answer that only says the opposite way is
  sent back once, then replaced by the app's answer (tests added). **Not re-measured** (allowance kept for the owner).
- Partial answers: the right numbers but a weak period (this week = 2 days imported), a list of names without
  their pieces, or a page name that doesn't exist ("Prices section", "supprimer les alertes").
- "busy" (6 qwen answers): Groq's 8 000 tokens a minute, from asking questions back to back. One person asking
  waits up to 20 s and gets the answer; two people at once may get the app's simpler answer.

**Model:** gpt-oss-120b stays the default (the owner's choice, ~30 % fewer tokens, so more answers a day);
qwen3.8-27b gave fuller "why" and open answers and is one line in `.env` (`GROQ_MODEL`).
llama-3.3-70b-versatile no longer exists on this Groq account, so it could not be compared.

**Questions a day on the free tier:** about 200 000 ÷ 3 900 ≈ **50 answers a day** with gpt-oss-120b, about
35 with qwen (1 000 requests a day is not the limit). Settings shows what is left today.

## The owner's 10 questions, old vs new

Old: what his shop answered on 8 Nov. New: gpt-oss-120b on the copy of his shop, 9 Nov, each asked once
("Et le mois dernier ?" right after the question before it).

| Question | Old answer | New answer | Verdict |
|---|---|---|---|
| Combien il nous reste de filtres à huile pour Dacia Logan à Rabat ? | Il reste 6 281 pièces … (WRONG: every Logan part) | Il reste 551 filtres à huile pour Dacia Logan au magasin de Rabat - Agdal. | right |
| Qu'est-ce qui s'est le mieux vendu en octobre à Marrakech ? | Je n'ai pas compris la question. | Le meilleur vendeur en octobre à Marrakech est l'« Huile moteur 5W30 5L » avec 1 531 pièces vendues. | right (by type) |
| Comment va le magasin cette semaine ? | 20 674 pièces vendues, une semaine normale c'est 20 668 … | Cette semaine (2–3 nov., ventes après le 3 nov. pas encore importées) : 6 872 pièces, 2 367 235 MAD, marge 30 %. | right, but no "normal week" to compare |
| Et le mois dernier ? | 92 032 pièces vendues, en hausse de 3 % … | Octobre : 92 032 pièces, 32 152 455 MAD, marge 30 % ; en tête Filtre à huile (6 787), Huile 5W30 (6 669), Huile 10W40 (6 466). | right, no comparison |
| Pourquoi les ventes de plaquettes de frein ont baissé ? | Je n'ai pas compris la question. | (blocked by the number check: a "9" no tool gave → the app's own answer is shown) | blocked |
| Quelles pièces ne bougent plus depuis longtemps ? | Je n'ai pas compris la question. | « 1 272 pièces sont en rupture depuis le 1 janvier (3 816 jours) » | **wrong**: read stock-out days, not dead stock (fixed after in the instructions, not re-measured) |
| Compare Casablanca et Rabat sur les batteries. | Casablanca vend plus : 613 … devant Rabat (459) … | Casablanca 45 batteries (25 × 70Ah, 20 × 60Ah), Rabat 40 (15 × 70Ah, 25 × 60Ah), du 2 au 3 nov. | right numbers, too short a period |
| chhal ba9i 3andna mn amortisseur dyal clio f casa | لم أفهم السؤال | Amortisseur dyal Clio f Casa kayn 14 7aja. | right |
| ما هي القطع الأكثر مبيعا في أكتوبر؟ | لم أفهم السؤال | أعلى القطع مبيعًا في أكتوبر: Filtre à huile، Huile moteur 5W30 5L، Huile moteur 10W40 5L، Filtre à gasoil، Bougie d'allumage | right, without the pieces |
| Who is our biggest customer? | I can't do that … nothing about customers. | I'm sorry, but the shop's data doesn't include information about customers. | right |

Old: 2 good, 5 not understood, 1 wrong. New: 7 right (3 of them thinner than they should be), 1 partial (right
numbers, 2-day period), 1 blocked by the check, 1 wrong (a wrong reading, every number from a tool), 0 numbers made up. 25 Groq answers used on 9 Nov.
