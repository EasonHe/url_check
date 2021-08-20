import  configparser
import  os
import pickle
#from conf import config

#print(config.mail_conf)

# config = configparser.ConfigParser()
# config.read('../conf/test.ini')
# # print(config.sections())
# # url = config.get('hejiating','url')
# # method = config.get('hejiating','method')
# # headers= (eval(config.get('hejiating','headers')))
# # payload = (eval(config.get('hejiating','payload')))
# # oo = config.has_option('hejiating','headers')
# # print(oo)
# # # print(method,url,headers,payload)
# config.add_section('baidu.com')
# config.set('baidu.com','url','http://www.baidu.com')
# config.set('baidu.com','method','get')
# config.set('baidu.com','interval','10')
# print(config.sections())
#
# config.write(open('../conf/test.ini','a'))
# config.write(sys.stdout)
test= {'int':12222222}
print(os.getcwd())
with open("../data/www.baidu.com.pkl","rb" ) as f:
    r=pickle.load(f)
    print(r)
    print('ok')