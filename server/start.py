import os
import uvicorn

if __name__=='__main__':
    uvicorn.run('server.app:app',host='0.0.0.0',port=int(os.getenv('PORT','8018')),
                access_log=False,proxy_headers=True,forwarded_allow_ips=os.getenv('EDGE_TRUSTED_PROXY_IPS','127.0.0.1'))
