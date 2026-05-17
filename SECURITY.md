# 🔐 Politique de Sécurité - BRVM Analytics

## Vue d'ensemble

Ce document décrit les pratiques de sécurité pour BRVM Analytics, une plateforme d'analyse financière SaaS utilisant Supabase, GitHub Actions, et APIs externes.

---

## 1. Gestion des Secrets

### ❌ Ne JAMAIS commiter de secrets

**Secrets compromis:**
- Clés API (Supabase, Anthropic, Mistral, GitHub)
- Tokens JWT
- Credentials de base de données
- Tokens d'authentification

### ✅ Bonnes pratiques

#### 1.1 Fichier `.env` (local, jamais committé)
#### 1.2 Fichier `.env.example` (template public)
---

## 2. Incident: Clé compromise (Mai 17, 2026)

### 📋 Chronologie

- 2026-05-17 00:45:36 UTC: GitGuardian détecte leak de Service Role JWT
- 2026-05-16 21:00: Nouvelle clé JWT créée et activée
- 2026-05-16 22:06: Nouveau secret GitHub Actions configuré
- 2026-05-16 22:12: Pipeline testé avec succès ✅

### 🔍 Analyse

**Clé compromise:**
- ID JWT: 6B239561-FEEB-476D-B130-G8TAG89EF5A7
- Type: ECC (P-256)
- Scope: Service Role (accès complet DB)

**Clé actuelle (sécurisée):**
- ID JWT: CBBDFE49-8B99-4CE8-849F-302DB47510CC
- Type: ECC (P-256)

### ✅ Mesures correctives

1. ✅ Régénération immédiate de la clé
2. ✅ Rotation JWT Keys via Supabase
3. ✅ Mise à jour GitHub Actions
4. ✅ Tests du pipeline avec nouvelle clé
5. ✅ Ajout de .env.example au repo
6. ✅ Vérification .gitignore pour secrets

---

## 3. Rotation des Clés - Procédure

1. Créer une nouvelle clé (Standby Key)
   - Supabase → Settings → JWT Keys
   - Clique "Create Standby Key"

2. Activer la nouvelle clé
   - Supabase → Settings → JWT Keys
   - Clique "Rotate keys"

3. Mettre à jour GitHub Actions
   - GitHub → Settings → Secrets and variables → Actions
   - Édite SUPABASE_SERVICE_ROLE_KEY

4. Tester le pipeline
   - GitHub Actions → Run workflow

---

## 4. Checkliste de Sécurité

- [ ] .env est dans .gitignore
- [ ] .env.example existe et est committé
- [ ] Aucun secret hardcodé dans les fichiers
- [ ] GitHub Actions utilise secrets.*
- [ ] Secret scanning activé sur GitHub
- [ ] Clés API rotées trimestriellement

**Dernière mise à jour:** 2026-05-16 22:30 UTC
