"""Labeled questions used only to report an honest score for "Ask your shop" — never to tune it.

Written before any question-reading code. Not edited afterward to make a score look better.

The shop: the demo shop (app/demo/demo_shop.py): branches "Casablanca - Maarif", "Rabat - Agdal",
"Marrakech - Gueliz"; categories Filters, Oils, Ignition, Brakes, Lighting, Suspension, Engine,
Transmission, Electrical, Cooling, Air conditioning, Visibility.

Each line: (language, the question as typed, the right question type, the right filters).
- part: the words the person used for the part, as typed (typos kept). Compared without little
  words ("de", "the", "من"...), accents or case.
- category / branch: the shop's own name for it.
- period: today, yesterday, this_week, last_week, this_month, last_month, this_year.
- A filter left out means "not asked". Forecasts always look 30 days ahead, so "next month" is not a period.
- "this month vs last month" is sales_vs_last with period this_month (compared with the one before).
Questions we can't answer (customers, staff, changing data, off-topic) are "cannot_answer".
Languages: en, fr, ar (Modern Standard Arabic), darija (Moroccan, in Latin letters or Arabic script).
"""

BlindQuestion = tuple[str, str, str, dict[str, str]]

CASA = "Casablanca - Maarif"
RABAT = "Rabat - Agdal"
MARRAKECH = "Marrakech - Gueliz"

BLIND_QUESTIONS: list[BlindQuestion] = [
    # English
    ("en", "How many oil filters did we sell last month?", "sales_of", {"part": "oil filters", "period": "last_month"}),
    ("en", "sales of brake pads this week in Rabat", "sales_of", {"part": "brake pads", "branch": RABAT, "period": "this_week"}),
    ("en", "how much did the Electrical category sell this year", "sales_of", {"category": "Electrical", "period": "this_year"}),
    ("en", "how many spark plgus did we sel yesterday", "sales_of", {"part": "spark plgus", "period": "yesterday"}),
    ("en", "sales last week in casablanca", "sales_of", {"branch": CASA, "period": "last_week"}),
    ("en", "what are our best sellers this month?", "best_sellers", {"period": "this_month"}),
    ("en", "top selling filters in Casablanca", "best_sellers", {"category": "Filters", "branch": CASA}),
    ("en", "whats running out?", "running_out", {}),
    ("en", "which parts will run out soon in marrakech", "running_out", {"branch": MARRAKECH}),
    ("en", "What should I order and how much will it cost?", "what_to_order", {}),
    ("en", "what do we need to order for brakes", "what_to_order", {"category": "Brakes"}),
    ("en", "how many alternators do we have in stock", "stock_of_part", {"part": "alternators"}),
    ("en", "stock of battery 70ah in rabat", "stock_of_part", {"part": "battery 70ah", "branch": RABAT}),
    ("en", "which parts are not selling at all", "dead_stock", {}),
    ("en", "dead stock in cooling", "dead_stock", {"category": "Cooling"}),
    ("en", "any open alerts?", "open_alerts", {}),
    ("en", "alerts for Casablanca", "open_alerts", {"branch": CASA}),
    ("en", "which deliveries are late", "late_deliveries", {}),
    ("en", "how many clutch kits will we sell next month", "forecast_of_part", {"part": "clutch kits"}),
    ("en", "forecast for wiper blades in marrakesh", "forecast_of_part", {"part": "wiper blades", "branch": MARRAKECH}),
    ("en", "are sales up compared to last week", "sales_vs_last", {"period": "this_week"}),
    ("en", "brake pads sales this month vs last month", "sales_vs_last", {"part": "brake pads", "period": "this_month"}),
    ("en", "who is our best customer?", "cannot_answer", {}),
    ("en", "what's the weather tomorrow", "cannot_answer", {}),
    ("en", "delete all the old parts", "cannot_answer", {}),
    # French
    ("fr", "Combien de filtres à huile on a vendu le mois dernier ?", "sales_of", {"part": "filtres à huile", "period": "last_month"}),
    ("fr", "ventes des plaquettes de frein cette semaine à Rabat", "sales_of", {"part": "plaquettes de frein", "branch": RABAT, "period": "this_week"}),
    ("fr", "ventes de la catégorie freinage cette année", "sales_of", {"category": "Brakes", "period": "this_year"}),
    ("fr", "ventes d'hier", "sales_of", {"period": "yesterday"}),
    ("fr", "quelles sont les meilleures ventes ce mois-ci", "best_sellers", {"period": "this_month"}),
    ("fr", "les produits les plus vendus à Marrakech", "best_sellers", {"branch": MARRAKECH}),
    ("fr", "qu'est-ce qui va bientôt être en rupture ?", "running_out", {}),
    ("fr", "quelles pièces vont manquer à Casa", "running_out", {"branch": CASA}),
    ("fr", "qu'est ce que je dois commander et combien ça coûte", "what_to_order", {}),
    ("fr", "commande à passer pour les filtres", "what_to_order", {"category": "Filters"}),
    ("fr", "combien d'alternateurs en stock à Rabat", "stock_of_part", {"part": "alternateurs", "branch": RABAT}),
    ("fr", "stock batterie 70ah", "stock_of_part", {"part": "batterie 70ah"}),
    ("fr", "stok des amortiseurs", "stock_of_part", {"part": "amortiseurs"}),
    ("fr", "quelles pièces ne se vendent plus", "dead_stock", {}),
    ("fr", "stock mort dans l'électrique", "dead_stock", {"category": "Electrical"}),
    ("fr", "y a-t-il des alertes ouvertes ?", "open_alerts", {}),
    ("fr", "livraisons en retard", "late_deliveries", {}),
    ("fr", "prévision des ventes pour les kits d'embrayage", "forecast_of_part", {"part": "kits d'embrayage"}),
    ("fr", "combien de bougies on va vendre le mois prochain à Casablanca", "forecast_of_part", {"part": "bougies", "branch": CASA}),
    ("fr", "les ventes de ce mois par rapport au mois dernier", "sales_vs_last", {"period": "this_month"}),
    ("fr", "quel est le meilleur client ?", "cannot_answer", {}),
    ("fr", "change le prix du filtre à huile", "cannot_answer", {}),
    # Arabic
    ("ar", "كم بعنا من فلاتر الزيت الشهر الماضي؟", "sales_of", {"part": "فلاتر الزيت", "period": "last_month"}),
    ("ar", "مبيعات وسادات الفرامل هذا الأسبوع في الرباط", "sales_of", {"part": "وسادات الفرامل", "branch": RABAT, "period": "this_week"}),
    ("ar", "مبيعات اليوم", "sales_of", {"period": "today"}),
    ("ar", "مبيعات قسم الكهرباء هذه السنة", "sales_of", {"category": "Electrical", "period": "this_year"}),
    ("ar", "ما هي المنتجات الأكثر مبيعا هذا الشهر؟", "best_sellers", {"period": "this_month"}),
    ("ar", "الأكثر مبيعا في مراكش", "best_sellers", {"branch": MARRAKECH}),
    ("ar", "ما هي القطع التي ستنفد قريبا؟", "running_out", {}),
    ("ar", "ماذا يجب أن أطلب وكم التكلفة؟", "what_to_order", {}),
    ("ar", "ماذا يجب أن نطلب من قسم الفرامل", "what_to_order", {"category": "Brakes"}),
    ("ar", "كم عندنا من البطاريات في المخزون؟", "stock_of_part", {"part": "البطاريات"}),
    ("ar", "مخزون شمعات الاشعال في الدار البيضاء", "stock_of_part", {"part": "شمعات الاشعال", "branch": CASA}),
    ("ar", "ما هي القطع التي لا تباع؟", "dead_stock", {}),
    ("ar", "المخزون الراكد في قسم التبريد", "dead_stock", {"category": "Cooling"}),
    ("ar", "هل هناك تنبيهات مفتوحة؟", "open_alerts", {}),
    ("ar", "التنبيهات في الرباط", "open_alerts", {"branch": RABAT}),
    ("ar", "التوصيلات المتأخرة من الموردين", "late_deliveries", {}),
    ("ar", "توقعات مبيعات مساحات الزجاج", "forecast_of_part", {"part": "مساحات الزجاج"}),
    ("ar", "مقارنة مبيعات هذا الأسبوع بالأسبوع الماضي", "sales_vs_last", {"period": "this_week"}),
    ("ar", "من هو أفضل موظف؟", "cannot_answer", {}),
    ("ar", "احذف كل القطع القديمة", "cannot_answer", {}),
    # Darija
    ("darija", "chhal bi3na mn filtre a huile had chhar", "sales_of", {"part": "filtre a huile", "period": "this_month"}),
    ("darija", "شحال بعنا من البلاكيط الشهر اللي فات", "sales_of", {"part": "البلاكيط", "period": "last_month"}),
    ("darija", "بيع ليوم", "sales_of", {"period": "today"}),
    ("darija", "chhal bi3na mn les filtres f rabat had l3am", "sales_of", {"category": "Filters", "branch": RABAT, "period": "this_year"}),
    ("darija", "chno li kaytba3 bzaf had simana", "best_sellers", {"period": "this_week"}),
    ("darija", "اشنو اللي كيتباع بزاف ف مراكش", "best_sellers", {"branch": MARRAKECH}),
    ("darija", "chno li ghadi ysali", "running_out", {}),
    ("darija", "اشنو اللي قرب يسالي ف الرباط", "running_out", {"branch": RABAT}),
    ("darija", "chno khassni ncommandi", "what_to_order", {}),
    ("darija", "شحال غادي تكلفني الكوموند", "what_to_order", {}),
    ("darija", "chhal 3ndna mn batri f stock", "stock_of_part", {"part": "batri"}),
    ("darija", "واش عندنا الدينامو ف كازا", "stock_of_part", {"part": "الدينامو", "branch": CASA}),
    ("darija", "chno li ma kaytba3ch", "dead_stock", {}),
    ("darija", "السلعة اللي ناعسة ف الفرانات", "dead_stock", {"category": "Brakes"}),
    ("darija", "kayna chi alerte?", "open_alerts", {}),
    ("darija", "التنبيهات ديال كازا", "open_alerts", {"branch": CASA}),
    ("darija", "chi livraison m3etla?", "late_deliveries", {}),
    ("darija", "chhal ghadi nbi3o mn amortisseur chhar jay", "forecast_of_part", {"part": "amortisseur"}),
    ("darija", "التوقعات ديال الكومبريسور", "forecast_of_part", {"part": "الكومبريسور"}),
    ("darija", "wach l bi3 tla3 3la simana li fatet", "sales_vs_last", {"period": "this_week"}),
    ("darija", "chkoun ahsan client", "cannot_answer", {}),
    ("darija", "bdel lprix dyal batri", "cannot_answer", {}),
    ("darija", "ach kayn f lmatch lyouma", "cannot_answer", {}),
]
