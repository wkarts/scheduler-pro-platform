"""Send one event using an independently issued incoming credential (standard library only).

Set SCHEDULER_WEBHOOK_URL and SCHEDULER_WEBHOOK_SECRET in the environment.
Pass --event-id unchanged on retries. No credentials are printed.
"""
import argparse
from hashlib import sha256
import hmac
import json
import os
import ssl
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler, ProxyHandler
from uuid import uuid4


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--event-id', required=True)
    parser.add_argument('--event-type', default='example.changed')
    parser.add_argument('--mode', choices=['hmac','bearer'], default='hmac')
    args = parser.parse_args()
    url = os.environ.get('SCHEDULER_WEBHOOK_URL', '')
    secret = os.environ.get('SCHEDULER_WEBHOOK_SECRET', '')
    target = urlsplit(url)
    if target.scheme != 'https' or not target.hostname or target.username or target.password or target.query or not secret:
        parser.error('Configure URL HTTPS sem credenciais/query e o segredo nas variáveis de ambiente.')
    body = json.dumps({'id':args.event_id,'type':args.event_type,'data':{'reference':'example'}}, ensure_ascii=False, separators=(',',':')).encode()
    headers = {'Content-Type':'application/json'}
    if args.mode == 'bearer':
        headers['Authorization'] = 'Bearer ' + secret
    else:
        stamp = str(int(time.time()))
        delivery = str(uuid4())
        signed = stamp.encode()+b'.'+delivery.encode()+b'.'+body
        headers.update({'X-Scheduler-Timestamp':stamp,'X-Scheduler-Delivery-Id':delivery,'X-Scheduler-Signature':'v1='+hmac.new(secret.encode(),signed,sha256).hexdigest()})
    opener=build_opener(NoRedirect(),ProxyHandler({}),HTTPSHandler(context=ssl.create_default_context()))
    try:
        with opener.open(Request(url, data=body, headers=headers, method='POST'), timeout=15) as response:
            print(response.status, response.read(16384).decode('utf-8'))
    except HTTPError as error:
        print('HTTP',error.code,'Consulte a documentação e reutilize o mesmo id nos reenvios.')
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
