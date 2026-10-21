"""Bound private JSON bodies and forbid caching, including validation failures."""
import re
from fastapi.responses import JSONResponse

def member_path(path):
    return path.startswith(('/api/auth/','/api/me/','/api/community/','/api/search')) or bool(re.match(r'^/api/movies/[^/]+/(?:features|facts|quiz|questions|threads|preparation)(?:/|$)',path))

class AccountBoundary:
    def __init__(self,app):self.app=app

    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or not member_path(scope['path']):
            return await self.app(scope,receive,send)
        async def private_send(message):
            if message['type']=='http.response.start':
                headers=[(k,v) for k,v in message['headers'] if k.lower() not in (b'cache-control',b'vary')]
                message={**message,'headers':headers+[(b'cache-control',b'no-store'),(b'vary',b'Cookie')]}
            await send(message)
        if scope['method'] not in ('GET','HEAD','OPTIONS'):
            headers=dict(scope['headers'])
            if headers.get(b'content-type',b'').split(b';')[0].strip().lower()!=b'application/json':
                return await JSONResponse({'detail':'Send a JSON request.'},status_code=415)(scope,receive,private_send)
            length=headers.get(b'content-length',b'0')
            if not length.isdigit() or int(length)>131072:
                return await JSONResponse({'detail':'Request exceeds the size limit.'},status_code=413)(scope,receive,private_send)
            messages=[];total=0
            while True:
                message=await receive()
                if message['type']=='http.disconnect':return
                total+=len(message.get('body',b''))
                if total>131072:
                    return await JSONResponse({'detail':'Request exceeds the size limit.'},status_code=413)(scope,receive,private_send)
                messages.append(message)
                if not message.get('more_body',False):break
            async def replay():return messages.pop(0) if messages else await receive()
            return await self.app(scope,replay,private_send)
        await self.app(scope,receive,private_send)
