# LAN HTTPS with Caddy and EasyDNS
Status: complete
Related specification: Joe's approved implementation plan in this chat, 2026-10-19.

## Goal and current behavior
Serve Zet at `https://zet.schonbok.net` with a trusted Let's Encrypt certificate
and unattended renewal. The hostname resolves to this machine's private
`192.168.87.25/24` address. At the start, Python served Zet on port 8081 and Caddy
was not installed. Ordinary LAN HTTP prevents secure-context UUID and clipboard APIs.

## Impact and constraints
- Machine-local Caddy binary, config, secrets, certificate state, and logs live in
  `C:\ProgramData\ZetHTTPS`; no secrets enter the repository or tool output.
- Preserve Python startup, application APIs, storage, queues, and production data.
- DNS-01 writes, Caddy/EasyDNS installation, service/firewall configuration, and
  certificate issuance are authorized by the implementation request.
- No new permanent tests, live AI jobs, router port forwarding, IIS, or DNS server.
- Documentation owner: `Docs/DEVELOPMENT.md` (deployment/run instructions).
  No domain data/invariant or code-map ownership changes are expected.

## Work packets
### WP1 — Prepare executable, configuration, and private credentials
- Dependencies: none. Files: machine-local HTTPS directory and this plan.
- Download Caddy with the EasyDNS module; apply restricted Windows ACLs. Provide
  local private credential entry without recording secrets in command history.
- Acceptance/validation: executable version/module inventory, config validation,
  secret-file ACL inspection. Status: complete.

### WP2 — Validate DNS-01 and enable trusted HTTPS
- Dependencies: WP1. Interfaces: EasyDNS live TXT records, Let's Encrypt staging
  then production, Caddy forwarding to `127.0.0.1:8081`.
- Use separate staging/production certificate state; bind to the LAN address,
  expose TCP 443 to the local subnet, and confirm DNS challenge cleanup.
- Acceptance/validation: staging issuance, production TLS trust/hostname/expiry,
  health/dashboard/image HTTP responses. Status: complete.

### WP3 — Persist operation and record acceptance
- Dependencies: WP2. Files/interfaces: Windows service/firewall, this plan,
  `Docs/DEVELOPMENT.md`.
- Configure automatic service startup/recovery and persistent state; restart the
  service and repeat HTTPS/browser checks. Document operation and recovery.
- Acceptance/validation: secure context, UUID/clipboard availability, no mixed
  content on inspected dashboard, successful service restart; Joe confirmed the
  iPad Safari checks passed. Status: complete.

## Validation boundaries
Use disposable configuration/browser checks and read-only requests against the
running dashboard; never submit model/render jobs. Check staged TXT cleanup,
normal certificate trust, browser APIs, sample images, secret ACLs, and final
`git diff --check`. No app source change means the fixture E2E baseline is not the
primary test for this host-level deployment.

## Progress and decisions
- 2026-10-19: DNS A record verified as `192.168.87.25`; no AAAA/CAA answer found.
  TCP 443 was unused. EasyDNS live key/token were available, but TXT permissions
  had not yet been verified. Go is installed. This session is not elevated;
  Windows service/firewall configuration will require a UAC-elevated local helper.
- Address reservation is not inspectable here; Joe must keep the LAN address stable.
- WP1: downloaded official custom Caddy 2.11.7 with exactly one nonstandard module,
  `dns.providers.easydns`; binary SHA256
  `528C43EE8BEB2977CCF95C2AF90FD479618D16AEE4E34F80758FE56F2E2F96E3`.
  Private local credential entry completed. Root ACL grants Joe, Administrators,
  and SYSTEM full access, LocalService read/execute; only production data/log
  directories additionally grant LocalService modify. Both configurations passed
  `caddy validate --envfile ...`. Backend health reports ready.
- WP2: staging process started on loopback port 8443 with isolated state/logs;
  initial authoritative `_acme-challenge` TXT count was zero.
- Staging DNS-01 issuance passed with zero Caddy errors. Staging HTTPS health
  returned HTTP 200/ready; its untrusted staging chain was accepted only for that
  disposable request. All three authoritative nameservers subsequently reported
  zero challenge TXT records. Staging was stopped before production startup.
- Codex execution policy rejected launching an elevated installer ("blocked by
  policy"). Joe was given the prepared administrator command; the resulting
  LocalService `ZetHTTPS` service is running. Production issuance succeeded.
  The helper also verifies trusted HTTPS after restarting Caddy, avoiding a
  second administrative setup action.
- Production certificate: Let's Encrypt YE1, DNS name `zet.schonbok.net`, valid
  through 2027-01-17T12:12:41Z. A standard .NET SslStream handshake validated
  hostname/chain successfully using TLS 1.3; no certificate bypass was used.
  Normal PowerShell HTTPS health returned ready.
- `Manage-Service.ps1 -Action Install` completed under Joe's administrator
  terminal, including trusted HTTPS before and after a service restart.
  Windows read-back confirms LocalService identity, delayed automatic startup,
  restart recovery delays 10/30/60 seconds, TCP 443 listener at `192.168.87.25`,
  localhost-only admin API, and the Private-profile firewall allow rule limited
  to `192.168.87.0/24`. No 80/8443/2021 listener remains. Python is unchanged.
- Production challenge cleanup: all three authoritative EasyDNS nameservers
  report zero TXT records after issuance.
- Disposable Playwright/Chromium inspection passed normal HTTPS trust, dashboard
  and health HTTP 200, secure context, generated UUID, text/image clipboard API
  availability, and 10 loaded inventory images. Zero page errors, mixed-content
  messages, or insecure network requests were observed. No clipboard contents,
  authored files, or generation jobs were changed by the browser check.
- Private credential entry and service helper scripts passed PowerShell parser
  checks; the disposable browser script passed Node syntax validation.
- Joe confirmed the administrator command finished and iPad Safari acceptance
  passed: normal certificate trust, image loading and representative clipboard
  actions. Follow-up service status was Running and HTTPS health remained ready.

## Final results
HTTPS is live and the machine-local implementation passed the checks above.
Only this plan and the owning development documentation are changed in Git;
application source, startup and declared project dependencies are unchanged.
Caddy and its approved EasyDNS module are machine-local deployment dependencies.
The running service handles future renewals; an actual future renewal and a full
machine reboot have not been observed. Joe confirmed iPad Safari acceptance.
The LAN address must remain stable. Final diff review and `git diff --check` passed.
