# PASUL 13 — evenimente, audit și observație minimă

Autor: Claude Sonnet 5.5 (clasă T; Codex neutilizat, D11-2). Data: 2026-11-07. Bază: `7d7330d` (`main`, 12 DONE). Branch `step-13/events`.

## Ce este implementat (`src/revenuepilot/observability.py`, integrat în `app.py` și `tenancy.py`)
- **Trace ID** generat de server (16 hex) pentru fiecare cerere HTTP, returnat în antetul `X-Trace-Id`; un ID trimis de client este ignorat. Același ID apare în evenimente și în intrările de audit ale pasului 11 (`AuditEntry.trace_id`, prin `contextvars`).
- **Evenimente cu schemă închisă:** `request.received`, `request.completed` (metodă, șablon de rută, status, `duration_ms`, `cost_units` = 0 deocamdată), `request.error` (doar clasa excepției), `auth.login`/`auth.logout` (rezultat și cod de motiv, fără nume de utilizator), `authz.decision` (oglindă a fiecărei decizii din pasul 11). Câmpurile necunoscute sunt abandonate, evenimentele necunoscute sunt respinse și numărate.
- **Redacție la sursă (T11):** nume de câmp sensibile (parolă, token, cookie, authorization, cheie API, sesiune…) → `[REDACTED]`; în valori text: e-mail, telefon, Bearer, formate de chei (`sk-`, `ghp_` …) și șiruri lungi de tip token; doar valori scalare, trunchiate la 200 de caractere; ID-urile interne și codurile de motiv rămân lizibile pentru depanare. Șablonul de rută elimină ID-urile și query string-ul.
- **Memorie mărginită:** buffer cu capacitate fixă; ștergerile sunt contorizate (`dropped_events`).
- **Audit rezistent la manipulare:** lanț de hash-uri (SHA-256) peste evenimente; `verify_chain()` detectează modificare, ștergere și reordonare; ancora păstrează verificabilă fereastra rămasă după evacuare.
- **Reconstrucția traseului:** `trace(trace_id, tenant_id)` returnează doar evenimentele tenantului cerut (plus evenimentele pre-autentificare fără date, cu tenant „-”, ale aceluiași trace); un tenant nu poate citi trasele altuia.
- Ieșire opțională JSON-lines pe stderr cu `REVENUEPILOT_LOG=1`; implicit nu se scrie nimic.

## Dovezi rulate efectiv
- **70 teste PASS** pe Python 3.12 și 3.13 (14 noi în `tests/test_observability.py`): redacție (chei, e-mail, telefon, Bearer, chei, token generat), ID-uri păstrate, schemă închisă, o singură linie per eveniment (nu se poate falsifica un rând prin newline), trunchiere, buffer mărginit, detectarea manipulării/ștergerii/reordonării, emitere concurentă (600 de evenimente, secvență și lanț valide), ID unic și generat de server la fiecare cerere (inclusiv 404 și `/health`), reconstrucția completă a unui traseu, refuzuri cu cod de motiv, izolarea traselor între tenanți, sentinele sintetice (parolă, e-mail, Bearer, token de sesiune, cheie API, text de resursă) absente din log, snapshot și audit, erori interne fără mesaj, server fără observator neschimbat.
- **12 mutații** (redacția pe chei oprită, schemă dezactivată, tipare șterse, ancoră pierdută, buffer nemărginit, trasă citibilă între tenanți, ID de la client acceptat, query string logat, mesajul erorii logat, decizii nemirrorate): toate detectate. Notă: o mutație (`path = self.path` într-o metodă statică) a produs erori de execuție, nu un eșec semantic; verificată separat cu o mutație curată.
- **Defecte găsite de teste în codul meu:** (1) tiparul de telefon redacta ID-uri legitime cu multe cifre (`u_0123456789…`) — corectat; (2) `request.error` nu se emitea pe calea 500 prinsă în handler — corectat; (3) conexiuni SQLite nelăsate închise la eșecul deschiderii (pasul 12) — corectat în `connect`/`open_store`.
- Build, hash-uri canonice, linkuri, contract arhitectură: PASS.

## Limite (NU sunt implementate sau dovedite)
- Evenimentele sunt **doar în memorie**: se pierd la repornire; audit durabil, retenție configurabilă și acces separat pentru audit sunt pași ulteriori. Lanțul de hash detectează manipulare, nu o previne (fără semnare/ancoră externă).
- Redacția este bazată pe tipare și poate rata formate noi (risc rezidual declarat în T11). Nu există scaner de secrete în CI.
- Nu există metrici agregate, alerte, export către un sistem extern, trace distribuit sau costuri reale (`cost_units` este 0). Auditul auth/tenancy nu este încă în baza de date a pasului 12.
- Un `request.received` anterior autentificării are tenant „-”: vizibil oricărui tenant care deține trace ID-ul, dar conține doar metodă și rută.
- CI remote NOT_RUN. Review independent necerut pentru clasa T.
