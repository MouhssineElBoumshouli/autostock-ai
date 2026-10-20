"""A second set of labeled questions for "Ask your shop", in shop-counter phrasing, all different
from app/ask/blind_test_questions.py. Used only to report an honest score — never to tune it.

Written before the rule was changed after the owner's own 48-question check. Not edited afterward.
Same shop, labels and conventions as app/ask/blind_test_questions.py.
"""

from app.ask.blind_test_questions import CASA, MARRAKECH, RABAT, BlindQuestion

BLIND_COUNTER_QUESTIONS: list[BlindQuestion] = [
    # English
    ("en", "how many front brake discs left in casa", "stock_of_part", {"part": "front brake discs", "branch": CASA}),
    ("en", "did we sell any radiators this week", "sales_of", {"part": "radiators", "period": "this_week"}),
    ("en", "total sales today", "sales_of", {"period": "today"}),
    ("en", "whats our top product in marrakech this year", "best_sellers", {"branch": MARRAKECH, "period": "this_year"}),
    ("en", "anything about to run out in the filters", "running_out", {"category": "Filters"}),
    ("en", "how much is the order going to cost us", "what_to_order", {}),
    ("en", "do we still have water pumps in rabat", "stock_of_part", {"part": "water pumps", "branch": RABAT}),
    ("en", "stuff that's been sitting on the shelf forever", "dead_stock", {}),
    ("en", "any problems flagged in rabat", "open_alerts", {"branch": RABAT}),
    ("en", "has the supplier delivery arrived, anything overdue", "late_deliveries", {}),
    ("en", "how many timing belt kits do you think we'll sell", "forecast_of_part", {"part": "timing belt kits"}),
    ("en", "is lighting selling better than last month", "sales_vs_last", {"category": "Lighting", "period": "this_month"}),
    ("en", "starter motor sales yesterday", "sales_of", {"part": "starter motor", "period": "yesterday"}),
    ("en", "can you print me an invoice", "cannot_answer", {}),
    ("en", "what's the profit margin on clutch kits", "cannot_answer", {}),
    ("en", "which employee sold the most today", "cannot_answer", {}),
    # French
    ("fr", "il nous reste combien de filtres à air ?", "stock_of_part", {"part": "filtres à air"}),
    ("fr", "on a vendu combien d'ampoules H7 aujourd'hui", "sales_of", {"part": "ampoules H7", "period": "today"}),
    ("fr", "les ventes du rayon refroidissement ce mois", "sales_of", {"category": "Cooling", "period": "this_month"}),
    ("fr", "c'est quoi qui part le plus à Casablanca", "best_sellers", {"branch": CASA}),
    ("fr", "quels articles risquent la rupture à Rabat", "running_out", {"branch": RABAT}),
    ("fr", "faut commander quoi pour l'éclairage", "what_to_order", {"category": "Lighting"}),
    ("fr", "montant de la prochaine commande", "what_to_order", {}),
    ("fr", "les pièces qui dorment en stock", "dead_stock", {}),
    ("fr", "y a des alertes sur les batteries ?", "open_alerts", {"part": "batteries"}),
    ("fr", "le fournisseur est en retard ?", "late_deliveries", {}),
    ("fr", "prévision pour les démarreurs à Marrakech", "forecast_of_part", {"part": "démarreurs", "branch": MARRAKECH}),
    ("fr", "les ventes de freinage de l'année", "sales_of", {"category": "Brakes", "period": "this_year"}),
    ("fr", "on vend plus ou moins que la semaine passée ?", "sales_vs_last", {"period": "this_week"}),
    ("fr", "combien de rotules on a vendu hier", "sales_of", {"part": "rotules", "period": "yesterday"}),
    ("fr", "ajoute 5 batteries au stock", "cannot_answer", {}),
    ("fr", "quel est le numéro du fournisseur Valeo", "cannot_answer", {}),
    # Arabic
    ("ar", "كم تبقى من أقراص الفرامل في الدار البيضاء؟", "stock_of_part", {"part": "أقراص الفرامل", "branch": CASA}),
    ("ar", "ما هي مبيعات قسم الإضاءة هذا الشهر", "sales_of", {"category": "Lighting", "period": "this_month"}),
    ("ar", "أي قطعة بيعت أكثر الأسبوع الماضي", "best_sellers", {"period": "last_week"}),
    ("ar", "هل هناك قطع على وشك النفاد في مراكش", "running_out", {"branch": MARRAKECH}),
    ("ar", "كم ستكلفنا الطلبية القادمة", "what_to_order", {}),
    ("ar", "ما الذي يجب طلبه من الفلاتر", "what_to_order", {"category": "Filters"}),
    ("ar", "القطع التي لم تبع منذ مدة طويلة", "dead_stock", {}),
    ("ar", "هل توجد تنبيهات حول البطاريات", "open_alerts", {"part": "البطاريات"}),
    ("ar", "هل هناك طلبيات متأخرة من الموردين", "late_deliveries", {}),
    ("ar", "كم نتوقع أن نبيع من المضخات", "forecast_of_part", {"part": "المضخات"}),
    ("ar", "مبيعات أمس", "sales_of", {"period": "yesterday"}),
    ("ar", "هل ارتفعت المبيعات مقارنة بالشهر الماضي", "sales_vs_last", {"period": "this_month"}),
    ("ar", "ما هو رقم هاتف المورد", "cannot_answer", {}),
    # Darija
    ("darija", "ch7al bqa mn disque frein f casa", "stock_of_part", {"part": "disque frein", "branch": CASA}),
    ("darija", "شحال بقا من الراديا", "stock_of_part", {"part": "الراديا"}),
    ("darija", "ach li tba3 ktar had chhar", "best_sellers", {"period": "this_month"}),
    ("darija", "chhal bi3na lyoum", "sales_of", {"period": "today"}),
    ("darija", "شحال بعنا ديال التبريد هاد العام", "sales_of", {"category": "Cooling", "period": "this_year"}),
    ("darija", "chno li 9rib ykmel f rabat", "running_out", {"branch": RABAT}),
    ("darija", "ach khassna njibo mn l fournisseur", "what_to_order", {}),
    ("darija", "شحال غادي تجي الكوموند ديال الفرامل", "what_to_order", {"category": "Brakes"}),
    ("darija", "sel3a li bayta f stock", "dead_stock", {}),
    ("darija", "kayn chi mochkil f l stock d marrakech", "open_alerts", {"branch": MARRAKECH}),
    ("darija", "l commande dyal valeo mazal ma wslat?", "late_deliveries", {}),
    ("darija", "ch7al ghadi nbi3o mn l batri f chhar jay", "forecast_of_part", {"part": "batri"}),
    ("darija", "l bi3 dyal had simana kter wla 9al mn li fatet", "sales_vs_last", {"period": "this_week"}),
    ("darija", "شحال بعنا من الأمورتيسور البارح", "sales_of", {"part": "الأمورتيسور", "period": "yesterday"}),
    ("darija", "3tini r9m dyal l client", "cannot_answer", {}),
]
