"""Quality-gated weather integration and chronological demand-estimation benchmark."""
from __future__ import annotations

import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit
from .reporting import publish_report


def parse_weather(path):
    """Decode a GHCN daily station file; reject flagged and encoded missing values."""
    rows = []
    for line_number, line in enumerate(Path(path).read_text(encoding='ascii').splitlines(), 1):
        if len(line) != 269:
            raise ValueError(f'Weather line {line_number} has {len(line)} characters; expected 269.')
        year, month, element = int(line[11:15]), int(line[15:17]), line[17:21]
        if element not in {'TMAX', 'TMIN', 'PRCP'} or year not in {2011, 2012}:
            continue
        for day in range(1, 32):
            date = pd.to_datetime(f'{year}-{month:02}-{day:02}', errors='coerce')
            if pd.isna(date):
                continue
            offset = 21 + (day-1)*8
            value, flag = int(line[offset:offset+5]), line[offset+6]
            rows.append({'date': date, 'element': element,
                         'value': value / 10 if value != -9999 and flag == ' ' else np.nan})
    data = pd.DataFrame(rows)
    if data.empty:
        raise ValueError('Weather file contains no 2011–2012 TMAX/TMIN/PRCP observations.')
    if data.duplicated(['date', 'element']).any():
        raise ValueError('Duplicate weather date/element keys are not allowed.')
    wide = data.pivot(index='date', columns='element', values='value').rename(columns={'TMAX': 'tmax_c', 'TMIN': 'tmin_c', 'PRCP': 'precip_mm'})
    if not {'tmax_c', 'tmin_c', 'precip_mm'} <= set(wide):
        raise ValueError('Weather source must contain temperature and precipitation elements.')
    return wide.reset_index()


def prepare_daily(bike, weather):
    required = {'dteday', 'hr', 'cnt', 'casual', 'registered', 'workingday'}
    if missing := required - set(bike):
        raise ValueError(f'Missing rental columns: {sorted(missing)}')
    data = bike.copy()
    data['date'] = pd.to_datetime(data.dteday, errors='raise').dt.normalize()
    for col in ['hr', 'cnt', 'casual', 'registered', 'workingday']:
        data[col] = pd.to_numeric(data[col], errors='raise')
    if not np.isfinite(data[['hr', 'cnt', 'casual', 'registered', 'workingday']]).all().all():
        raise ValueError('Rental numeric inputs must be finite.')
    if not data.hr.between(0, 23).all() or not data.hr.eq(data.hr.astype(int)).all():
        raise ValueError('Hour must be an integer from 0 to 23.')
    if data.duplicated(['date', 'hr']).any():
        raise ValueError('Duplicate rental date/hour keys are not allowed.')
    if not data.cnt.eq(data.casual + data.registered).all() or data[['cnt', 'casual', 'registered']].lt(0).any().any():
        raise ValueError('Rental counts must be nonnegative and equal casual + registered.')
    if not data.workingday.isin([0, 1]).all() or data.groupby('date').workingday.nunique().gt(1).any():
        raise ValueError('Working-day flags must be binary and consistent within each date.')
    coverage = data.groupby('date').hr.nunique()
    full_calendar = pd.date_range(data.date.min(), data.date.max(), freq='D')
    missing_hours = int(24 * len(full_calendar) - len(data))
    daily = data.groupby('date').agg(rentals=('cnt', 'sum'), workingday=('workingday', 'first')).reset_index()
    daily = daily[daily.date.isin(coverage[coverage == 24].index)]
    if weather.duplicated('date').any():
        raise ValueError('Weather dates must be unique before joining.')
    joined = daily.merge(weather, on='date', how='left', validate='one_to_one')
    complete = joined[['tmax_c', 'tmin_c', 'precip_mm']].notna().all(axis=1)
    final = joined.loc[complete].copy()
    if final.empty:
        raise ValueError('No complete rental/weather dates remain after coverage checks.')
    if not np.isfinite(final[['tmax_c', 'tmin_c', 'precip_mm']]).all().all():
        raise ValueError('Weather measurements must be finite.')
    if final.tmax_c.lt(final.tmin_c).any() or final.precip_mm.lt(0).any():
        raise ValueError('Weather measurements violate temperature ordering or precipitation bounds.')
    final = final.sort_values('date').reset_index(drop=True)
    return final, {'hourly_rows': len(data), 'calendar_days': len(full_calendar), 'missing_hour_slots': missing_hours,
                   'complete_hour_days': len(daily), 'weather_incomplete_days': int((~complete).sum()), 'analysis_days': len(final)}


def chronological_benchmark(daily):
    """Compare fixed models on the latest 20% of dates, never random-split.

    Observed weather is contemporaneous. This estimates historical demand under
    observed conditions; it is not a forecast using predicted future weather.
    """
    if len(daily) < 100:
        raise ValueError('At least 100 complete days are required for the chronological benchmark.')
    data = daily.set_index('date').sort_index().copy()
    data['weekday'] = data.index.dayofweek
    data['month'] = data.index.month
    data['year'] = data.index.year
    # Calendar shift is intentional: seven calendar days, never seven retained rows.
    data['lag7'] = data.rentals.reindex(data.index - pd.Timedelta(days=7)).to_numpy()
    data = data.dropna(subset=['lag7'])
    cut = int(len(data) * .8)
    train, test = data.iloc[:cut], data.iloc[cut:]
    if len(train) < 50 or len(test) < 10:
        raise ValueError('Insufficient train/test dates after calendar-lag alignment.')
    calendar = ['workingday', 'weekday', 'month', 'year']
    predictions = {'Training median': np.full(len(test), train.rentals.median()), 'Seven-day observed lag': test.lag7.to_numpy()}
    for name, features in [('Calendar model', calendar), ('Calendar + weather model', calendar + ['tmax_c', 'tmin_c', 'precip_mm'])]:
        model = HistGradientBoostingRegressor(max_iter=150, max_leaf_nodes=15, learning_rate=.05, l2_regularization=1, random_state=42)
        model.fit(train[features], train.rentals)
        predictions[name] = model.predict(test[features])
    metrics = [{'model': name, 'mae': float(mean_absolute_error(test.rentals, pred)),
                'rmse': float(np.sqrt(mean_squared_error(test.rentals, pred)))} for name, pred in predictions.items()]
    records = [{'date': str(date.date()), 'observed': float(y), **{name: float(predictions[name][i]) for name in predictions}} for i, (date, y) in enumerate(test.rentals.items())]
    validation = []
    # Expanding-window validation stays wholly inside the training period.
    for fold, (fit_idx, val_idx) in enumerate(TimeSeriesSplit(n_splits=3).split(train), 1):
        fit, val = train.iloc[fit_idx], train.iloc[val_idx]
        estimates = {'Training median': np.full(len(val), fit.rentals.median()),
                     'Seven-day observed lag': val.lag7.to_numpy()}
        for name, features in [('Calendar model', calendar), ('Calendar + weather model', calendar + ['tmax_c', 'tmin_c', 'precip_mm'])]:
            estimator = HistGradientBoostingRegressor(max_iter=150, max_leaf_nodes=15, learning_rate=.05, l2_regularization=1, random_state=42)
            estimator.fit(fit[features], fit.rentals)
            estimates[name] = estimator.predict(val[features])
        validation.append({'fold': fold, 'train_end': str(fit.index.max().date()),
                           'validation_start': str(val.index.min().date()), 'validation_end': str(val.index.max().date()),
                           'metrics': [{'model': name, 'mae': float(mean_absolute_error(val.rentals, pred))} for name, pred in estimates.items()]})
    return {'split': {'train_start': str(train.index.min().date()), 'train_end': str(train.index.max().date()),
                      'test_start': str(test.index.min().date()), 'test_end': str(test.index.max().date()),
                      'train_days': len(train), 'test_days': len(test)},
            'metrics': metrics, 'predictions': records, 'expanding_validation': validation,
            'protocol': 'Fixed 80/20 chronological split; fixed hyperparameters; no test-set tuning; observed contemporaneous weather; rolling observed seven-day lag.',
            'model_parameters': {'max_iter': 150, 'max_leaf_nodes': 15, 'learning_rate': .05, 'l2_regularization': 1, 'random_state': 42}}


def summarize(daily, audit):
    groups = daily.assign(year=daily.date.dt.year, precipitation=np.where(daily.precip_mm > 0, 'Measured precipitation', 'Zero reported')).groupby(['year', 'precipitation']).rentals.agg(['count', 'median']).reset_index()
    benchmark = chronological_benchmark(daily)
    return {'audit': audit, 'precipitation_groups': groups.to_dict('records'), 'benchmark': benchmark,
            'monthly': daily.assign(month=daily.date.dt.strftime('%Y-%m')).groupby('month').rentals.agg(['count', 'mean']).reset_index().to_dict('records')}


def report_spec(result):
    b = result['benchmark']
    views = [{'label': 'Chronological holdout: absolute error', 'kind': 'bar', 'unit': 'rentals / day',
       'series': [{'name': 'Mean absolute error, lower is better', 'points': [{'x': r['model'], 'y': r['mae']} for r in b['metrics']]}]}]
    views.append({'label': 'Holdout: observed and estimated demand', 'kind': 'line', 'unit': 'rentals / day',
      'series': [{'name': name, 'points': [{'x': r['date'], 'y': r[name]} for r in b['predictions']]} for name in ['observed', 'Calendar model', 'Calendar + weather model']]})
    names = [r['model'] for r in b['metrics']]
    views.append({'label': 'Training period: expanding validation', 'kind': 'bar', 'unit': 'mean fold MAE',
     'series': [{'name': 'Three expanding-window validation folds', 'points': [
        {'x': name, 'y': float(np.mean([next(m['mae'] for m in fold['metrics'] if m['model'] == name) for fold in b['expanding_validation']]))} for name in names]}]})
    for year in sorted({r['year'] for r in result['precipitation_groups']}):
        views.append({'label': f'{year}: precipitation groups', 'kind': 'bar', 'unit': 'median daily rentals',
          'series': [{'name': str(year), 'points': [{'x': r['precipitation'], 'y': r['median']} for r in result['precipitation_groups'] if r['year'] == year]}]})
    best = min(b['metrics'], key=lambda r: r['mae'])
    losses = sum(next(m['mae'] for m in fold['metrics'] if m['model'] == 'Calendar + weather model') > next(m['mae'] for m in fold['metrics'] if m['model'] == 'Seven-day observed lag') for fold in b['expanding_validation'])
    return {'title': 'Weather, demand and a fair comparison', 'subtitle': 'A validated daily dataset, followed by a chronological benchmark against simple alternatives.',
     'category': 'Data engineering / applied modelling', 'findings': [f'{result["audit"]["missing_hour_slots"]} absent date/hour slots are identified before daily totals are compared.',
      f'{best["model"]} has the lowest holdout MAE: {best["mae"]:.1f} rentals per day.',
      f'The weather model trails the seven-day lag in {losses} of three earlier validation periods, exposing sensitivity to time period.'],
     'views': views, 'methodology': [{'title': 'Quality gate before modelling', 'body': 'Require unique date/hour keys, valid count identities and complete 24-hour coverage. Decode GHCN missing values and reject quality-flagged weather observations before a one-to-one daily join.'},
      {'title': 'Chronological benchmark', 'body': b['protocol'] + ' Three expanding-window validation folds stay inside the training period. Calendar-only and calendar-plus-weather models use the same fixed estimator settings. MAE and RMSE are evaluated on the same dates.'},
      {'title': 'Decision boundary', 'body': 'Contemporaneous observed weather makes this retrospective demand estimation, not a production forecast. Missing dates, seasonal changes and system growth affect generalization. A single holdout does not establish future business impact.'}],
     'notes': 'Input fingerprints and software versions are saved with the report. The NOAA station source is mutable.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rentals', type=Path, default=Path('raw/uci_bikeshare_hourly.csv'))
    parser.add_argument('--weather', type=Path, required=True, help='Downloaded GHCN station .dly file')
    parser.add_argument('--output', type=Path, default=Path('reports'))
    args = parser.parse_args()
    try:
        daily, audit = prepare_daily(pd.read_csv(args.rentals), parse_weather(args.weather))
        result = summarize(daily, audit)
        publish_report(args.output, result, report_spec(result), [args.rentals, args.weather])
    except (ValueError, OSError) as exc:
        parser.exit(2, f'Analysis failed: {exc}\n')


if __name__ == '__main__':
    main()
