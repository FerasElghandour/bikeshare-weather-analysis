"""Offline example using the public implementation; see README for evidence scope."""
import sys,json,pathlib,os
repo=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(repo));sys.path.insert(0,str(repo/'src'));os.chdir(repo)
import pandas as pd
from mobility_weather.analysis import prepare_daily
rentals=pd.DataFrame([{'dteday':f'2011-01-{d:02}','hr':h,'cnt':3,'casual':1,'registered':2,'workingday':1} for d in [1,2] for h in range(24)]).drop(index=0)
weather=pd.DataFrame({'date':pd.date_range('2011-01-01',periods=2),'tmax_c':[10.,11.],'tmin_c':[1.,2.],'precip_mm':[0.,1.]})
daily,audit=prepare_daily(rentals,weather)
print(json.dumps({"fixture":"generated two days with one missing hour","audit":audit,"retained_daily_rentals":daily.rentals.tolist()}))
