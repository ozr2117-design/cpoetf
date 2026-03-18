import requests
def fetch_hist():
    url = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh515880,day,,,300,qfq"
    res = requests.get(url)
    print(res.json()['data']['sh515880']['qfqday'][-5:])
    
def fetch_sina_rt():
    url = "http://hq.sinajs.cn/list=sh515880"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Referer": "http://finance.sina.com.cn"
    }
    res = requests.get(url, headers=headers)
    print(res.text)

if __name__ == '__main__':
    fetch_hist()
    fetch_sina_rt()
