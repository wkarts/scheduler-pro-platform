"""HTTPS receiver example: verify HMAC and durably enqueue, not execute business effects.

Run behind HTTPS with Python 3.13, FastAPI and Uvicorn:
  export SCHEDULER_WEBHOOK_SECRET='the complete whsec_... value'
  export SCHEDULER_WEBHOOK_INBOX='/persistent-data/scheduler-inbox.sqlite3'
  uvicorn webhook_receiver:app --host 127.0.0.1 --port 8010

The SQLite inbox MUST be stored in a persistent volume. A separate consumer should
process received rows transactionally/idempotently. This example does not implement
CRM/ERP business rules, authentication for those systems or production TLS termination.
"""
import asyncio
from hashlib import sha256
import hmac
import json
import os
from pathlib import Path
import sqlite3
import time
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request

MAX_BYTES = 65536
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


def store(delivery_id: str, digest: str, body: bytes) -> bool:
    filename = os.environ.get('SCHEDULER_WEBHOOK_INBOX', '')
    if not filename:
        raise RuntimeError('SCHEDULER_WEBHOOK_INBOX must point to persistent storage')
    Path(filename).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(filename, timeout=5) as connection:
        connection.execute('pragma journal_mode=WAL')
        connection.execute('create table if not exists inbox ('
                           'delivery_id text primary key, digest text not null, '
                           'payload text not null, received_at integer not null, '
                           "state text not null default 'received')")
        connection.execute('begin immediate')
        previous = connection.execute('select digest from inbox where delivery_id=?', (delivery_id,)).fetchone()
        if previous:
            if not hmac.compare_digest(previous[0], digest):
                raise ValueError('Delivery identifier was reused with a different body')
            return True
        connection.execute('insert into inbox(delivery_id,digest,payload,received_at) values(?,?,?,?)',
                           (delivery_id,digest,body.decode('utf-8'),int(time.time())))
        return False


@app.post('/webhooks/scheduler')
async def receive(request: Request) -> dict[str, object]:
    secret = os.environ.get('SCHEDULER_WEBHOOK_SECRET', '')
    if not secret:
        raise HTTPException(503, 'Receiver not configured')
    expected_bearer = os.environ.get('SCHEDULER_WEBHOOK_BEARER', '')
    if expected_bearer and not hmac.compare_digest(
        request.headers.get('authorization','').encode(), ('Bearer '+expected_bearer).encode()
    ):
        raise HTTPException(401, 'Invalid authentication')
    timestamp = request.headers.get('x-scheduler-timestamp','')
    delivery_id = request.headers.get('x-scheduler-delivery-id','')
    supplied = request.headers.get('x-scheduler-signature','')
    try:
        UUID(delivery_id)
        if len(timestamp) > 12 or abs(int(time.time())-int(timestamp)) > 300:
            raise ValueError('Timestamp outside acceptance window')
    except ValueError as exc:
        raise HTTPException(401, 'Invalid event authentication') from exc
    body = bytearray()
    try:
        async with asyncio.timeout(10):
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > MAX_BYTES:
                    raise HTTPException(413, 'Event too large')
    except TimeoutError as exc:
        raise HTTPException(408, 'Request timeout') from exc
    expected = 'v1='+hmac.new(secret.encode(), timestamp.encode()+b'.'+delivery_id.encode()+b'.'+body, sha256).hexdigest()
    if not hmac.compare_digest(expected.encode(), supplied.encode()):
        raise HTTPException(401, 'Invalid signature')
    try:
        event = json.loads(body)
        if not isinstance(event, dict) or str(UUID(event['id'])) != request.headers.get('x-scheduler-event-id'):
            raise ValueError('Invalid event ID')
        if event.get('type') != request.headers.get('x-scheduler-event'):
            raise ValueError('Invalid event type')
        replayed = await asyncio.to_thread(store, delivery_id, sha256(body).hexdigest(), bytes(body))
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(400, 'Invalid event or conflicting delivery') from exc
    except (sqlite3.Error, OSError, RuntimeError) as exc:
        raise HTTPException(503, 'Inbox unavailable') from exc
    # Acknowledge only after the inbox transaction commits.
    return {'accepted':True,'duplicate':replayed}
