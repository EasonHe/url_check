import configparser
import smtplib
import  os
from  flask import request

from email.mime.text import MIMEText
def mailconf(tos,subject,content):
    try:
        config = configparser.ConfigParser()
        config.read('conf/mail.ini')
        smtp_server = config.get('section1', 'smtp_server')
        smtp_port = config.get('section1', 'smtp_port')
        smtp_username = config.get('section1', 'smtp_username')
        smtp_password = str(config.get('section1', 'smtp_password'))
        fromuser=config.get('section1', 'fromuser')
        print(content,subject,tos)

        body = "{},<br>".format(content)
        body += "<p>来自测试环境的cherker:include some wrong.</p>"
        msg = MIMEText(body, "html",'utf-8')
        msg["Subject"] = subject
        msg["From"] = fromuser
        msg["To"] = ",".join(tos)
        msg["Accept-Language"] = "zh-CN"
        msg["Accept-Charset"] = "ISO-8859-1,utf-8"
        s = smtplib.SMTP_SSL(smtp_server,smtp_port);
        s.set_debuglevel(1)
        s.login(smtp_username, smtp_password)
        s.sendmail(smtp_username,tos, msg.as_string())

        return True
    except  ValueError as e:
        print(e)
        return  False
    #raise Exception('send fail')

class geturl:
    def sender():
        tos = request.values.get('tos').split(',')
        subject = request.values.get('subject')
        content = request.values.get('content')
        print(content)

        if  True == mailconf(tos, subject, content):
            return   'success' + '\n'
        else:
            return  'false'


