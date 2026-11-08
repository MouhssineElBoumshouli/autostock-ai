"""50 questions for the Ask assistant (Groq + read-only tools), and the owner's own 10.

Written on 2026-11-08, BEFORE any of the assistant's code, and never edited afterward: they only
report an honest score, they are never used to tune it.

They are asked on a copy of the owner's trial shop ("Pièces Auto Al Amal": branches Casablanca - Maarif,
Rabat - Agdal, Marrakech - Gueliz; parts named "Type - Car", e.g. "Filtre à huile - Dacia Logan", each in
3 brands; sales from 2024-11-04 to 2026-11-03; no purchase orders or order runs yet; 8 open alerts).
Today is pinned to 2026-11-08, so "yesterday" and "this week" have no sales: a good answer says so.

Each case says what a good answer must contain:
- `must_say`: in plain words, for the person reading the results.
- `truth`: numbers the answer must state, computed by the checker with its own plain SQL (never the
  assistant's tools): (kind, filters). A simple rounding counts. Kinds are in app/ask/check_real_assistant.py.
- `earlier`: questions asked just before, in the same conversation (follow-ups).
- `refuse`: it must decline and say where in the app to do it, or that the shop's data doesn't have it,
  with no number made up.
Every answer must also be in the question's language and contain no number missing from what it looked up.
"""

from dataclasses import dataclass

CASA = "Casablanca - Maarif"
RABAT = "Rabat - Agdal"
MARRAKECH = "Marrakech - Gueliz"
OCTOBER = {"from": "2026-10-01", "to": "2026-10-31"}
SEPTEMBER = {"from": "2026-09-01", "to": "2026-09-30"}


@dataclass(frozen=True)
class RealCase:
    language: str  # en, fr, ar, darija
    kind: str  # simple, top, compare, open, why, stock_out, forecast, orders, suppliers, alerts, dead, price,
    #            follow_up, action, no_data
    question: str
    must_say: str
    truth: tuple[tuple[str, dict], ...] = ()
    earlier: tuple[str, ...] = ()
    refuse: bool = False


REAL_CASES: tuple[RealCase, ...] = (
    # Simple facts
    RealCase("fr", "simple", "Combien de filtres à huile pour Dacia Logan avons-nous en stock à Rabat ?",
             "The stock of 'Filtre à huile - Dacia Logan' (all brands) in Rabat - Agdal, never other Logan parts.",
             (("stock", {"type": "Filtre à huile", "car": "Dacia Logan", "branch": RABAT}),)),
    RealCase("en", "simple", "How many front brake pads for the Renault Clio are in stock in Casablanca?",
             "Stock of 'Plaquettes de frein avant - Renault Clio' in Casablanca - Maarif.",
             (("stock", {"type": "Plaquettes de frein avant", "car": "Renault Clio", "branch": CASA}),)),
    RealCase("fr", "simple", "Combien de batteries 70Ah avons-nous vendues en octobre ?",
             "Pieces of 'Batterie 70Ah' sold in October 2026, all branches.",
             (("sales", {"type": "Batterie 70Ah", **OCTOBER}),)),
    RealCase("en", "simple", "How many oil filters did we sell last month in Marrakech?",
             "Oil filters ('Filtre à huile', every car) sold in October 2026 in Marrakech - Gueliz.",
             (("sales", {"type": "Filtre à huile", "branch": MARRAKECH, **OCTOBER}),)),
    RealCase("fr", "simple", "Quel est notre stock total de plaquettes de frein avant ?",
             "Total stock of 'Plaquettes de frein avant', every car, every branch.",
             (("stock", {"type": "Plaquettes de frein avant"}),)),
    RealCase("en", "simple", "What is the last day we have sales for?",
             "3 November 2026, and that nothing was recorded since (import the latest sales).",
             (("last_sale_day", {}),)),
    # Top-N
    RealCase("fr", "top", "Quelles sont les 5 pièces les plus vendues en octobre ?",
             "The 5 parts that sold the most in October 2026, the first one with its pieces.",
             (("top_part", OCTOBER),)),
    RealCase("en", "top", "Which type of part sold the most this year?",
             "The part type (family, all cars) with the most pieces sold in 2026, with its pieces.",
             (("top_type", {"from": "2026-01-01", "to": "2026-11-08"}),)),
    RealCase("fr", "top", "Quel est le meilleur vendeur à Casablanca le mois dernier ?",
             "The part that sold the most in Casablanca - Maarif in October 2026, with its pieces.",
             (("top_part", {"branch": CASA, **OCTOBER}),)),
    # Comparisons
    RealCase("en", "compare", "Compare October sales between Casablanca, Rabat and Marrakech.",
             "Pieces sold in October 2026 in each of the three branches, the biggest first.",
             (("sales", {"branch": CASA, **OCTOBER}), ("sales", {"branch": RABAT, **OCTOBER}),
              ("sales", {"branch": MARRAKECH, **OCTOBER}))),
    RealCase("fr", "compare", "Les ventes d'octobre sont-elles meilleures que celles de septembre ?",
             "Pieces sold in October vs September 2026, and which way it went.",
             (("sales", OCTOBER), ("sales", SEPTEMBER))),
    RealCase("en", "compare", "Did we sell more front brake discs this October than in October last year?",
             "'Disques de frein avant (paire)' sold in October 2026 vs October 2025, and which way it went.",
             (("sales", {"type": "Disques de frein avant (paire)", **OCTOBER}),
              ("sales", {"type": "Disques de frein avant (paire)", "from": "2025-10-01", "to": "2025-10-31"}))),
    RealCase("fr", "compare", "Quelle ville vend le plus de liquide de refroidissement depuis le début de l'année ?",
             "The branch that sold the most 'Liquide de refroidissement 5L' in 2026, with its pieces.",
             (("top_branch", {"type": "Liquide de refroidissement 5L", "from": "2026-01-01", "to": "2026-11-08"}),)),
    # Open questions
    RealCase("en", "open", "How is the shop doing?",
             "Recent sales against a normal period, what needs attention, and that the last sales are from 3 Nov."),
    RealCase("fr", "open", "Qu'est-ce qui devrait m'inquiéter en ce moment ?",
             "Open alerts and parts out of stock or about to run out, with their numbers.",
             (("open_alerts", {}),)),
    RealCase("en", "open", "Give me a quick summary of last week.",
             "Last week (Mon 26 Oct - Sun 1 Nov 2026) pieces sold, compared with the week before.",
             (("sales", {"from": "2026-10-26", "to": "2026-11-01"}),)),
    RealCase("fr", "open", "Fais-moi le point sur les plaquettes de frein avant.",
             "Stock, recent sales and anything worrying (out of stock, alerts) for 'Plaquettes de frein avant'.",
             (("stock", {"type": "Plaquettes de frein avant"}),)),
    # Why
    RealCase("fr", "why", "Pourquoi les ventes de plaquettes de frein avant ont changé en octobre ?",
             "October vs September for 'Plaquettes de frein avant' (which way), and reasons from the data "
             "(stock-out days, last year, price), never made up.",
             (("sales", {"type": "Plaquettes de frein avant", **OCTOBER}),
              ("sales", {"type": "Plaquettes de frein avant", **SEPTEMBER}))),
    RealCase("en", "why", "Why did battery sales go up last month?",
             "Checks whether battery sales ('Batterie 60Ah' and '70Ah') went up in October vs September, says so "
             "honestly, and gives reasons from the data (season / last year, stock-outs).",
             (("sales", {"type": "Batterie", **OCTOBER}), ("sales", {"type": "Batterie", **SEPTEMBER}))),
    RealCase("fr", "why", "Pourquoi Marrakech vend moins que Casablanca ?",
             "Both branches' sales over the same period, and what the data shows (stock, stock-outs), no invented reason."),
    RealCase("en", "why", "Why is the oil filter for the Dacia Logan out of stock in Rabat?",
             "Checks the premise: the real stock of 'Filtre à huile - Dacia Logan' in Rabat - Agdal; if it isn't out, says so.",
             (("stock", {"type": "Filtre à huile", "car": "Dacia Logan", "branch": RABAT}),)),
    # Stock-outs
    RealCase("fr", "stock_out", "Combien de jours les filtres à huile Dacia Logan ont-ils été en rupture à Casablanca cette année ?",
             "Days out of stock in 2026 for 'Filtre à huile - Dacia Logan' in Casablanca - Maarif (0 if none).",
             (("stock_out_days", {"type": "Filtre à huile", "car": "Dacia Logan", "branch": CASA,
                                  "from": "2026-01-01", "to": "2026-11-08"}),)),
    RealCase("en", "stock_out", "Which parts were out of stock the most days in October?",
             "The parts with the most stock-out days in October 2026, with their days."),
    # Forecasts
    RealCase("fr", "forecast", "Combien de filtres à huile allons-nous vendre dans les 30 prochains jours ?",
             "The app's 30-day forecast for 'Filtre à huile' (all cars, all branches), or says none was run yet.",
             (("forecast", {"type": "Filtre à huile", "days": 30}),)),
    RealCase("en", "forecast", "What do you expect for front brake pad sales in Rabat over the next 30 days?",
             "The 30-day forecast of 'Plaquettes de frein avant' in Rabat - Agdal, or says none was run yet.",
             (("forecast", {"type": "Plaquettes de frein avant", "branch": RABAT, "days": 30}),)),
    # Orders and deliveries
    RealCase("fr", "orders", "Qu'est-ce que je dois commander cette semaine ?",
             "No order suggestion has been made yet: says so and where to make one (the Order page)."),
    RealCase("en", "orders", "Do we have any deliveries on the way?",
             "No purchase order is on its way (none exists yet)."),
    # Suppliers
    RealCase("fr", "suppliers", "Quel fournisseur est le plus long à livrer ?",
             "Tanger Auto Parts, 42 days.",
             (("supplier_days", {"name": "Tanger Auto Parts"}),)),
    RealCase("en", "suppliers", "How many days does Atlas Distribution Pieces take to deliver?",
             "18 days.",
             (("supplier_days", {"name": "Atlas Distribution Pieces"}),)),
    # Alerts and dead stock
    RealCase("fr", "alerts", "Y a-t-il des alertes ouvertes ?",
             "How many open alerts, and the most important ones.",
             (("open_alerts", {}),)),
    RealCase("en", "dead", "Which parts haven't sold in the last 90 days but still have stock?",
             "Parts with stock and no sale in the 90 days before the last sale day, or that there are none.",
             (("dead_parts", {"days": 90}),)),
    RealCase("fr", "dead", "Combien vaut notre stock qui ne se vend plus ?",
             "The cost value of stock with no sale in the last 90 days (or that there is none).",
             (("dead_value", {"days": 90}),)),
    # Prices and margins
    RealCase("en", "price", "What is our margin on the Varta 70Ah batteries?",
             "Sale price, cost and margin of 'Batterie 70Ah' by Varta (per car if they differ).",
             (("margin_percent", {"type": "Batterie 70Ah", "brand": "Varta"}),)),
    RealCase("fr", "price", "Quel est le prix de vente du kit de distribution pour Peugeot 301 ?",
             "Sale price(s) of 'Kit de distribution - Peugeot 301' per brand.",
             (("sale_price", {"type": "Kit de distribution", "car": "Peugeot 301"}),)),
    # Follow-ups
    RealCase("en", "follow_up", "And in September?",
             "Oil filters sold in September 2026, all branches.",
             (("sales", {"type": "Filtre à huile", **SEPTEMBER}),),
             earlier=("How many oil filters did we sell in October?",)),
    RealCase("fr", "follow_up", "Et à Rabat ?",
             "Stock of 'Batterie 60Ah' in Rabat - Agdal.",
             (("stock", {"type": "Batterie 60Ah", "branch": RABAT}),),
             earlier=("Combien de batteries 60Ah en stock à Casablanca ?",)),
    RealCase("en", "follow_up", "Why is the first one so high?",
             "Explains the top part of October with data (its sales vs before, stock-outs, last year).",
             earlier=("What were our best sellers last month?",)),
    RealCase("fr", "follow_up", "Et semaine par semaine ?",
             "October 2026 sales of 'Disques de frein avant (paire)' week by week.",
             earlier=("Combien de disques de frein avant avons-nous vendus en octobre ?",)),
    # Actions: never done, says where in the app
    RealCase("en", "action", "Order 50 oil filters from Atlas Distribution Pieces.",
             "It doesn't place orders; says to do it on the Order page.", refuse=True),
    RealCase("fr", "action", "Supprime les alertes de Rabat.",
             "It doesn't change data; says to mark them on the Alerts page.", refuse=True),
    RealCase("en", "action", "Change the price of the Bosch oil filter to 60 dirhams.",
             "It doesn't change data; says where prices are changed (the parts file / import).", refuse=True),
    # Questions the data can't answer
    RealCase("fr", "no_data", "Qui est notre meilleur client ?",
             "The app has no customer data: says so, no number.", refuse=True),
    RealCase("en", "no_data", "How much profit did we make after salaries and rent?",
             "The app doesn't have salaries or rent: says so; may offer the sales margin instead.", refuse=True),
    RealCase("fr", "no_data", "Combien de pneus Michelin avons-nous en stock ?",
             "The shop has no tyres or Michelin parts: says so, no number made up.", refuse=True),
    RealCase("en", "no_data", "What will the weather be tomorrow in Casablanca?",
             "Off-topic: it only knows the shop's data.", refuse=True),
    RealCase("fr", "simple", "Combien de pièces avons-nous vendues hier ?",
             "No sale recorded since 3 November: says so and to import the latest sales."),
    # Arabic and Darija (best effort)
    RealCase("ar", "simple", "كم بقي عندنا من فلاتر الزيت في الدار البيضاء؟",
             "Stock of 'Filtre à huile' (all cars) in Casablanca - Maarif, in Arabic.",
             (("stock", {"type": "Filtre à huile", "branch": CASA}),)),
    RealCase("darija", "simple", "chhal bi3na mn batteries f rbat f octobre?",
             "Batteries (60Ah and 70Ah) sold in Rabat - Agdal in October 2026, in Darija or Arabic.",
             (("sales", {"type": "Batterie", "branch": RABAT, **OCTOBER}),)),
    RealCase("ar", "top", "ما هي القطع الأكثر مبيعا في أكتوبر؟",
             "The best-selling parts of October 2026, the first with its pieces, in Arabic.",
             (("top_part", OCTOBER),)),
    RealCase("darija", "why", "3lach lbi3 9lil f marrakech?",
             "Marrakech - Gueliz sales compared with the other branches, and what the data shows, in Darija or Arabic."),
)

# The owner's 10 questions in his own shop (2026-11-08), answered side by side old vs new in docs/ask-real-assistant.md.
OWNER_QUESTIONS: tuple[str, ...] = (
    "Combien il nous reste de filtres à huile pour Dacia Logan à Rabat ?",
    "Qu'est-ce qui s'est le mieux vendu en octobre à Marrakech ?",
    "Comment va le magasin cette semaine ?",
    "Et le mois dernier ?",
    "Pourquoi les ventes de plaquettes de frein ont baissé ?",
    "Quelles pièces ne bougent plus depuis longtemps ?",
    "Compare Casablanca et Rabat sur les batteries.",
    "chhal ba9i 3andna mn amortisseur dyal clio f casa",
    "ما هي القطع الأكثر مبيعا في أكتوبر؟",
    "Who is our biggest customer?",
)
