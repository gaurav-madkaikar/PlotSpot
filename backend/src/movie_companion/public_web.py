"""Read-only public HTTPS with DNS pinning, TLS identity and redirect checks."""
import asyncio
from dataclasses import dataclass
import ipaddress
import re
import socket
from time import monotonic
from urllib.parse import urljoin,urlsplit,urlunsplit
from urllib.robotparser import RobotFileParser
import httpx

AGENT='PlotSpotSourceReader/1.0'
class SourceRejected(ValueError):pass

def public_url(value):
    if not isinstance(value,str) or not 1<=len(value)<=2000 or any(c.isspace() or ord(c)<32 for c in value):raise SourceRejected('Invalid URL')
    try:
        parts=urlsplit(value);host=(parts.hostname or '').rstrip('.').encode('idna').decode('ascii').lower()
        if parts.scheme!='https' or parts.username is not None or parts.password is not None or parts.port not in (None,443):raise SourceRejected('HTTPS without credentials is required')
    except (ValueError,UnicodeError):raise SourceRejected('Invalid URL') from None
    if (not re.fullmatch(r'[a-z0-9.-]{1,253}',host) or '.' not in host
            or host.endswith(('.local','.internal','.localhost','.onion')) or '..' in host):raise SourceRejected('Invalid public host')
    try:ipaddress.ip_address(host)
    except ValueError:pass
    else:raise SourceRejected('Literal IP targets are forbidden')
    return urlunsplit(('https',host,parts.path or '/',parts.query,''))

async def public_addresses(host):
    async with asyncio.timeout(5):
        records=await asyncio.to_thread(socket.getaddrinfo,host,443,type=socket.SOCK_STREAM)
    addresses=list(dict.fromkeys(record[4][0] for record in records))
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise SourceRejected('Private or non-global DNS address')
    return addresses

@dataclass(frozen=True)
class WebRead:
    url: str
    body: bytes
    content_type: str

class PublicWebReader:
    def __init__(self,*,resolver=public_addresses,client_factory=httpx.AsyncClient,deadline=25,robots=True):
        self.resolver=resolver;self.client_factory=client_factory;self.deadline=deadline;self.robots=robots
        self.slots=asyncio.Semaphore(3);self.robot_cache={}

    async def _robots_allowed(self,url):
        origin=f'https://{urlsplit(url).netloc}'
        cached=self.robot_cache.get(origin)
        if cached is None or cached[0]<=monotonic():
            parser=RobotFileParser()
            try:
                read=await self._read(origin+'/robots.txt',maximum=64000,redirects=1)
                parser.parse(read.body.decode('utf-8',errors='replace').splitlines())
            except httpx.HTTPStatusError as error:
                if error.response.status_code not in (404,410):raise SourceRejected('Robots policy unavailable') from None
                parser.parse([])
            self.robot_cache[origin]=(monotonic()+3600,parser)
            if len(self.robot_cache)>100:self.robot_cache.pop(next(iter(self.robot_cache)))
        else:parser=cached[1]
        if not parser.can_fetch(AGENT,url):raise SourceRejected('Robots policy disallows this read')

    async def _read(self,url,*,maximum,redirects=3,check_robots=False):
        for step in range(redirects+1):
            url=public_url(url);host=urlsplit(url).hostname
            if check_robots:await self._robots_allowed(url)
            addresses=await self.resolver(host)
            if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):raise SourceRejected('Unsafe DNS resolution')
            # A client per hop prevents sharing a TLS connection between different
            # original hosts on one IP. Cookies/proxies/auth are never forwarded.
            async with self.client_factory(timeout=10,trust_env=False,follow_redirects=False,verify=True,
                                           limits=httpx.Limits(max_connections=1)) as client:
                target=httpx.URL(url).copy_with(host=addresses[0])
                request=client.build_request('GET',target,headers={'Host':host,'User-Agent':AGENT,'Accept':'text/html,text/plain','Accept-Encoding':'identity'})
                request.extensions['sni_hostname']=host
                response=await client.send(request,stream=True)
                try:
                    if response.status_code in (301,302,303,307,308):
                        if step==redirects or not response.headers.get('location'):raise SourceRejected('Redirect budget exceeded')
                        url=public_url(urljoin(url,response.headers['location']));continue
                    response.raise_for_status()
                    mime=response.headers.get('content-type','').split(';')[0].strip().lower()
                    if mime not in ('text/html','text/plain'):raise SourceRejected('Unsupported source type')
                    if response.headers.get('content-encoding','identity').lower() not in ('','identity'):raise SourceRejected('Unexpected encoded body')
                    length=response.headers.get('content-length')
                    if length and (not length.isdigit() or int(length)>maximum):raise SourceRejected('Source byte budget exceeded')
                    body=bytearray()
                    async for chunk in response.aiter_raw():
                        body.extend(chunk)
                        if len(body)>maximum:raise SourceRejected('Source byte budget exceeded')
                    return WebRead(url,bytes(body),mime)
                finally:await response.aclose()
        raise SourceRejected('Redirect budget exceeded')

    async def fetch(self,url,*,maximum=1500000):
        async with self.slots,asyncio.timeout(self.deadline):
            return await self._read(public_url(url),maximum=maximum,check_robots=self.robots)
