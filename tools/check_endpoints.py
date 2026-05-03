import requests, json
urls=['http://127.0.0.1:5555/api/analytics','http://127.0.0.1:5555/api/insights','http://127.0.0.1:5555/api/chart/success_rates','http://127.0.0.1:5555/api/emotion/stats']
for u in urls:
    try:
        r=requests.get(u, timeout=5)
        print(u, r.status_code)
        print(json.dumps(r.json(), indent=2)[:1000])
    except Exception as e:
        print(u, 'ERROR', e)
