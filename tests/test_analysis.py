import numpy as np
import pandas as pd
import pytest
from analysis import parse_weather, prepare_daily, chronological_benchmark


def rental_fixture():
    return pd.DataFrame([{'dteday': f'2011-01-{day:02}', 'hr': hour, 'cnt': 3,
                          'casual': 1, 'registered': 2, 'workingday': 1}
                         for day in [1,2] for hour in range(24)])


def weather_fixture():
    return pd.DataFrame({'date': pd.date_range('2011-01-01', periods=2),
                         'tmax_c': [10.,11.], 'tmin_c': [1.,2.], 'precip_mm': [0.,1.]})


def test_missing_hours_are_not_treated_as_zero_demand():
    rentals = rental_fixture().drop(index=0)
    daily, audit = prepare_daily(rentals, weather_fixture())
    assert len(daily)==1 and audit['missing_hour_slots']==1
    assert daily.iloc[0].rentals==72


def test_duplicate_keys_fail_instead_of_double_counting():
    rentals = rental_fixture()
    with pytest.raises(ValueError, match='Duplicate rental'):
        prepare_daily(pd.concat([rentals,rentals.iloc[[0]]]), weather_fixture())


def test_count_identity_and_weather_ordering_are_enforced():
    rentals = rental_fixture()
    rentals.loc[0,'cnt']=9
    with pytest.raises(ValueError, match='counts'):
        prepare_daily(rentals, weather_fixture())
    weather = weather_fixture()
    weather.loc[0,'tmin_c']=99
    with pytest.raises(ValueError, match='temperature'):
        prepare_daily(rental_fixture(), weather)


def test_ghcn_quality_flags_and_missing_sentinel_are_decoded(tmp_path):
    fields = ['00100   ']*31
    fields[1] = '-9999   '
    fields[2] = '00200 Q '
    lines = ['USW00013743201101'+element+''.join(fields) for element in ['TMAX','TMIN','PRCP']]
    path=tmp_path/'station.dly';path.write_text('\n'.join(lines))
    result = parse_weather(path)
    assert result.iloc[0].tmax_c == 10
    assert pd.isna(result.iloc[1].tmax_c) and pd.isna(result.iloc[2].tmax_c)


def test_chronological_split_and_calendar_lag_do_not_use_future_targets():
    dates=pd.date_range('2011-01-01',periods=160).delete([12,40])
    daily=pd.DataFrame({'date':dates,'rentals':np.arange(len(dates))+100,
                        'workingday':(dates.dayofweek<5).astype(int),'tmax_c':20.,'tmin_c':10.,'precip_mm':0.})
    result=chronological_benchmark(daily)
    assert result['split']['train_end'] < result['split']['test_start']
    for fold in result['expanding_validation']:
        assert fold['train_end'] < fold['validation_start'] <= fold['validation_end'] < result['split']['test_start']
    original=daily.set_index('date').rentals
    for row in result['predictions']:
        assert row['Seven-day observed lag'] == original.loc[pd.Timestamp(row['date'])-pd.Timedelta(days=7)]
