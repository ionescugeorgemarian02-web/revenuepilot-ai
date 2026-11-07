# PASUL 08 — stack și schelet minim

Autor: Codex, 2026-11-07; model/efort runtime neverificate. Bază `d4fcb1a` (pasul 07), branch `step-08/minimal-skeleton`. Recomandarea canonică GPT-6.1 Sol / Medium; alternativ Claude Sonnet 5.5 / Medium.

Alegere: Python 3.12.14 fixat în `.python-version`, compatibilitatea declarată `>=3.12,<3.14` în `pyproject.toml`, zero dependințe externe în `requirements.lock`. Build zipapp cu biblioteca standard. Rularea locală ascultă exclusiv `127.0.0.1`; endpoint `/health` răspunde JSON, alte rute 404. Aceasta este doar fundația tehnică, fără autentificare, tenanturi, DB, agent, costuri sau expunere publică. Nu este pregătită de producție.

Comenzi din rădăcină:

```sh
python3 -B -I scripts/build_skeleton.py
python3 -B -I -m unittest discover -s tests -v
PYTHONPATH=src python3 -B -m revenuepilot
# pentru artefact: python3 -B dist/revenuepilot.pyz
```

Buildul folosește stdlib; nu instalează pachete sau sudo. `dist/` este ignorat în Git, iar sursa rămâne reproductibilă. Cu `python3.13` disponibil local, buildul și testul au trecut și pe 3.13; mediul separat Claude rămâne NOT_RUN. Pe telefon, GitHub poate afișa sursele și probele; hostingul viitor rămâne necunoscut. Dacă hostul cere alt runtime, interfața HTTP și testul smoke pot fi păstrate, iar shell-ul înlocuit cu un server adecvat; alegerea se face după măsurarea hostului, fără promisiuni de compatibilitate neverificate.

Față de baseline 06: apare un build/test produs real local, fără KPI comercial, date clienți ori reducere de risc măsurată. Cost comercial activat zero. Memoria și învățarea produsului nu sunt implementate; jurnalul Git rămâne singura memorie persistentă de dezvoltare. Riscuri: HTTP stdlib nu este stack de producție, CI este indisponibil la nivel de cont, dependența 07 are CI blocat. PASUL 08 îndeplinește criteriul canonic prin build/test local real și dependența 07 este închisă; nu se începe 09.

## Integrare

PR #11 a fost integrat în `main` prin merge commit `eec60126bd61c617f1fe9c41962b301f8d43ad16`. Build/test locale au trecut pe Python 3.12 și 3.13; CI remote rămâne NOT_RUN (Actions dezactivat pentru cont). Pasul 08: DONE. STOP înainte de 09.
