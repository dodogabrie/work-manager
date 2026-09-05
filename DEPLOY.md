# Deploy

Work Planner gira in Docker Compose dietro un reverse proxy che termina TLS.
Il frontend è servito da nginx e fa già da proxy verso il backend, quindi
l'unica porta da esporre è quella del frontend.

## 1. Preparare l'ambiente

```bash
cp .env.example .env
```

La password owner **non sta in `.env`**: un hash argon2 è pieno di `$`
(`$argon2id$v=19$m=...`) e Docker Compose li interpola come variabili,
consegnando al container un hash mutilato e un login che fallisce senza dire
perché. Vive quindi in `secrets/owner_password_hash`, scritto dal comando:

```bash
mkdir -p secrets
docker compose run --rm backend python -m app.cli hash-password
```

Il segreto di sessione invece va in `.env` (non contiene `$`):

```bash
docker compose run --rm backend python -m app.cli secret          # -> SESSION_SECRET
```

Poi imposta:

```ini
PUBLIC_BASE_URL=https://planner.edoardogabrielli.com
CORS_ORIGINS=https://planner.edoardogabrielli.com
POSTGRES_PASSWORD=<una password robusta>
HTTP_PORT=8080
TZ=Europe/Rome
```

`PUBLIC_BASE_URL` **deve** essere in `https`: da lì il backend deduce che il
cookie di sessione va marcato `Secure`.

## 2. Avviare

```bash
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
```

Le migrazioni Alembic girano da sole all'avvio del backend.

## 3. Reverse proxy e TLS

Il servizio ascolta su `127.0.0.1:8080`, non su Internet. Davanti serve un
proxy che termini TLS. Con Caddy bastano due righe:

```
planner.edoardogabrielli.com {
    reverse_proxy 127.0.0.1:8080
}
```

Caddy ottiene e rinnova il certificato da solo. Con nginx serve invece
`certbot` e un blocco `server` con `proxy_pass http://127.0.0.1:8080`, più gli
header `X-Forwarded-Proto` e `X-Forwarded-For`.

## 4. Verifica

```bash
curl -fsS https://planner.edoardogabrielli.com/health
```

Poi apri il sito, entra con la password owner, crea un task e controlla che il
piano si materializzi.

**Prova anche il link manager da un browser senza sessione** (o in incognito):
è l'unico modo di accorgersi se la Manager View sta esponendo qualcosa che non
dovrebbe.

## 5. Backup

`backup.sh` fa un dump compresso in `backups/` e trattiene 30 giorni.

```bash
crontab -e
0 3 * * * /percorso/work-planner/backup.sh
```

Il ripristino:

```bash
gunzip -c backups/workplanner-<stamp>.sql.gz | \
  docker compose exec -T db psql -U workplanner workplanner
```

Un backup mai ripristinato non è un backup: provane uno subito dopo il primo
deploy, su un database di prova.

## 6. Aggiornamenti

```bash
git pull
docker compose -f compose.yaml -f compose.prod.yaml up -d --build
```

Il backend applica le migrazioni all'avvio. Fai un backup **prima** di un
aggiornamento che tocca lo schema.

## 7. Log e stato

```bash
docker compose logs -f backend
docker compose ps
```

Il backend espone `/health`; entrambi i container hanno un healthcheck, quindi
`docker compose ps` dice se qualcosa è degradato.

## Note di sicurezza

- Il database non espone porte in produzione (`ports: []`).
- `.env` e `secrets/` non sono nel repository e non devono finirci.
- `secrets/owner_password_hash` è montato in sola lettura in produzione e ha
  permessi `600`.
- I token API, i link manager e i feed ICS sono salvati **hashati**: se ne
  perdi uno va revocato e ricreato, non recuperato.
- Il rate limit sul login è in memoria e per processo: con più worker uvicorn
  il limite effettivo si moltiplica. Con un solo worker — la configurazione
  prevista per un'app personale — è quello dichiarato.
