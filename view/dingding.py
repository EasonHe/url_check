import requests
from conf import config
def ding_sender(title="OMG",msg="meassage"):
    print("title is:",title)
    print("message is:", msg)
    message = "## " + title +"\n" +"### " + msg
    headers = {'Content-Type': 'application/json'}

    mydata = {"msgtype": "markdown", "markdown": {"title":title, "text": message}}
    r = requests.post("{}access_token={}".format(config.dingding_url,config.access_token),headers=headers,json=mydata)
    r.encoding = 'utf-8'
    content  = r.text
    print(mydata)
    return  "dingding return code status {}".format('success')


