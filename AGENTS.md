# AGENTS.md — Instructions Globales du Projet

## Objectif

Production d'un **bootcamp complet** en exploitation de vulnérabilités applicatives.
Niveau : livre de référence. Public cible : débutants à intermédiaires en cybersécurité.

## Architecture Agentique

```
Orchestrateur (primary)
    ├── course-writer  → Rédaction pédagogique
    ├── code-tester    → Validation technique
    └── proofreader    → Relecture finale
```

## Règles du projet

### Langue
- Français académique soigné avec accents corrects
- Tutoiement pédagogique
- Vocabulaire technique précis

### Structure du cours
1. Introduction et contexte
2. Fondamentaux (réseau, web, Linux)
3. Attaques par catégorie (injection, auth, crypto, etc.)
4. Études de cas réels
5. TP pratiques en lab
6. Défense et remédiation

### Environnement
- **Lab** : Docker / Ubuntu 22.04+
- **Hébergement** : Windows
- **Outils** : nmap, sqlmap, Burp Suite, Metasploit, hydra, john, hashcat

### Versionnement
- Auteur : `yugmerabtene`
- Messages de commit : clairs, première personne, sans mentions de bot
- Commit après chaque tâche terminée

### Sécurité
- Avertissement légal dans chaque module d'exploitation
- Jamais de vrais payloads hors lab
- Jamais de secrets dans le dépôt

## Fichiers du projet

| Fichier | Description |
|---------|-------------|
| `opencode.json` | Configuration principale |
| `.opencode/agent/orchestrator.md` | Agent orchestrateur |
| `.opencode/agent/course-writer.md` | Sous-agent rédaction |
| `.opencode/agent/code-tester.md` | Sous-agent validation |
| `.opencode/agent/proofreader.md` | Sous-agent relecture |
| `.opencode/CONTEXT.md` | Contexte projet |
| `.opencode/tracking.json` | Progression |
