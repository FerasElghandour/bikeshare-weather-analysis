# Washington Bike-Share and Weather

Combine UCI Capital Bikeshare hourly counts with NOAA daily weather observations, validate source quality and reshape the records into daily analysis tables.

## Completion

Udacity project: **Real World Data Wrangling with Python**. Passed on **2026-10-11**, verified against the authenticated Udacity project-pass email. The receipt is kept privately.

This is a cleaned portfolio edition of the recovered implementation associated with that project. Udacity's email confirms the project passed; it does not certify this Git commit or identify the accepted archive by hash.

## Approach

The notebook checks missing hour slots, decodes NOAA missing values and quality flags, reshapes monthly weather records, restricts rentals to dates with 24 coded hours, and joins daily rental counts to temperature and precipitation.

## Recorded results

The saved analysis found 165 absent date/hour slots across 76 dates. On the complete-hour cohort, median rentals on days with measured precipitation were about 17.3% lower in 2011 and 20.4% lower in 2012 than on days with zero reported precipitation. These are descriptive associations.

These figures come from saved execution records. Release validation is described in `VALIDATION.md`.

## Run

Release execution checks used Python 3.14.3; analysis dependency versions are pinned in `requirements.txt`.

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
jupyter lab
```

Open `bikeshare_weather.ipynb` and run all cells from the repository root. The first run needs access to NOAA. The notebook creates `raw/`, `cleaned/` and `figures/` as needed.

See [DATA.md](DATA.md) for inputs, attribution and excluded materials. Notebook outputs are cleared in this edition to exclude raw-data previews and machine-specific output.

## Limitations

Airport weather is a regional proxy. Season, working days and system growth can confound the comparisons. Missing hourly records are not assumed to mean zero demand. NOAA data can be revised, so a fresh download may differ from the original run.

## Provenance and rights

Prepared by Mohamed Feras Elghandour with AI assistance in implementation, debugging, analysis and documentation. This repository does not claim unaided coding or production deployment. Udacity supplied the educational context; third-party tools and inputs retain their own rights. Course lesson text, assessment prompts, rubrics, answer keys, pass-email bodies and authenticated classroom captures are excluded.

No new repository-wide software license is granted in this release. Existing third-party license notices remain applicable; see [DATA.md](DATA.md) and any `third_party/` or `vendor/` notices. This is an educational portfolio project, without a claim of Udacity endorsement.
