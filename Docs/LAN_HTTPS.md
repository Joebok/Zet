# Zet LAN and Tailscale HTTPS troubleshooting

Verified on Joe's Windows machine on **2026-10-19**. Start with the quick checks,
then use the symptom table. This guide describes the installed configuration;
the [completed deployment plan](../plans/completed/lan-https.md) records setup
and acceptance evidence. The [Tailscale extension plan](../plans/completed/tailscale-https.md)
records the second hostname and its separate acceptance checks.
The Tailscale firewall/startup action and host-local certificate/browser checks
passed. Joe also confirmed that a separate Tailscale-connected device loaded the
dashboard and images without a certificate warning.

## Quick checks

Open **https://zet.schonbok.net** on a device connected to the home LAN.
Use **https://zet2.schonbok.net** from an authorized device connected to Tailscale,
including when away from home. Both reach the same Zet server and library.
Use HTTPS without `:8081`. Port 80 redirects are disabled, so an HTTP bookmark
will not automatically become HTTPS.

Run these in an ordinary PowerShell window **on the Zet host**:

```powershell
Resolve-DnsName zet.schonbok.net -Type A -DnsOnly
Resolve-DnsName zet2.schonbok.net -Type A -DnsOnly
Get-Service ZetHTTPS
Invoke-RestMethod http://127.0.0.1:8081/api/health
Invoke-RestMethod https://zet.schonbok.net/api/health
Invoke-RestMethod https://zet2.schonbok.net/api/health
```

Expected: the LAN A record is `192.168.87.25`, the Tailscale A record is
`100.87.65.80`, the service is `Running`, and all health responses contain
`ready: true`. The local HTTP check tests Python; each
HTTPS check tests the complete path through Caddy and validates the certificate.
`127.0.0.1` always means the device running the command, so the HTTP check belongs
on the host, not another computer.

## How the pieces fit together

```text
Name lookup:
  Client's existing DNS resolver -> EasyDNS -> zet: 192.168.87.25
                                             zet2: 100.87.65.80

Dashboard traffic, inside the home LAN:
  Browser -> HTTPS/TCP 443 -> Caddy -> HTTP/localhost:8081 -> Zet Python server

Dashboard traffic over Tailscale:
  Authorized Tailscale client -> encrypted tailnet connection -> 100.87.65.80:443
                             -> Caddy -> HTTP/localhost:8081 -> same Zet server

Certificate issuance and renewal, using outbound internet access:
  Caddy -> EasyDNS API -> temporary public DNS TXT record
  Let's Encrypt -> checks that TXT record -> issues certificate to Caddy
```

| Piece | Installed setting | Responsibility |
| --- | --- | --- |
| EasyDNS A record | `zet.schonbok.net` -> `192.168.87.25` | Tells clients where to connect |
| EasyDNS Tailscale A record | `zet2.schonbok.net` -> `100.87.65.80` | Resolves the custom hostname to this computer's Tailscale address |
| Tailscale | Windows service `Tailscale`; unattended operation | Carries private connections from authorized clients; tailnet access rules still apply |
| Host LAN address | `192.168.87.25/24` | Must stay stable; reserve it in DHCP or use a suitable static configuration |
| Caddy | Windows service `ZetHTTPS` | Accepts HTTPS, presents the certificate, and forwards requests to Python |
| Python / Uvicorn | Existing Zet server on `0.0.0.0:8081` | Runs the dashboard, APIs, and application services |
| Let's Encrypt | Production ACME certificate authority | Issues the browser-trusted certificate at no certificate cost |
| EasyDNS live key and token | Private local credential file | Permit Caddy's temporary DNS validation records |
| Windows Firewall | Rules `ZetHTTPS-LAN-TCP443` and `ZetHTTPS-Tailscale-TCP443` | Allow each network to reach its matching Caddy listener |
| Browser | HTTPS secure context | Enables `crypto.randomUUID` and clipboard APIs; clipboard interactions still follow browser rules |

EasyDNS publishes the LAN and Tailscale addresses in public DNS; it does not carry Zet's
web traffic. The hostname/address are public DNS information, but that alone
does not provide internet routing to the server. This setup added no router port
forwarding. No Pi-hole, AdGuard, IIS, Tailscale Serve, or manually installed
certificate authority is part of this HTTPS path. LAN clients need only a browser;
clients using `zet2` need Tailscale connected. Publishing the Tailscale address does
not grant someone membership in, or access through, your tailnet.

The Python server remains independently managed. Caddy's automatic startup does
**not** start Zet. Direct Python HTTP access on 8081 also remains as it was before.

## Files, ports, and startup

Everything specific to this machine's HTTPS deployment lives under
`C:\ProgramData\ZetHTTPS`, outside the Git checkout.

| Relative path | Purpose |
| --- | --- |
| `bin\caddy.exe` | Caddy executable containing `dns.providers.easydns` |
| `Caddyfile` | Production hostname, bind address, proxy, certificate provider, storage, and logging settings |
| `credentials.env` | Live EasyDNS credentials, loaded into Caddy's environment on startup |
| `data\` | Persistent production certificates, private keys, ACME account, and renewal state |
| `logs\caddy.json` | Current operational log; rotated at 10 MiB, retaining up to three rotated files for up to seven days |
| `logs\service-*.txt` | Output from service installation/recovery configuration |
| `Enter-Credentials.ps1` | Masked local credential-entry dialog |
| `Manage-Service.ps1` | Administrator installation or restart helper, followed by trusted HTTPS health verification |
| `install-status.json`, `restart-status.json`, `enabletailscale-status.json` | Most recent helper status, step, detail, and timestamp |
| `service-verification.json` | Timestamped record of successful trusted HTTPS and restart checks |
| `tls-verification.json`, `browser-verification.json` | Historical deployment-check reports; these are not continuous monitoring |
| `Verify-Browser.mjs`, `browser-desktop.png` | Disposable desktop browser check and its captured image |
| `Caddyfile.staging`, `staging-data\`, `staging-logs\` | Isolated staging validation setup/evidence; not used by the production service |
| `Caddyfile.tailscale-staging`, `tailscale-staging-data\`, `tailscale-staging-logs\` | Separate staging validation for zet2; not used by production |
| `tailscale-browser-verification.json`, `tailscale-tls-verification.json` | Historical host-local checks of the Tailscale hostname |
| `backups\before-tailscale-20261019\` | Pre-extension Caddyfile and helper/browser scripts for recovery; not a complete machine backup |

Production listeners:

| Listener | Purpose |
| --- | --- |
| `192.168.87.25:443` | Caddy HTTPS; HTTP/1.1 and HTTP/2 |
| `100.87.65.80:443` | Caddy HTTPS for `zet2.schonbok.net` over Tailscale |
| `127.0.0.1:2020` | Caddy's local administration API; not a client-facing dashboard |
| `0.0.0.0:8081` | Existing Python dashboard server |

There is no production listener on port 80. HTTP/3 is disabled, so no UDP 443
firewall rule is required. The staging listeners on 8443/2021 were stopped after
validation.

The service runs as **NT AUTHORITY\LocalService**, with delayed automatic startup
and a dependency on the `Tailscale` Windows service. Tailscale is configured for
unattended operation so it can remain running after sign-out. Both sites share
one Caddy service: stopping Tailscale or losing its bind address can also affect
Caddy startup and LAN access. Service ordering and restart recovery help with
startup, but a complete machine reboot remains an untested acceptance boundary.
Crash recovery restarts it after 10, 30, then 60 seconds. The HTTPS directory
grants Joe, Administrators, and SYSTEM full access. LocalService has read/execute
access and can modify the production `data` and `logs` directories. Caddy's
expanded configuration autosave is disabled.

## Find the failing layer

| Symptom | First checks / next action |
| --- | --- |
| Name cannot be found | Check the EasyDNS A record and `Resolve-DnsName` on the affected computer. Compare with the host. A successful ping only proves name resolution/reachability, not HTTPS. |
| LAN hostname works on host, times out on another device | Check the client is on the home LAN rather than guest Wi-Fi, cellular, or an isolated network. Check TCP 443, the firewall rule, and the host's Private network profile. |
| `zet2` works on host, fails on another device | Confirm that device is connected to the correct tailnet, can reach `100.87.65.80`, and is allowed TCP 443 by tailnet policy. Check the dedicated Tailscale firewall rule/interface. A host-local check does not prove remote routing. |
| `zet2` fails while LAN HTTPS works | Check Tailscale connection/sign-in, the `zet2` A record, and its listener/certificate. HTTPS certificate renewal does not renew a Tailscale device's login/authorization. |
| HTTP fails but HTTPS works | Expected: port 80 and automatic redirects are disabled. Update the bookmark. |
| HTTPS returns **502 Bad Gateway** | Caddy is reachable but cannot get a usable response from Python. Check local HTTP health and the Python listener; start Zet using its normal launcher if stopped. |
| Python health works, HTTPS fails | Check `ZetHTTPS` service status, its log, the Caddy bind address, and certificate validity. |
| Failure after reboot | Allow delayed Caddy startup. Check Caddy service status and whether the separately managed Python server has been started. |
| Service stops immediately | Inspect `logs\caddy.json` and the Windows service error. Common causes include invalid configuration, inaccessible files, an absent bind address, or port 443 already in use. |
| Certificate warning | Verify the exact HTTPS hostname, device clock, actual served certificate, and renewal errors. The installed configuration must use production Let's Encrypt, not the staging issuer. |
| `crypto.randomUUID is not a function` | Confirm the page uses `https://zet.schonbok.net`, rather than the old HTTP address. Reload the page. |
| Clipboard action fails | First check trusted HTTPS; then retry with a direct tap/click. Browser permissions and Safari's interaction requirements can still apply. |
| Preferences or selections appear different | HTTP, LAN HTTPS and the zet2 hostname are different browser origins. Browser-local state does not automatically transfer; that does not itself mean server-side library data disappeared. |
| New router/network causes failures | Check the address and subnet. DNS, Caddy's bind address, and firewall local/remote addresses must agree. Some resolvers filter public DNS answers containing private addresses. |
| Renewal starts failing | Check outbound internet, EasyDNS live credentials/permissions, and DNS propagation in Caddy logs. Existing valid certificates may still serve the dashboard during a temporary renewal failure. |

### Separate a DNS problem from an HTTPS problem

On a Windows device connected to the home LAN, this bypasses DNS for one request
while still validating the certificate against the correct hostname:

```powershell
curl.exe --fail --show-error --resolve zet.schonbok.net:443:192.168.87.25 https://zet.schonbok.net/api/health
curl.exe --fail --show-error --resolve zet2.schonbok.net:443:100.87.65.80 https://zet2.schonbok.net/api/health
```

If this succeeds but the normal hostname request fails, investigate DNS or client
resolver settings. If both fail, continue with the service/network checks. Opening
`https://192.168.87.25` instead is not an equivalent test: the certificate is for
the hostname, not the IP address.
The second command also requires a working Tailscale path when run on a remote
device. It bypasses DNS, not Tailscale authorization or firewall rules.

### Inspect listeners and firewall

These are read-only checks; they do not restart anything:

```powershell
Get-NetTCPConnection -State Listen |
    Where-Object { $_.LocalPort -in @(443, 2020, 8081) } |
    Select-Object LocalAddress, LocalPort, OwningProcess

Get-NetConnectionProfile |
    Select-Object InterfaceAlias, NetworkCategory

Get-NetFirewallRule -Name ZetHTTPS-LAN-TCP443 |
    Select-Object Name, Enabled, Direction, Action, Profile

Get-NetFirewallRule -Name ZetHTTPS-LAN-TCP443 |
    Get-NetFirewallAddressFilter |
    Select-Object LocalAddress, RemoteAddress

Get-NetFirewallRule -Name ZetHTTPS-LAN-TCP443 |
    Get-NetFirewallPortFilter |
    Select-Object Protocol, LocalPort

Get-NetFirewallRule -Name ZetHTTPS-LAN-TCP443 |
    Get-NetFirewallApplicationFilter |
    Select-Object Program
```

Expected firewall settings: enabled inbound Allow, **Private** profile,
TCP 443, local address `192.168.87.25`, remote subnet `192.168.87.0/24`, and the
Caddy executable. A change to the network's Public/Private classification can
therefore affect access. Review the network classification rather than disabling
the firewall. Permissions may require an administrator terminal on some systems.

For the Tailscale rule, use `ZetHTTPS-Tailscale-TCP443` in the same inspection
commands. Expected settings: inbound Allow, TCP 443, local address
`100.87.65.80`, remote range `100.64.0.0/10`, interface alias **Tailscale**, Caddy's
executable, and all network profiles. The explicit interface/address restriction
keeps this rule separate from LAN/public adapters. Tailnet policy still decides
which authenticated clients may connect. Inspect the interface filter with:

```powershell
Get-NetFirewallRule -Name ZetHTTPS-Tailscale-TCP443 |
    Get-NetFirewallInterfaceFilter |
    Select-Object InterfaceAlias
Get-Service ZetHTTPS | Select-Object -ExpandProperty ServicesDependedOn
& 'C:\Program Files\Tailscale\tailscale.exe' status
```

### Read the log and setup status

```powershell
Get-Content C:\ProgramData\ZetHTTPS\logs\caddy.json -Tail 40
Get-Content C:\ProgramData\ZetHTTPS\install-status.json
```

Look for the error nearest the failure time. Proxy connection errors point toward
Python; DNS/API/authorization errors point toward certificate validation. Rotated
logs may contain earlier events. Helper status is historical: `complete` means
that helper run succeeded at its recorded time, not that the site is healthy now.

## Start or restart the appropriate component

If Python is stopped, use the normal Zet launcher. The current Windows launcher
can be invoked from PowerShell:

```powershell
& 'C:\Users\Joe\Projects\Zet\run_zet_web.bat'
```

It checks for the existing 8081 listener before launching Python. Keep its terminal
open while using this launcher. Do not launch a second server against the same
normal library to diagnose HTTPS.

For a running Caddy service that needs restarting, use **PowerShell / Terminal as
administrator**:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\ProgramData\ZetHTTPS\Manage-Service.ps1 -Action Restart
```

This briefly interrupts HTTPS, restarts only Caddy, and waits for trusted HTTPS
health. Python must also be healthy for the helper's final check to pass.
When `zet2` is configured, the helper checks trusted health at both hostnames.
To start a stopped Caddy service, run `Start-Service ZetHTTPS` in the administrator
terminal, then repeat the quick checks.

## Certificates and EasyDNS credentials

Caddy automatically handles issuance and renewal while running. There is no
separate scheduled renewal job. Outbound access to EasyDNS and Let's Encrypt is
needed for issuance/renewal; clients do not need the API credentials.

Validation uses temporary public TXT records named
`_acme-challenge.zet.schonbok.net` and `_acme-challenge.zet2.schonbok.net`.
They may be absent during normal operation; that is expected. Let Caddy manage
them rather than editing them during validation. Credentials must allow both.
No inbound public connection to Zet is required for DNS-01 validation.

To replace the live token/key, run this in an **ordinary interactive** PowerShell
window and enter both values in the masked dialog:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File C:\ProgramData\ZetHTTPS\Enter-Credentials.ps1
```

Then use the administrator restart command above so the service reads the new
file. The Caddyfile references `EASYDNS_API_TOKEN` and `EASYDNS_API_KEY`; keep actual
values in `credentials.env`. Do not paste credentials or certificate private keys
into chat, Git, command arguments, or troubleshooting output.

To inspect the certificate actually served, use the browser's site-certificate
viewer, or run this read-only PowerShell check on the host:

```powershell
$zetTcp = [Net.Sockets.TcpClient]::new('192.168.87.25', 443)
$zetTls = $null
try {
    $zetTls = [Net.Security.SslStream]::new($zetTcp.GetStream(), $false)
    $zetTls.AuthenticateAsClient('zet.schonbok.net')
    $zetCert = [Security.Cryptography.X509Certificates.X509Certificate2]::new($zetTls.RemoteCertificate)
    $zetCert | Select-Object Subject, Issuer, NotBefore, NotAfter, Thumbprint
} finally {
    if ($zetTls) { $zetTls.Dispose() }
    $zetTcp.Dispose()
}
```

This uses normal certificate validation. A failed handshake is diagnostic evidence;
do not disable production certificate checks to make it appear healthy.

## Configuration changes, updates, and recovery

- **Changing the LAN address:** update the EasyDNS A record, `bind` in `Caddyfile`,
  the firewall local/remote scope, and the address/subnet embedded in
  `Manage-Service.ps1`. The helper creates a missing firewall rule but does not
  rewrite an existing rule's addresses. Also check for unexpected AAAA records.
  Prefer keeping the current address stable.
- **Changing the Tailscale address:** update the zet2 A record, its Caddy `bind`,
  and the Tailscale rule/helper address. The existing firewall rule is not
  automatically rewritten. Keep the current node registration/address when
  possible; reinstallation or removing/re-registering the device may change it.
- **Updating Caddy:** preserve the EasyDNS module. A stock Caddy binary may not
  contain it. Check the proposed executable with `version` and
  `list-modules --skip-standard` before replacing the service binary. Obtain it
  from [Caddy's custom download page](https://caddyserver.com/download) with
  `github.com/caddy-dns/easydns` selected. No automatic binary updater was installed.
- **Before restarting with edited configuration:** validate it with the command
  below. It loads the credential file without putting values in command history.
  Validation is not proof that DNS permissions or issuance will succeed.

```powershell
& 'C:\ProgramData\ZetHTTPS\bin\caddy.exe' validate --config C:\ProgramData\ZetHTTPS\Caddyfile --adapter caddyfile --envfile C:\ProgramData\ZetHTTPS\credentials.env
```

For recovery, keep a protected backup of `Caddyfile`, `credentials.env`, `data`,
the custom executable, and the two administration scripts. This includes secrets
and private keys; use an encrypted backup with restricted access. Persistent
`data` allows certificate/account state to survive restarts. Do not delete it to
force renewal. The Windows service/firewall definitions live outside the folder;
copying the folder alone does not recreate them.

The prepared `Manage-Service.ps1 -Action Install` command, run as administrator,
creates missing service/firewall definitions and verifies trusted HTTPS before
and after restarting Caddy. With zet2 configured, it also configures Tailscale
unattended operation, service dependency, and the dedicated interface firewall.
For an already-installed service, the one-time extension command is:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\ProgramData\ZetHTTPS\Manage-Service.ps1 -Action EnableTailscale
```

These administrator actions assume the paths and addresses described here,
valid credentials, and a healthy Python server. A restored machine with different
addresses needs those settings reviewed first. Full rebuild/reboot recovery has
not been tested; the initial installation and service restart have been tested.

## Validation record and references

Initial verification passed staging and production DNS-01 issuance, TXT cleanup
on all three EasyDNS nameservers, normal TLS hostname/chain validation, and HTTPS
health before/after service restart. Chromium loaded 10 inventory images with no
page errors, mixed content, or insecure requests and exposed UUID/clipboard APIs.
Joe confirmed iPad Safari certificate trust, image loading, and clipboard actions.
Actual future renewal and a complete host reboot have not yet been observed.
The guide's read-only DNS, health, listener, firewall, and served-certificate checks
were rerun successfully when this guide was written; all PowerShell examples were
syntax-checked. Writing this guide did not restart services or change networking.
The subsequent zet2 extension passed separate staging/production issuance and
authoritative challenge cleanup. Both hostnames passed host-local browser and
normal certificate checks. Joe completed the administrator action; firewall and
service dependency read-back passed, and both sites stayed healthy after restart.
Joe confirmed the separate Tailscale-device acceptance check passed. Testing away
from home Wi-Fi was not separately reported; see the extension plan.

- [Caddy EasyDNS module](https://caddyserver.com/docs/modules/dns.providers.easydns)
- [Caddy Windows service instructions](https://caddyserver.com/docs/running#windows-service)
- [Caddy command-line reference](https://caddyserver.com/docs/command-line)
- [Let's Encrypt DNS-01 explanation](https://letsencrypt.org/docs/challenge-types/#dns-01-challenge)
- [Zet development/run instructions](DEVELOPMENT.md)
