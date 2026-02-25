import requests
from conf import config


def ding_sender(title="OMG", msg="message"):
    print("title is:", title)
    print("message is:", msg)
    message = "## " + title + "  \n" + msg
    headers = {"Content-Type": "application/json"}

    mydata = {"msgtype": "markdown", "markdown": {"title": title, "text": message}}
    try:
        r = requests.post(
            "{}access_token={}".format(config.dingding_url, config.access_token),
            headers=headers,
            json=mydata,
            timeout=10,
        )
        r.encoding = "utf-8"
        content = r.text
        print("钉钉发送结果:", r.status_code, content)
    except Exception as e:
        print("钉钉发送失败:", e)
    return "dingding return code status {}".format("success")


def ding_report(title="OMG", msg="message"):
    """发送汇总报告到钉钉"""
    print("Report title is:", title)
    print("Report message is:", msg)
    message = "## " + title + "  \n" + msg
    headers = {"Content-Type": "application/json"}

    mydata = {"msgtype": "markdown", "markdown": {"title": title, "text": message}}
    r = requests.post(
        "{}access_token={}".format(config.dingding_url, config.access_token),
        headers=headers,
        json=mydata,
    )
    r.encoding = "utf-8"
    print("Report sent:", mydata)
    return "dingding report status {}".format("success")
