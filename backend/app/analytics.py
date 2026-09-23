from datetime import date, timedelta

LABELS = {'visits': ('방문 횟수', '회'), 'pageviews': ('조회수', '건')}

def summarize(rows):
    result=[]
    for metric,(label,unit) in LABELS.items():
        subset=sorted([r for r in rows if r['metric']==metric],key=lambda r:r['date'])
        if not subset:
            continue
        values=[r['value'] for r in subset]
        end=date.fromisoformat(subset[-1]['date'])
        start=date.fromisoformat(subset[0]['date'])
        by_date={r['date']:r['value'] for r in subset}
        recent_dates=[(end-timedelta(days=i)).isoformat() for i in range(7)]
        prior_dates=[(end-timedelta(days=i)).isoformat() for i in range(7,14)]
        complete=all(d in by_date for d in recent_dates+prior_dates)
        recent=sum(by_date[d] for d in recent_dates) if complete else None
        prior=sum(by_date[d] for d in prior_dates) if complete else None
        trend='데이터 부족' if not complete else ('증가' if recent>prior else '감소' if recent<prior else '유지')
        result.append({'metric':metric,'label':label,'unit':unit,'count':len(subset),'start':start.isoformat(),'end':end.isoformat(),'total':sum(values),'average':round(sum(values)/len(values),2),'min':min(values),'max':max(values),'peak_dates':[r['date'] for r in subset if r['value']==max(values)],'missing_days':(end-start).days+1-len(by_date),'recent7':recent,'previous7':prior,'trend':trend,'change_percent':round((recent-prior)/prior*100,1) if complete and prior else None,'points':[{'date':r['date'],'value':r['value']} for r in subset]})
    return {'count':len(rows),'unique_days':len({r['date'] for r in rows}),'series':result,'notes':'두 지표를 서로 합산하지 않습니다. 추세는 각 지표의 마지막 관측일 기준 최근 7일과 이전 7일을 비교합니다. 누락일은 0으로 채우지 않습니다.'}
