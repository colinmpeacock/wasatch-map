# Wasatch Backcountry Planner

A free 3D backcountry planning map for the Wasatch. It shows slope, aspect, avalanche problems and routes, and it reads the Utah Avalanche Center forecast automatically each morning.

## What's in this folder
| File | What it does |
|---|---|
| `index.html` | The whole map app |
| `manifest.webmanifest`, `sw.js`, `icon-*.png`, `icon.svg` | Let the map install on a phone and open offline |
| `scripts/fetch_uac.py` | Downloads the UAC forecasts and saves them to `data/uac/latest.json` |
| `workflow/uac-forecast.yml` | Runs that script every 15 minutes from about 5 to 10 AM Mountain time. On GitHub it has to live at `.github/workflows/uac-forecast.yml` (step 2). |
| `data/uac/` | Where the forecast file is written |

## Set it up on GitHub (about 10 minutes)
1. **Make the repository.** Sign in at github.com, then click **New repository**.
   - Name it something like `wasatch-map`.
   - Make it **Public**. GitHub Pages and scheduled Actions are free for public repositories.
   - Create it.
2. **Upload the files.** On the new repository, click **uploading an existing file**.
   - Drag in everything in this folder except the `workflow` folder, including the `scripts` and `data` folders.
   - Commit.
   - Then add the scheduled job: **Add file > Create new file**, type the name `.github/workflows/uac-forecast.yml` (the slashes create the folders), paste in the contents of `workflow/uac-forecast.yml`, and commit.
3. **Add your contact for UAC.** Go to **Settings > Secrets and variables > Actions > Variables > New repository variable**.
   - Name: `UAC_CONTACT`. Value: your email address.
   - UAC asks every program that reads its forecasts to identify itself this way, and may block requests that don't.
4. **Turn on the website.** Go to **Settings > Pages**.
   - Under Source, choose **Deploy from a branch**, then branch `main` and folder `/ (root)`.
   - Save. After a minute or two your map is live at `https://YOUR-NAME.github.io/wasatch-map/`.
5. **Run the forecast once by hand.** Go to the **Actions** tab, then **UAC forecast > Run workflow**.
   - When the run turns green, `data/uac/latest.json` appears in the repository.
   - Refresh the map. The **UAC forecast** section shows today's forecast.
6. **Put it on your phone.** Open the link and add it to your home screen:
   - iPhone: Safari > Share > **Add to Home Screen**.
   - Android: Chrome menu > **Install app**.

## Using the map file on your computer without GitHub
A page opened straight from a file can't read other files next to it. Two options:
- Run the fetcher yourself, then click **UAC forecast > Forecast data source > Load a forecast file** and pick the `data/uac/latest.json` it wrote. Run it from a terminal in this folder:
  ```
  python scripts/fetch_uac.py --contact you@example.com
  ```
- If the GitHub Action is already running, paste this address under **Forecast data source**:
  `https://raw.githubusercontent.com/YOUR-NAME/wasatch-map/main/data/uac/latest.json`

## Good to know
- **Issue times.** UAC usually issues forecasts between 5 and 8 AM, and the regular season starts in late fall. Before then, regions show "no forecast".
- **Old forecasts.** If a forecast is not from today, the panel says so in red, and the terrain colors stay off unless you turn them on.
- **Elevation bands.** The terrain colors split upper, mid and lower bands at the elevations set under Terrain analysis. The defaults are 8,000 and 9,500 ft. Check them against the elevations printed on the UAC rose for your region.
- **Problem locations.** UAC's problem roses mark where each problem is most likely, not everywhere it can occur. The full forecast on utahavalanchecenter.org is the authority. This map is a planning aid.
- **Inactive repositories.** GitHub pauses scheduled Actions in public repositories after 60 days with no activity. If the forecast stops updating after a quiet summer, re-enable it on the Actions tab.
- **Credit.** The forecast data belongs to the Utah Avalanche Center. The map credits them and links to the full forecast. Consider supporting UAC if you use it a lot.
