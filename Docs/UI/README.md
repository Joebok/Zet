# Dashboard UI captures

The standalone Playwright runner captures every dashboard page section at:

- Desktop: 1920 × 911
- iPad landscape: 1024 × 768
- Phone: 390 × 844

Install the capture dependency and browser once:

```powershell
npm install
npx playwright install chromium
```

Start the dashboard, then run the capture process from the repository root:

```powershell
.\run_zet_web.bat
npm run capture:ui
```

Run the two commands in separate terminals. To capture a dashboard at another
address, set `ZET_DASHBOARD_URL` before running the capture:

```powershell
$env:ZET_DASHBOARD_URL = "http://127.0.0.1:8081/"
npm run capture:ui
```

Screenshots are written to `Desktop`, `Ipad`, and `Phone`. Existing PNG files
in those folders are removed before each run, so screenshots for deleted pages
do not remain. Other files are preserved.

Pages are discovered from `main > section.page` elements. Adding or removing a
dashboard page therefore requires no capture-script update unless the dashboard
changes that page convention.
