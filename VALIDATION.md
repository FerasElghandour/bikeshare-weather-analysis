# Release validation — October 17, 2026

- Fresh complete notebook execution passed: `bikeshare_weather.ipynb` (26 code cells).
- Checks used isolated working copies with the required input files. Test-only Ford GoBike/TMDb inputs and executed outputs are not published.
- Published notebook code cells match the indexed submission archive exactly. Release cleanup only changes metadata, output retention and data-availability notes.
- Notebook schema validated; output cells and execution counts are cleared in the published files.
- Fresh checks ran on macOS with Python 3.14.3, NumPy 2.5.4, pandas 3.0.6, Matplotlib 3.11.2 and, where used, seaborn 0.13.2 and requests 2.34.2. Notebook execution used nbclient 0.11.0 and ipykernel 7.4.0.
- Gitleaks 8.30.1 reported no secret findings in the final prepared release.
- The README distinguishes historical recorded findings from release checks. A Udacity project pass does not certify this cleaned Git commit.
- The fresh weather check used the public NOAA station file downloaded for this release; the external NOAA snapshot is not committed.
