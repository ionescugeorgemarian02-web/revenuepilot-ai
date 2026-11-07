# PASUL 10 — identitate, sesiuni și autentificare (dezvoltare locală)

Autor: Claude Sonnet 5.5 (selectat de utilizator; planul recomandă Sol/Sonnet Medium, clasă M). Data: 2026-11-07. Bază: `4f75fee` (`main`, pașii 07–09 DONE). Branch `step-10/auth`.

## Ce este implementat (și testat local)

`src/revenuepilot/auth.py` + rute în `src/revenuepilot/app.py`, fără dependențe externe (stdlib, scrypt).

| Control | Implementare | Amenințare (docs/security) |
|---|---|---|
| Parole | scrypt N=2^14, sare unică, comparație constant-time, hash cu parametri validați (refuză N prea mare); lungime 12–256 | T01 |
| Sesiuni | token aleator 256 biți, doar SHA-256 al tokenului în store; expirare inactivitate 30 min și absolută 8 h; max 5 sesiuni/utilizator | T01 |
| Cookie | `HttpOnly; SameSite=Strict; Secure; Path=/`, prefix `__Host-`, fără Domain | T01 |
| Reautorizare | la fiecare cerere: sesiune, utilizator activ, `auth_version`; rolul și tenantul vin din server, nu din client | Contract acces: „tenantul efectiv provine din sesiune” |
| Identitate greșită | `/api/tenants/{id}/whoami`: alt tenant (existent sau nu) → 403 identic, fără enumerare | T01 |
| Brute force | 5 eșecuri/60 s per (client, utilizator) → 429 + `Retry-After`; parola corectă nu ocolește blocarea; utilizator necunoscut = același cost și același răspuns ca parolă greșită | T01 |
| CSRF / rebinding | POST cere `Origin` egal cu `Host`, `Content-Type: application/json`, `Host` din allowlist (127.0.0.1/localhost cu portul serverului); corp max 4 KB | T01, B1 |
| Acțiune sensibilă | schimbare parolă cere parola curentă, invalidează toate sesiunile, emite una nouă | T01 (reautentificare) |
| Fără secrete în repo | nicio parolă în cod; utilizatorul dev există doar dacă `REVENUEPILOT_DEV_PASSWORD` e setat la rulare; test care scanează `src/` după literali | G (securitate) |

**Marcaj explicit:** orice răspuns de identitate conține `"auth_mode": "dev-local-only"`; la pornire serverul scrie pe stderr dacă utilizatorul dev e activ.

## Comenzi (din rădăcină)

```sh
python3 -B -I -m unittest discover -s tests -v          # 17 teste
python3 -B -I scripts/build_skeleton.py
# rulare locală cu utilizator dev sintetic (parola o alegi tu, nu intră în Git):
REVENUEPILOT_DEV_PASSWORD='<parola ta, min. 12 caractere>' PYTHONPATH=src python3 -B -m revenuepilot
```

## Dovezi rulate efectiv

- 17 teste PASS pe Python 3.12.3 și 3.13.18 (8,8 s): acces neautorizat, cookie forjat/trunchiat/gol, logout, expirare idle și absolută, utilizator dezactivat, identitate din sesiune vs client, tenant inexistent, lockout și recuperare, CSRF/Host/Content-Type/JSON/dimensiune, schimbare parolă, hash-uri malformate, absența textului clar în store, plafon de sesiuni, scanare secrete.
- Rulare manuală pe procesul real (`python -m revenuepilot`): fără sesiune 401; parolă greșită 401 generic; login 200 cu cookie HttpOnly; `/api/me` 200. Build zipapp PASS; hash-uri canonice și linkuri PASS.
- Testele existente de smoke (08/09) trec neschimbate.

## Limite (NU sunt implementate sau NU sunt dovedite)

- Nu există OAuth/OIDC, MFA, înregistrare de utilizatori, resetare parolă, persistență (la repornire dispar utilizatorii și sesiunile) sau UI de login. Utilizatorul dev este unic și sintetic.
- Fără DB, deci nu există izolare tenant a datelor; doar identitatea tenantului din sesiune și un endpoint de probă. Izolarea reală este pasul 11/12.
- Cookie `Secure` pe `http://127.0.0.1`: Chrome/Firefox îl acceptă pe loopback; Safari iOS poate refuza. `REVENUEPILOT_INSECURE_COOKIE=1` (doar local) renunță la `Secure`. Neverificat pe browser real.
- Blocarea e per (client, utilizator) în memorie: pe loopback toți clienții au aceeași adresă; un atacator poate bloca temporar un utilizator (DoS de cont) — compromis acceptat la dev, de reconsiderat înainte de expunere publică.
- Furtul unei sesiuni valide până la revocare rămâne riscul rezidual T01 din registru.
- CI remote: NOT_RUN (Actions dezactivat la nivel de cont; vezi PROGRESS). Review independent: necerut pentru clasa M, nepretins. Producție: nu.
- Cost: zero. Memorie/învățare produs: neimplementate.

## Note pentru reviewer
Atacă: `_json_body` (ordinea verificărilor), `authenticate` (TOCTOU între verificare și `last_seen` — sub același lock), `login` (verificarea parolei în afara lock-ului e intenționată pentru a nu bloca alte cereri), cursa `change_password` între citirea hash-ului și scriere.

Lecție candidată: testele de securitate cu ceas injectat (`clock`) fac expirarea verificabilă fără `sleep`. Nu se promovează ca regulă fără evaluare.
