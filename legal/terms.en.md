> ※This is a template. Review the content yourself before publishing and consult a professional (e.g. a lawyer) if needed. This is not intended as definitive legal advice. The Japanese version (`terms.md`) is the primary/authoritative document; this is a convenience translation.

# Terms of Service

Last updated: 2026-07-06

These Terms of Service ("Terms") govern the use of the Discord Bot "今日なんのゲームする？Bot" (the "Service"), provided by RyuTekLabo ("we", "us", "the Operator"). By adding the Service to a server or running any of its commands, you agree to these Terms.

## 1. Service Overview

The Service scans the voice channel (VC) you are in on Discord, finds Steam games commonly owned among the members present, and suggests titles you can play together. Main commands:

- `/link` — Link your Steam profile URL, custom URL name, or SteamID64
- `/unlink` — Remove the link
- `/profile` — Check your own or another member's link status
- `/games` — Show up to the top 10 multiplayer-capable games commonly owned by the current VC members
- `/pick` — Randomly suggest one title from the candidates above
- `/premium` — Check current free-tier usage and premium subscription status

## 2. Eligibility

1. Use of the Service requires a valid Discord account and membership in a Discord server where the Service has been added (the "Server").
2. Linking a Steam account via `/link` requires a valid Steam account. To fetch your owned-games list, that Steam account's privacy setting for "Game details" must be set to Public.
3. You must meet the age and eligibility requirements of both Discord's and Steam's own terms of service/guidelines.

## 3. Prohibited Conduct

You must not:

1. Violate any applicable law or public order and morals.
2. Link another person's Steam account via `/link` without their consent (note: pasting someone else's profile URL only links that URL's Steam account — it does not benefit or affect the person who pasted it, by design).
3. Send excessive requests, or use automation to repeatedly invoke commands, in a way that places undue load on the Service.
4. Probe for or exploit vulnerabilities in the Service, or reverse-engineer it, except where permitted by law.
5. Attempt to circumvent the free-tier usage limits through improper means (e.g., abusive creation of multiple servers).
6. Engage in any other conduct the Operator deems inappropriate.

## 4. Compliance with Steam and Discord Terms

1. The Service uses the Steam Web API and Steam Store data. You must comply with the [Steam Subscriber Agreement](https://store.steampowered.com/subscriber_agreement/).
2. The Service is delivered via Discord's bot platform. You must comply with the [Discord Terms of Service](https://discord.com/terms) and [Discord Community Guidelines](https://discord.com/guidelines).
3. The Service is not officially affiliated with Valve Corporation (Steam) or Discord Inc.

## 5. Fees and Billing

1. The Service offers a free tier and a Premium plan.
2. **Free tier**: each Discord server may use the `/games` and `/pick` commands up to 3 times per day and 60 times per month (both limits apply, shared and pooled across all members of that server).
3. **Premium plan**: ¥380/month (tax included) removes the usage limit for the subscribed server. Premium is granted at the server (guild) level as a whole — not to the individual member who completes payment.
4. Payment is processed via **Stripe**, sold directly by the Operator. Discord's built-in monetization features are not used.
5. Premium is a monthly auto-renewing subscription. Unless cancelled, it automatically continues into the next billing period. See `legal/refund.md` for cancellation.
6. Fees may change with prior notice; changes take effect from the next renewal onward.

## 6. Disclaimer of Warranties

1. The Service is provided "as is," with no warranty, express or implied, as to completeness, accuracy, usefulness, or fitness for a particular purpose.
2. Owned-game and multiplayer-classification data is derived from the Steam Web API and unofficial Steam Store data; its accuracy or currency is not guaranteed.
3. Except in cases of willful misconduct or gross negligence by the Operator, the Operator is not liable for damages arising from use of, or inability to use, the Service. Where the Operator is liable, total liability is capped at the amount you paid the Operator in the preceding 3 months.
4. The Operator is not responsible for outages caused by third-party services (Discord, Steam, Stripe, hosting providers, etc.).

## 7. Changes, Suspension, and Termination of the Service

1. The Operator may change, suspend, or discontinue the Service without prior notice.
2. The Operator may suspend the Service in whole or in part for maintenance, failures, force majeure, or other unavoidable reasons.
3. If the Service is discontinued, handling of servers with active Premium subscriptions (including any prorated refunds) will follow `legal/refund.md` and any termination notice issued at that time.

## 8. Changes to These Terms

The Operator may revise these Terms as needed. Revised Terms will be announced within the Service, on the relevant Discord server, or on the website; continued use after such notice constitutes acceptance.

## 9. Governing Law and Jurisdiction

1. These Terms are governed by the laws of Japan.
2. The Yokohama District Court (横浜地方裁判所) shall have exclusive jurisdiction as the court of first instance for any dispute arising from the Service.

## 10. Contact

For questions about these Terms, contact support@ryuteklabo.com.
