# -*- coding: utf-8 -*-
from apscheduler.schedulers.blocking import BlockingScheduler
import json

import  requests
from requests import exceptions

def hello():
    print('hello')

def job():
    try:
        headers = {'Content-Type':'application/x-www-form-urlencoded','openid':'YXazYNOQ1UtdFCINYJ5QyrqA2QVu6qWmoi5zBJBAV69P3AeH8EVmGCwCf5IKbzDK'}
        name = 'hejiating'
        payload = {'searchType':0 ,'programType':0, 'productId':0,'content':1122}
        data = {}

        r = requests.post("https://andhejiating.js.chinamobile.com/afuos-wechat-api/vod/search-content",headers=headers,data=payload,timeout=10)
        r.encoding = 'utf-8'
        retime = r.elapsed.microseconds/1000
        statuscode = r.status_code

        data = {'url_name': name,'statuscode':statuscode,'resp_time': retime,'contents':r.text}
        print(data)

    except  exceptions.ConnectTimeout:
        data = {'url_name':name,'erro': 'timeout'}
        print(data)


    except exceptions.TooManyRedirects:
        print (TooManyRedirects)



def get():
    try:
        headers = {'Content-Type':'application/x-www-form-urlencoded','openid':'YXazYNOQ1UtdFCINYJ5QyrqA2QVu6qWmoi5zBJBAV69P3AeH8EVmGCwCf5IKbzDK'}
        name = 'baidu.com'
        payload = {'searchType':0 ,'programType':0, 'productId':0,'content':1122}
        data = {}

        r = requests.get("https://www.baidu.com",data=None,timeout=10,headers=None)
        r.encoding = 'utf-8'
        retime = r.elapsed.microseconds/1000
        statuscode = r.status_code

        data = {'url_name': name,'statuscode':statuscode,'resp_time': retime,'contents':r.text}
        print(data)

    except  exceptions.ConnectTimeout:
        data = {'url_name':name,'erro': 'timeout'}
        print(data)


    except exceptions.TooManyRedirects:
        print (TooManyRedirects)

get()