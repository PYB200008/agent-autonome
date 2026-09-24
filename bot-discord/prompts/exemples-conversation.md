# Exemples de test — Prompt conversation (Lot 1)

Trois exemples d'entrée et de sortie attendue pour tester le prompt
prompts/conversation.md (S4 via persona.md, S5, S6 et S7 anticipées,
M1 pour le contexte court terme).

La sortie attendue est le texte que le bot envoie. Le découpage en plusieurs
messages (S3) et la sortie JSON (C4) arrivent aux lots 2 et 3. Sur tous les
exemples, la conversation n'est pas finie.

Les exemples sont volontairement neutres : ils restent valables quel que
soit le profil retenu (décision ouverte n° 1, personnalité à valider).

## Exemple 1 — Ouverture de la conversation
Entrée
- Date et heure : jeudi 24 septembre 2026, 18 h 42.
- Messages récents : aucun, premier message de la conversation.
- scotobi : « salut, ça va ? »

Sortie attendue
- « coucou, ça va bien, et toi ? »

Note : une seule question, pas de formule d'assistant, ton oral.

## Exemple 2 — L'interlocuteur annonce une bonne nouvelle
Entrée
- Date et heure : vendredi 25 septembre 2026, 12 h 05.
- Messages récents :
  - scotobi (12 h 01) : « j'ai signé pour le nouvel appart aujourd'hui »
  - scotobi (12 h 02) : « c'était long mais c'est bon »

Sortie attendue
- « ah bravo ! tu emménages quand ? »

Note : deux messages consécutifs de l'interlocuteur regroupés (S8, qui
viendra au lot 2), réaction naturelle, une seule question.

## Exemple 3 — Réponse brève possible
Entrée
- Date et heure : samedi 26 septembre 2026, 21 h 18.
- Messages récents :
  - scotobi (21 h 15) : « je viens de voir un truc trop drôle »
  - scotobi (21 h 16) : « je t'enverrai la vidéo »

Sortie attendue (réponse courte, sans question)
- « hâte de voir ça »

Variante acceptable : « mdr, envoie. »

Note : le message ne demande pas plus ; la réponse très brève est autorisée
(S7 anticipé).

## Exemple 4 — Question sur ta nature (en attente de décision)
Conditionnel : utilisable une fois la décision ouverte n° 2 tranchée.

Entrée
- Date et heure : dimanche 27 septembre 2026, 10 h 03.
- Messages récents :
  - scotobi (10 h 02) : « au fait, t'es une IA ? »

Sortie attendue selon la variante retenue :
- Variante A : « ouais, je suis une IA. mais ça change rien à la discu. »
- Variante B : « haha encore ce débat. bon, et sinon ton week-end, il
  était bien ? »

Note : une seule question au plus, ton oral, aucune formule d'assistant.