#config.py
import  sys,os
mail_conf = 'conf/mail.ini'#邮件程序使用的文件
task_conf = 'conf/task.ini'#任务文件
#告警设置
send_to =  ['hewei@raiyee.com']
history_datat_day = 3


dingding_url = "https://oapi.dingtalk.com/robot/send?"
access_token = "6f3c39a23f1ce5ee22e888d9b1e61df18a61be7305ade92d179cfdfedda45e"
#task_conf 文件使用说明
#
# 通过post 方法添加动态任务，
# 参数又有如下
# timout（超时时间） headers（请求头） cookies payload（数据），interval (url检查的间隔时间)
#监控参数
# {'add_job':  {"section": 'www.baidu.com', 'url':"http://www.baidu.com",'method': "get","interval" : 5}}

#{'add_job':  {"section": 'www.baidu.com', 'url':"http://www.baidu.com",'method': "get","interval":5,"threshold":{'stat_code': 200,'delay':[300,2],'math_str': '百度' }    }}
