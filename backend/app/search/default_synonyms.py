"""The synonym list every new shop starts with. Each shop can edit its own copy in Settings.

One group = words that mean the same part, in French, English, Arabic and Darija.
Searching any word of a group also searches the others. Keep a group to true equivalents:
"bougie" alone is not here because it can mean a spark plug or a glow plug.
"""

DEFAULT_SYNONYMS: list[list[str]] = [
    # Brakes
    ["plaquettes de frein", "plaquette de frein", "brake pads", "brake pad", "فحمات الفرامل", "فحمات", "بلاكيت"],
    ["frein", "freins", "brake", "brakes", "فرامل", "فران", "فرانات"],
    ["disque de frein", "brake disc", "brake rotor", "قرص الفرامل", "ديسك فران", "ديسك"],
    ["étrier", "étrier de frein", "caliper", "brake caliper", "ملقط الفرامل", "كاليبر"],
    ["liquide de frein", "brake fluid", "سائل الفرامل", "زيت الفرامل"],
    # Filters and oils
    ["filtre", "filter", "فلتر", "فيلتر", "مصفاة"],
    ["filtre à huile", "oil filter", "فلتر الزيت", "فيلتر ليويل"],
    ["filtre à air", "air filter", "فلتر الهواء", "فيلتر الهوا"],
    ["filtre habitacle", "cabin filter", "pollen filter", "فلتر المكيف", "فلتر المقصورة"],
    ["filtre à gasoil", "filtre à carburant", "fuel filter", "diesel filter", "فلتر الوقود", "فلتر المازوت"],
    ["huile moteur", "engine oil", "motor oil", "زيت المحرك", "زيت الموتور", "ليويل ديال الموتور"],
    ["huile", "oil", "زيت", "ليويل"],
    ["liquide de refroidissement", "antigel", "coolant", "antifreeze", "سائل التبريد", "ليكيد ديال الراديا"],
    # Ignition and electrical
    ["bougie d'allumage", "spark plug", "شمعة الإشعال", "بوجي", "بوجية"],
    ["bougie de préchauffage", "glow plug", "شمعة التسخين", "بوجي ديال التسخين"],
    ["bobine d'allumage", "ignition coil", "ملف الإشعال", "بوبين"],
    ["allumage", "ignition", "إشعال"],
    ["batterie", "battery", "بطارية", "باطري", "باتري"],
    ["alternateur", "alternator", "dynamo", "dinamo", "مولد كهربائي", "دينامو", "الطرناتور"],
    ["démarreur", "starter", "starter motor", "محرك التشغيل", "ديمارور", "مارش"],
    # Engine and cooling
    ["courroie de distribution", "kit de distribution", "timing belt", "سير التوقيت", "كوروا ديال الديستريبيسيون"],
    ["courroie d'accessoires", "accessory belt", "serpentine belt", "drive belt", "سير المولد"],
    ["courroie", "belt", "سير", "كوروا"],
    ["pompe à eau", "water pump", "مضخة الماء", "بومبا ديال الما"],
    ["pompe à essence", "pompe à carburant", "fuel pump", "مضخة الوقود", "مضخة البنزين"],
    ["pompe", "pump", "مضخة", "بومبا"],
    ["thermostat", "ترموستات", "منظم الحرارة"],
    ["radiateur", "radiator", "مبرد", "رادياتور", "راديا"],
    ["durite", "hose", "خرطوم", "دوريت"],
    ["joint", "gasket", "حشوة", "جوان"],
    ["échappement", "exhaust", "عادم", "الشكمان"],
    ["moteur", "engine", "motor", "محرك", "موتور"],
    # Suspension, steering, transmission
    ["amortisseur", "shock absorber", "shock", "ممتص الصدمات", "مساعد", "امورتيسور"],
    ["rotule de direction", "tie rod end", "رأس المقود", "روتيل"],
    ["biellette de barre stabilisatrice", "biellette stabilisatrice", "stabilizer link", "sway bar link", "ذراع التوازن"],
    ["roulement de roue", "roulement", "wheel bearing", "bearing", "رولمان ديال الروضة", "رولمان", "محمل العجلة"],
    ["embrayage", "clutch", "القابض", "كلاتش", "لامبرياج", "امبرياج"],
    ["kit", "set", "طقم"],
    # Other
    ["balai d'essuie-glace", "essuie-glace", "wiper blade", "wiper", "ماسحة الزجاج", "مساحات"],
    # Where on the car
    ["avant", "front", "أمامي", "امامية", "القدام"],
    ["arrière", "rear", "back", "خلفي", "خلفية", "اللور"],
    ["gauche", "left", "يسار", "ليسر"],
    ["droit", "droite", "right", "يمين", "ليمن"],
]
