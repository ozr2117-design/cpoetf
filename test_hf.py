import requests

url = "http://hq.sinajs.cn/list=hf_CL"
headers = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "http://finance.sina.com.cn"
}
res = requests.get(url, headers=headers)
print(res.text)
