> ※This is a template. Review the content yourself before publishing and consult a professional (e.g. a lawyer) if needed. This is not intended as definitive legal advice. The Japanese version (`privacy.md`) is the primary/authoritative document; this is a convenience translation. Re-verify against the actual implementation (`db.py`) before publishing, since accurate handling of Steam IDs may matter for Stripe's direct-sales review requirements.

# Privacy Policy

Last updated: 2026-07-06

RyuTekLabo ("we", "us", "the Operator") sets out this Privacy Policy ("Policy") describing how user information is handled by the Discord Bot "今日なんのゲームする？Bot" (the "Service").

## 1. Information We Collect

The Service collects and stores the following information, only as needed to provide its functionality (this reflects the actual database schema):

| Category | Specific items | Trigger / storage |
|---|---|---|
| Discord-related information | Internal Discord user ID (snowflake), internal Discord server (guild) ID | Retrieved from the Discord API when commands run; stored in the `users`, `usage_log`, and `entitlements` tables |
| Steam account information | SteamID64 resolved from the profile URL/custom URL name you supply, Steam display name (persona name), link timestamp | Collected when running `/link`; stored in the `users` table |
| Steam owned-games information | Owned games' app IDs, titles, total playtime, and playtime in the last 2 weeks | Fetched from the Steam Web API and cached when running `/games`/`/pick`; stored in the `owned_games` table (keyed by Steam ID), expires after 1 hour (may persist in storage until the next fetch) |
| Game metadata | App IDs, titles, and multiplayer classification from the Steam Store | Cached from Steam Store data; stored in the `app_categories` table (not tied to any individual user), expires after 30 days |
| Usage logs | Server ID, Discord user ID, command name, timestamp | Recorded each time `/games`/`/pick` runs, to track free-tier consumption; stored in the `usage_log` table |
| Entitlement information | Subject (typically the server), plan type, source (manual or Stripe), expiration | Stored to determine premium status; stored in the `entitlements` table |
| Stripe billing-related information | Stripe subscription ID, corresponding Discord server ID, Stripe customer ID, subscription status | Stored upon receiving Stripe webhooks; stored in the `stripe_subscriptions` table. **Actual payment details — card number, name, billing address, email, etc. — are not stored on the Service's servers; they are collected and held by Stripe, our payment processor** |

The Service uses Discord's "Server Members" privileged gateway intent to fetch the list of voice-channel members when a command runs. This is processed on the fly each time `/games`/`/pick` is invoked and the member list itself is not stored in the database (only each member's link status is looked up from the `users` table).

## 2. Purpose of Use

Collected information is used solely for the following purposes:

1. Linking Steam accounts and displaying link status (`/link`, `/unlink`, `/profile`)
2. Computing commonly-owned games among VC members and suggesting multiplayer titles (`/games`, `/pick`)
3. Tracking free-tier consumption (3/day and 60/month, per server) and distinguishing premium status (`/premium`)
4. Managing Premium subscription state via Stripe webhooks
5. Preventing abuse, handling incidents, and improving the Service

## 3. Third-Party Disclosure and Subprocessors

1. The Service sends information, as needed, to the following external services. Handling of information by each is governed by that party's own privacy policy.
   - **Steam Web API / Steam Store (Valve Corporation)**: sends the SteamID64 to retrieve owned games, profile info, and store game data.
   - **Discord (Discord Inc.)**: used to send/receive command interactions and retrieve VC member information.
   - **Stripe (Stripe, Inc.)**: used to process Premium payments. Name, card details, and billing information are collected and held directly by Stripe; the Operator only retains limited data received from Stripe (subscription ID, customer ID, status, etc.).
   - **Hosting**: the Service itself (bot process and database) runs on the Operator's home server (Raspberry Pi). This website (landing page, this Policy, etc.) is served as static files via Cloudflare, Inc.'s Cloudflare Pages, which only delivers static content and has no access to the Service's database.
2. Collected information is not disclosed to any other third party except where required by law.

## 4. Retention Period

1. Information in the `users` table (Steam account linkage, etc.) is retained until you run `/unlink`, or until you request deletion from the Operator.
2. The `owned_games` cache goes stale after 1 hour but may remain in the database, un-deleted, until the next `/games`/`/pick` run. Running `/unlink` does not necessarily delete this Steam-ID-keyed cache automatically. If you want it fully deleted, contact us as described below.
3. `usage_log` (usage history) is retained for free-tier management purposes. The Operator aims to periodically delete or anonymize this data, but no automatic deletion mechanism is currently implemented.
4. `entitlements` and `stripe_subscriptions` (premium entitlement and billing linkage data) may be retained for a reasonable period after contract termination for accounting and anti-fraud purposes.

## 5. Your Rights

1. **Unlinking / deletion**: you may delete your own Steam account link (the corresponding row in the `users` table) at any time via `/unlink`.
2. **Access / deletion requests**: for data not removed by the above command (e.g., usage logs, cached game data), you may request access, deletion, or correction by contacting us below. We will respond within a reasonable scope.
3. **Cancelling Premium**: see `legal/refund.md` for how to cancel (e.g., via the Stripe Customer Portal).

## 6. Cookies and Similar Technologies

The Service itself (a Discord Bot) does not use cookies. However, if you go through a separately provided web page operated by the Operator — such as a Stripe checkout page or a landing page — that page may use cookies or similar technologies. See that page's own notice for details.

## 7. Use by Minors

Use of the Service requires meeting Discord's own age requirements. If a minor uses the paid Premium plan, please obtain parental/guardian consent first.

## 8. Changes to This Policy

This Policy may be revised in response to changes in law or in the Service. Material changes will be announced within the Service or on the website.

## 9. Contact

For inquiries regarding the handling of personal information, or access/deletion requests, contact:

- Operator: RyuTekLabo
- Email: support@ryuteklabo.com
