# Tailscale HTTPS through the existing Caddy service
Status: complete
Related specification: Joe's request to serve zet2.schonbok.net through Caddy, 2026-10-19.

## Goal and current behavior
Add trusted, automatically renewed HTTPS for `zet2.schonbok.net` at Tailscale
IPv4 `100.87.65.80`, forwarding to the same local Python server on port 8081.
Keep `zet.schonbok.net` at `192.168.87.25` working. At the start, DNS resolved
correctly and both Windows services were running, but Caddy had no Tailscale listener.

## Impact and constraints
Machine-local configuration/scripts/firewall and service startup are affected;
the owning reference is `Docs/LAN_HTTPS.md`, linked from Development/Index.
No application source/API/data/queue changes, new dependency, Tailscale Serve,
Funnel, permanent test, or live AI job is needed. Preserve existing work.
Credentials stay in the existing restricted environment file. Joe explicitly
authorized Caddy setup and the new hostname's certificate-related DNS writes.

## Luna-sized work packets
### WP1 — Validate the new hostname and certificate permissions
- Dependencies: none. Files: isolated machine-local staging config/state/logs.
- Record current configuration for recovery; validate an isolated staging site
  for zet2 with existing EasyDNS credentials.
- Acceptance/checks: staging issuance/health and authoritative TXT cleanup;
  existing LAN health stays ready. Status: complete.

### WP2 — Enable dual-network Caddy and startup/firewall rules
- Dependencies: WP1. Files/interfaces: Caddyfile, Manage-Service.ps1, Windows
  ZetHTTPS/Tailscale services and a dedicated Tailscale-interface firewall rule.
- Bind the new site to 100.87.65.80:443 and use existing DNS-01 automation. Preserve
  the LAN site. Prepare one administrator helper action for dependency/firewall,
  restart, production trust checks on both names, and restart persistence.
- Acceptance/checks: trusted production health at both hostnames, explicit bind
  addresses, restricted firewall scope, startup dependency, challenge cleanup.
  Status: complete.

### WP3 — Browser acceptance and troubleshooting reference
- Dependencies: WP2. Files: disposable browser check, Docs/LAN_HTTPS.md,
  Docs/DEVELOPMENT.md, Docs/INDEX.md, and this plan.
- Verify both names with read-only browser/API/image/secure-context checks.
  Document new paths, failure modes and recovery. Ask Joe to verify another
  Tailscale-connected device; host-local checks cannot establish remote routing.
- Acceptance/checks: browser checks, remote-device confirmation, final diff and
  git diff --check. Complete/archive once acceptance is established.
  Status: complete; Joe confirmed the separate Tailscale-device check passed.

## Progress and decisions
- Existing LAN setup and its documentation are uncommitted work from this chat;
  preserve them. The second A record resolves to `100.87.65.80`.
- This session is not elevated. Its prior UAC launch was blocked by execution
  policy; prepare the complete administrator action for Joe rather than retrying
  the blocked elevation mechanism.
- Existing Python startup and the local Caddy admin API remain independent.
- WP1 passed: isolated zet2 staging certificate issued, HTTPS health ready, and
  all three authoritative nameservers reported zero TXT records after cleanup.
  The original LAN health remained ready. Backups of the original Caddyfile,
  service helper and browser check are in the restricted machine-local
  `backups/before-tailscale-20261019` directory. Staging was stopped.
- WP2: dual-network configuration validated and was applied via Caddy's local
  reload API. LAN health remains ready. Production zet2 issuance succeeded.
  The prepared EnableTailscale administrator action enables unattended Tailscale,
  adds its service dependency and interface-scoped TCP 443 firewall rule, restarts
  Caddy, and checks trusted HTTPS health on both names.
- Production zet2 chain/hostname trust passed using a normal SslStream handshake
  over TLS 1.3. Issuer Let's Encrypt YE2; expiry 2027-01-17T12:40:26Z. All three
  authoritative nameservers report zero challenge TXT records after issuance.
- Disposable Chromium checks passed for both origins: dashboard/health HTTP 200,
  secure context, generated UUID, text/image clipboard APIs, 10 inventory images,
  zero page errors, zero mixed-content messages, and zero insecure requests.
  These checks were host-local and did not change clipboard contents or submit
  any authored changes/generation jobs. Browser and helper scripts passed syntax
  checks; documentation PowerShell blocks parsed without errors.
- Joe confirmed the administrator EnableTailscale command finished. Its status
  reports complete and both HTTPS health URLs passed after restart. Read-back
  confirms service dependency on Tailscale and the enabled inbound TCP 443 rule:
  local 100.87.65.80, remote 100.64.0.0/10, interface Tailscale, all profiles,
  and only the Caddy executable. The unattended-mode command exited successfully.
- Both hostnames remain healthy after restart, with both explicit HTTPS addresses
  and the localhost-only admin API owned by the new Caddy service process.
- Joe confirmed a separate Tailscale-connected device loaded the dashboard and
  images without a certificate warning. Whether that check was performed away
  from home Wi-Fi was not separately reported.

## Final results
Machine-local implementation is complete. Both certificates are trusted, Caddy
automatically manages renewal, the Tailscale firewall/startup configuration is
active, and the service restart preserved both sites. Browser checks passed as
recorded above, and Joe confirmed separate-device Tailscale acceptance.
Documentation and final `git diff --check` passed. Actual future renewal and full
reboot remain unobserved. No application source or Python startup changed.
