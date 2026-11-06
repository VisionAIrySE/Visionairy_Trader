"""Refresh only pinned public listing directories; preserve point-in-time identity."""
from datetime import datetime,timezone
import re
import time
import urllib.request
from replay import DataError,NoRedirect
from universe_snapshot import snapshot_bytes
from market_monitor import pack,ScanCancelled

URLS={kind:'https://www.nasdaqtrader.com/dynamic/SymDir/'+filename for kind,filename in
      [('nasdaq','nasdaqlisted.txt'),('other','otherlisted.txt')]}


def current_universe(universe,session_date,now):
    try:
        available=universe['available_at']
        if isinstance(available,bool) or not isinstance(available,(int,float)):return False
        if not 0<=now-available<=86400:return False
        # Receipt UTC date may be the next day during the same US evening.
        # The source creation labels below establish session identity.
        if {s['directory'] for s in universe['sources']}!={'nasdaq','other'}:return False
        for source in universe['sources']:
            match=re.fullmatch(r'File Creation Time: (\d{8})\d{2}:\d{2}',source['provider_creation_label'])
            if not match or datetime.strptime(match[1],'%m%d%Y').date().isoformat()!=session_date:return False
        return True
    except (KeyError,TypeError,ValueError,OverflowError):return False


class UniverseRefresh:
    def __init__(self,opener=None,now=time.time,minimum_rows=1000):
        self.opener=opener or urllib.request.build_opener(NoRedirect())
        self.now=now;self.minimum_rows=minimum_rows

    def refresh(self,store,session_date,cancel_event=None):
        raw={}
        for kind,url in URLS.items():
            if cancel_event is not None and cancel_event.is_set():raise ScanCancelled('Listing refresh cancelled')
            request=urllib.request.Request(url,headers={'User-Agent':'VisionAIry-Market-Research/1.0'},method='GET')
            with self.opener.open(request,timeout=8) as response:
                value=response.read(3000001)
            if len(value)>3000000:raise DataError('Listing source exceeds bounded size')
            raw[kind]=value
        result=snapshot_bytes(raw,int(self.now()))
        if not current_universe(result,session_date,self.now()):raise DataError('Current-session source directories required')
        if any(s['listing_rows']<self.minimum_rows for s in result['sources']):
            raise DataError('Unexpectedly small listing directory requires review')
        if cancel_event is not None and cancel_event.is_set():raise ScanCancelled('Listing refresh cancelled')
        packed=pack(result)
        if len(packed)>450000:raise DataError('Listing snapshot exceeds bounded durable storage')
        store.call('scan_universe_put',{'sha256':result['source_sha256'],'packed_universe':packed})
        return result
