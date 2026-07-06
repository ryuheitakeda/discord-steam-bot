# 今日なんのゲームする？Bot

A Discord bot that looks at the Steam games members of a voice channel own in common and suggests
"something to play together today". (Formerly working title: "Discord x Steam VC Bot".)

*(This is an English translation of `README.md`. The Japanese version is the source of truth; if the
two ever diverge, defer to `README.md`.)*

## Features

- `/link <steam>` — Link your own Steam profile URL (or SteamID64 / custom URL name)
- `/unlink` — Remove the link
- `/profile [user]` — Check link status
- `/games [all]` — Show up to the top 10 titles supporting multiplayer, taken from the common
  library of everyone currently in your voice channel (`all:True` disables the multiplayer filter)
- `/pick [all]` — Randomly pick one title from the list above
- `/premium` — Check the server's plan status (free / premium) and show the upgrade link

`/link` works by having each member paste their own Steam profile URL/ID. If you paste someone
else's URL, the account gets linked to *that* URL (not you) — the person who ran the command gets
no benefit from doing so (there's no incentive to impersonate). Rather than something like a
Discord OAuth2 account link, this is intentionally kept to a simple self-report.

### Freemium limits

`/games` and `/pick` are rate-limited per server on a rolling window (3/day and 60/month). Servers
subscribed to Premium (¥380/month via Stripe) get unlimited use. When the limit is hit, the bot
automatically shows an upgrade link (Stripe Payment Link).

Bot-owner-only admin commands `/grant` and `/revoke` are also available for manually granting or
revoking Premium.

### Localization (i18n)

Command responses automatically switch between Japanese and English based on each Discord user's
locale setting (`locales/ja.json` / `locales/en.json`, `i18n.py` / `translator.py`).

## Setup

### 1. Create a Discord Bot

1. Create a new application at the [Discord Developer Portal](https://discord.com/developers/applications)
2. Add a Bot under the "Bot" tab and grab the token
3. Enable **SERVER MEMBERS INTENT** under "Privileged Gateway Intents" (needed to resolve voice
   channel members; Message Content Intent is not required)
4. Under "OAuth2 → URL Generator", select the `bot` and `applications.commands` scopes, grant
   "Send Messages" and "Embed Links" permissions, and invite the bot to your server using the
   generated URL

### 2. Get a Steam Web API key

Get an API key from [https://steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey).

### 3. Preparation on the member side

Each member needs to set "Game details" to **Public** under Steam's Privacy Settings → Profile
(otherwise their game library can't be fetched).

### 4. Environment setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env and set DISCORD_TOKEN / STEAM_API_KEY
# Also set GUILD_ID while developing so slash commands sync instantly
```

### 5. Run

```bash
source .venv/bin/activate
python bot.py
```

Once the startup log shows the command sync result, you're ready to go.

## How to use it

1. Each member runs `/link <their own Steam profile URL>` (e.g. `https://steamcommunity.com/id/xxxx`)
2. Two or more linked members join the same voice channel
3. Run `/games` or `/pick`

## Notes

- The owned-games cache refreshes every hour; the multiplayer-detection cache refreshes every 30 days
- Multiplayer detection uses Steam Store's unofficial API (`appdetails`). To stay under its rate
  limit, new lookups are capped at 30 per command. Some titles may show up as "undetermined" on the
  first run, but this resolves itself as the cache fills in over subsequent runs

## Deployment (Raspberry Pi / systemd)

Production runs on a Raspberry Pi under systemd for the time being. The full set of templates lives
under `deploy/`.

1. On the Pi, place the full bot codebase (including `bot.db` and `.env`) in a directory of your
   choice (referred to below as `{{BOT_DIR}}`), then create a virtualenv and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Replace `{{BOT_DIR}}` in `deploy/discord-steam-bot.service` with the actual absolute path (e.g.
   `/home/ryu/discord-steam-bot`), then place it at `/etc/systemd/system/discord-steam-bot.service`
3. Enable and start it:

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now discord-steam-bot.service
   journalctl -u discord-steam-bot -f   # check logs; the startup log should show the command-sync result
   ```

**Note:** the Pi may already be running the bot under a different unit name or a different startup
mechanism. Don't just overwrite it — diff the existing unit against `deploy/discord-steam-bot.service` and
apply the difference. Since the bot uses a single token, make sure the old and new units are never
running at the same time (double-connecting the same token) — stop the old unit before starting the
new one.

To expose the Stripe webhook externally, follow `deploy/cloudflare-tunnel.md` to set up a Cloudflare
Tunnel.

## Backup (Litestream + R2) and restore procedure

`bot.db` (SQLite) is continuously replicated to Cloudflare R2 via [Litestream](https://litestream.io/).
The config template is `deploy/litestream.yml`, and the systemd unit to run it as a daemon is
`deploy/litestream.service`.

### Setup

1. [Install Litestream](https://litestream.io/install/) (ARM builds are available for Raspberry Pi)
2. Replace `{{BOT_DIR}}`, `{{R2_BUCKET}}`, `{{R2_ENDPOINT}}` in `deploy/litestream.yml` with real
   values, and place it at `{{BOT_DIR}}/deploy/litestream.yml`
   (leave `access-key-id` / `secret-access-key` as `${R2_ACCESS_KEY_ID}` / `${R2_SECRET_ACCESS_KEY}` —
   Litestream expands these from the environment)
3. Copy `deploy/litestream.env.example` to `{{BOT_DIR}}/deploy/litestream.env`, fill in the real
   `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` from the R2 API token, and `chmod 600` it (this file
   must never be committed to git)
4. Replace `{{BOT_DIR}}` in `deploy/litestream.service` and place it at
   `/etc/systemd/system/litestream.service`
5. Verify replication manually before turning it into a daemon:

   ```bash
   # Manual check (Ctrl+C to stop)
   litestream replicate -config {{BOT_DIR}}/deploy/litestream.yml

   # Once confirmed, run it as a daemon
   sudo systemctl daemon-reload
   sudo systemctl enable --now litestream.service
   ```

### Restore

Recovering `bot.db` after, say, Pi hardware failure or SD card corruption:

```bash
litestream restore -config {{BOT_DIR}}/deploy/litestream.yml -o {{BOT_DIR}}/bot.db {{BOT_DIR}}/bot.db
# Make sure discord-steam-bot.service is stopped first — restoring on top of a bot.db the service still has
# open will conflict with it.
```

### Restore drills (do this periodically)

To avoid a false sense of security ("we're backing up" when the backup is actually broken),
periodically restore into a separate directory and verify integrity there.

```bash
mkdir -p /tmp/discord-steam-bot-restore-drill
litestream restore -config {{BOT_DIR}}/deploy/litestream.yml -o /tmp/discord-steam-bot-restore-drill/bot.db {{BOT_DIR}}/bot.db

# SQLite integrity check
sqlite3 /tmp/discord-steam-bot-restore-drill/bot.db "PRAGMA integrity_check;"
# Should return "ok"

# Eyeball that the key tables have the expected records (see db.py for the schema/table names)
sqlite3 /tmp/discord-steam-bot-restore-drill/bot.db ".tables"

rm -rf /tmp/discord-steam-bot-restore-drill
```

## Monitoring

Liveness monitoring via healthchecks.io is set up (see `deploy/monitoring.md` for details).
`discord-steam-bot-heartbeat.timer` pings every 5 minutes while the process is alive, and
`discord-steam-bot-notify-failure.service` fires immediately via `OnFailure` if
`discord-steam-bot.service` crashes.

## Migrating to a different host

To move off the Raspberry Pi to a different host (e.g. a future VPS migration — candidates being
WebARENA Indigo, Sakura's VPS, etc.), the basic procedure is: `rsync` the whole bot directory (code +
`bot.db` + `.env`) over, install dependencies, and enable systemd. That's it.

```bash
# Stop the bot on the old host first (to keep bot.db consistent)
ssh old-host "sudo systemctl stop discord-steam-bot litestream"

# Transfer the code + bot.db + .env to the new host
rsync -avz --exclude '.venv' --exclude '__pycache__' \
  old-host:{{BOT_DIR}}/ new-host:{{BOT_DIR}}/

# On the new host
ssh new-host "cd {{BOT_DIR}} && python -m venv .venv && \
  .venv/bin/pip install -r requirements.txt"

# Re-install deploy/discord-steam-bot.service, litestream.service, (and cloudflared.service if applicable)
ssh new-host "sudo systemctl daemon-reload && \
  sudo systemctl enable --now litestream.service discord-steam-bot.service"

# Disable the units on the old host
ssh old-host "sudo systemctl disable --now discord-steam-bot litestream"
```

Instead of rsyncing `bot.db` directly, you can also restore it from Litestream on the new host
(if the bot is actively writing to `bot.db` during the rsync, there's a risk of inconsistency, so
this is the safer option once Litestream is in steady operation). After migrating, don't forget to
also move over the old host's Cloudflare Tunnel configuration, if applicable.
