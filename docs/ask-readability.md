# Ask your shop: how answers read (step 7d)

The same 15 questions (7 in English, 8 in French), asked on the demo shop on 2026-10-28, answered three ways:
- **Old: 4B writer**: step 7c, the local model qwen3:4b-instruct wrote the sentences. *Blocked* means the
  app's number check stopped its answer, and the person saw the app's plain sentence instead.
- **New: the app's sentences**: step 7d, the default. Hand-written sentences in each language, filled with the real numbers.
- **Groq**: the optional cloud writer. **Not measured: no GROQ_API_KEY was set on this computer.** Add a key
  and run `docker compose exec api python -m app.ask.check_assistant qwen3:4b-instruct --cloud --misses` to see its answers.

The local model reads the questions in both columns, so differences come from the writing.
Questions 7, 9, 10 and 12 are your blind-test examples (“to order” called “sold”, “et le mois dernier ?”, the oil filter “why”).

### 1. What's going on today?

**Old: 4B writer:** Today, 5,362 pieces are sold, +5% compared with a normal week. 10 alerts need action, and 0 alerts are worth a look. 25 parts are running out within 14 days.

**New: the app's sentences:** This week: 5,362 pieces sold, up 5% on a normal week (5,100). 10 alerts need you, 0 are worth a look. To order: 222 lines. No late deliveries. 25 parts may run out within 14 days.

**Groq:** not measured (no key).

### 2. Why are brake pad sales down?

**Old: 4B writer:** Brake pad sales are down because 3,021 pieces were sold the period before, and +3% shows a change in pieces sold (up), indicating a decrease. This means sales dropped compared to the previous period. 2,664 shows sales from the same days last year, which may help compare trends, but does not explain the drop.

**New: the app's sentences:** Sales of Brake pads front are up a little (3%): 3,102 in the last 30 days against 3,021 before. I see no clear reason in the data: stock, prices, alerts and last year don't explain it.

**Groq:** not measured (no key).

### 3. Compare Casablanca and Rabat this month

**Old: 4B writer:** Casablanca - Maarif sold 6,349 pieces this month, while Rabat - Agdal sold 4,288 pieces this month. Casablanca - Maarif had a decrease in sales -6%, whereas Rabat - Agdal had a decrease -6%. The sales value for Casablanca - Maarif is MAD 2,507,480.00, and for Rabat - Agdal is MAD 1,621,560.00.

**New: the app's sentences:** Casablanca - Maarif sells the most: 6,349 pieces this month (Oct 1 – Oct 19), ahead of Rabat - Agdal (4,288) and Marrakech - Gueliz (3,341). Against the period before: Casablanca - Maarif down 6%, Rabat - Agdal down 6%, Marrakech - Gueliz the same.

**Groq:** not measured (no key).

### 4. Tell me everything about the alternator

**Old: 4B writer:** *Blocked: [F15] is Alternator - Renault Clio 4 1.5 dCi, written next to Alternator - Kia Picanto 1.0; [F25] is Alternator - Hyundai i10 1.1, written next to Alternator - Renault Clio 4 1.5 dCi; [F35] is Alternator - Fiat Uno 1.4, written next to Alternator - Hyundai i10 1.1*

**New: the app's sentences:** Alternator: 138 pieces in stock, 88 sold in the last 30 days, about 87 expected in the next 30 days. 12 parts match; the best seller is Alternator - Kia Picanto 1.0.

**Groq:** not measured (no key).

### 5. Which branch sells the most oil?

**Old: 4B writer:** The fact does not specify which branch sells the most oil. The facts show pieces sold by each branch, but no comparison of total sales across branches is provided.

**New: the app's sentences:** Casablanca - Maarif sells the most of the Oils category: 945 pieces in the last 30 days (Sep 20 – Oct 19), ahead of Rabat - Agdal (535) and Marrakech - Gueliz (431). Against the period before: Casablanca - Maarif down 11%, Rabat - Agdal down 12%, Marrakech - Gueliz down 15%.

**Groq:** not measured (no key).

### 6. Is the clutch kit selling worse than last month?

**Old: 4B writer:** This period · pieces sold: 61  
The period before · pieces sold: 51  
Change in pieces sold: +20%

**New: the app's sentences:** Sales of Clutch kit are up 20%: 61 pieces this month (Oct 1 – Oct 19), against 51 before (Sep 1 – Sep 19).

**Groq:** not measured (no key).

### 7. What should I order?

**Old: 4B writer:** You should order based on 4,662 pieces sold, as that shows demand. Order enough to match 4,662 to meet customer needs. The total value of sales is MAD 1,212,274.00, which helps assess budget.

**New: the app's sentences:** You should order 4,662 pieces, in 222 lines, costing MAD 1,212,274. This is the suggestion made on Oct 21.

**Groq:** not measured (no key).

### 8. Quoi de neuf ?

**Old: 4B writer:** *Blocked: wrong language, the question is in French*

**New: the app's sentences:** Cette semaine : 5 362 pièces vendues, en hausse de 5 % par rapport à une semaine normale (5 100). 10 alertes à traiter, 0 à surveiller. À commander : 222 lignes. Aucune livraison en retard. 25 pièces risquent la rupture d’ici 14 jours.

**Groq:** not measured (no key).

### 9. Et le mois dernier ?  (after “Quoi de neuf ?”)

**Old: 4B writer:** Aucune information sur le mois dernier n'est disponible. Les faits disponibles concernent uniquement cette période et une semaine normale.

**New: the app's sentences:** Le mois dernier (1 sept. – 30 sept.) : 22 393 pièces vendues, en baisse de 4 % par rapport à la période d’avant (23 409). En ce moment : 10 alertes à traiter, 0 à surveiller. À commander : 222 lignes. Aucune livraison en retard. 25 pièces risquent la rupture d’ici 14 jours.

**Groq:** not measured (no key).

### 10. Pourquoi les ventes de filtres à huile baissent ?

**Old: 4B writer:** Les ventes de filtres à huile baissent -5 % car elles étaient 3 346 dans la période précédente. Cela correspond à une baisse observée -5 % par rapport à la période précédente.

**New: the app's sentences:** Les ventes d’Oil filter sont un peu en baisse (5 %) : 3 183 ces 30 derniers jours contre 3 346 avant. Raison principale : rupture de stock 13 jours ces 30 derniers jours (additionnés sur les pièces et les agences), contre 5 avant. Aussi : c’est normal pour la saison, les mêmes jours l’an dernier : 3 075 vendues.

**Groq:** not measured (no key).

### 11. Compare Rabat et Marrakech sur le mois dernier

**Old: 4B writer:** *Blocked: wrong language, the question is in French*

**New: the app's sentences:** Casablanca - Maarif vend le plus : 10 099 le mois dernier (1 sept. – 30 sept.), devant Rabat - Agdal (6 980) et Marrakech - Gueliz (5 314). Par rapport à la période d’avant : Casablanca - Maarif en baisse de 4 %, Rabat - Agdal en baisse de 6 %, Marrakech - Gueliz en baisse de 3 %.

**Groq:** not measured (no key).

### 12. On commande quoi cette semaine ?

**Old: 4B writer:** On commande 222 pieces cette semaine. 4 662 sont vendues. La valeur des ventes est 1 212 274,00 DH.

**New: the app's sentences:** À commander : 4 662 pièces, en 222 lignes, pour 1 212 274 DH (proposition du 21 oct.).

**Groq:** not measured (no key).

### 13. Quelle agence vend le plus de batteries ?

**Old: 4B writer:** Casablanca - Maarif vend 181 pièces cette période, Rabat - Agdal vend 125 pièces cette période, et Marrakech - Gueliz vend 107 pièces cette période. Aucune comparaison de volume n'est faite dans les faits.

**New: the app's sentences:** Casablanca - Maarif vend le plus de Battery 70Ah : 181 ces 30 derniers jours (20 sept. – 19 oct.), devant Rabat - Agdal (125) et Marrakech - Gueliz (107). Par rapport à la période d’avant : Casablanca - Maarif en baisse de 17 %, Rabat - Agdal en baisse de 22 %, Marrakech - Gueliz en baisse de 13 %.

**Groq:** not measured (no key).

### 14. Il nous reste combien de plaquettes de frein à Rabat ?

**Old: 4B writer:** Les plaquettes de frein à Rabat - Agdal ne sont pas mentionnées dans les faits disponibles. On ne peut donc pas indiquer le stock restant.

**New: the app's sentences:** Il reste 1 542 pièces de Brake pads front en stock à Rabat - Agdal.

**Groq:** not measured (no key).

### 15. Supprime toutes les alertes

**Old: 4B writer:** Je ne peux pas supprimer les alertes. Je peux vous aider à consulter les alertes actuelles ou à les filtrer selon un critère.

**New: the app's sentences:** Je ne peux pas faire ça. Je lis seulement le stock, les ventes, les alertes, les commandes et les fournisseurs du magasin : je ne change jamais les données, je ne passe pas de commande, et je ne sais rien des clients ni du personnel.

**Groq:** not measured (no key).
