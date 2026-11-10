"""Check advertised documentation/site links without credentials or mutations.

Local filesystem checks do not establish publication. Local setup services are
listed as untested. Public checks require final HTTP200, including redirects.
"""
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote,urljoin,urlsplit,urlunsplit
import argparse,ipaddress,re,shutil,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[1]
DEFAULT_SITE='https://crashcart.52.202.25.181.sslip.io/'

class HTMLLinks(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.ids=set()
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        for key in ('id','name'):
            if a.get(key):self.ids.add(a[key])
        if a.get('href') and tag in ('a','link'):self.links.append(a['href'])
        if a.get('src') and tag in ('img','script','source','iframe'):self.links.append(a['src'])
    handle_startendtag=handle_starttag

def html(text):
    p=HTMLLinks();p.feed(text);return p

def markdown_links(text):
    # Inline links/images, autolinks, reference destinations and bare URLs.
    # Mask fenced code only for relative links: public command URLs still count.
    urls=[]
    for match in re.finditer(r'!?\[[^\]\n]*\]\(\s*',text):
        start=match.end()
        if text[start:start+1]=='<':
            end=text.find('>',start+1)
            if end>=0:urls.append(text[start+1:end])
            continue
        depth=0;end=start
        while end<len(text):
            char=text[end]
            if char.isspace() or (char==')' and depth==0):break
            if char=='(':depth+=1
            elif char==')':depth-=1
            if char=='\\' and end+1<len(text):end+=1
            end+=1
        if end>start:urls.append(text[start:end])
    for match in re.finditer(r'^\s{0,3}\[[^\]]+\]:\s*(<[^>]+>|\S+)',text,re.M):urls.append(match.group(1).strip('<>'))
    urls.extend(html(text).links)
    urls.extend(re.findall(r'<(https?://[^>\s]+)>',text))
    for match in re.finditer(r'https?://[^\s<>"\']+',text):
        url=match.group(0).rstrip('`.,;:!')
        # Parentheses around markdown destinations are delimiters; balanced URL
        # parentheses remain part of the address.
        while url.endswith(')') and url.count(')')>url.count('('):url=url[:-1]
        if url:urls.append(url)
    return set(unescape(url) for url in urls)

def markdown_ids(text):
    ids=set(html(text).ids);seen={}
    for match in re.finditer(r'^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$',text,re.M):
        heading=re.sub(r'<[^>]*>','',match.group(1))
        heading=re.sub(r'\[([^\]]+)\]\([^)]*\)',r'\1',heading)
        heading=unescape(heading).lower().replace('`','').replace('*','')
        slug=re.sub(r'[^\w\- ]','',heading).replace(' ','-')
        index=seen.get(slug,0);seen[slug]=index+1;ids.add(slug+('-'+str(index) if index else ''))
    return ids

def local_address(url):
    host=(urlsplit(url).hostname or '').lower()
    if host in ('localhost','localhost.localdomain') or host.endswith(('.localhost','.local')):return True
    try:return not ipaddress.ip_address(host).is_global
    except ValueError:return False

def public_url(raw):
    value=urlsplit(raw)
    if value.username or value.password:raise ValueError('Credential-bearing URL rejected')
    if not value.hostname:raise ValueError('HTTP URL lacks a host')
    return urlunsplit((value.scheme,value.netloc,value.path or '/',value.query,''))

class Check:
    def __init__(self,site):
        self.site=site.rstrip('/')+'/';self.urls={};self.fragments={};self.local_only=set();self.other=set();self.failures=[];self.local_count=0;self.local_anchors=0;self.public_anchors=0;self.cache={}
    def fail(self,label,message):self.failures.append((label,message));print('FAIL',label,'—',message,flush=True)
    def add_public(self,url,source):
        if local_address(url):self.local_only.add(url);return
        try:base=public_url(url)
        except ValueError as exc:self.fail(source,str(exc));return
        self.urls.setdefault(base,set()).add(source)
        if urlsplit(url).fragment:self.fragments.setdefault(base,set()).add(unquote(urlsplit(url).fragment))
    def add(self,link,source,document=None,base=None):
        value=urlsplit(link)
        if value.scheme in ('http','https'):self.add_public(link,source);return
        if value.scheme or link.startswith('//'):
            if link.startswith('//') and base:self.add_public(urljoin(base,link),source)
            else:self.other.add(link)
            return
        if base:self.add_public(urljoin(base,link),source);return
        if document is None:return
        target=(document.parent/unquote(value.path)).resolve() if value.path else document
        if not target.is_relative_to(ROOT):self.fail(source,link+' leaves the repository');return
        self.local_count+=1
        if not target.exists():self.fail(source,'missing local file '+str(target.relative_to(ROOT)));return
        if value.fragment:
            fragment=unquote(value.fragment)
            if target.is_file() and target.suffix.lower() in ('.md','.html','.htm'):
                text=target.read_text();ids=markdown_ids(text) if target.suffix.lower()=='.md' else html(text).ids
                self.local_anchors+=1
                if fragment not in ids:self.fail(source,'missing local anchor '+str(target.relative_to(ROOT))+'#'+fragment)
            else:print('ANCHOR_UNTESTED',link,'— non-HTML/Markdown target',flush=True)
    def curl(self,url):
        with tempfile.TemporaryDirectory(prefix='crashcart-link-check-') as folder:
            body=Path(folder)/'body'
            command=['curl','--silent','--show-error','--location','--max-redirs','8','--connect-timeout','5','--max-time','20','--max-filesize','8388608','--proto','=http,https','--proto-redir','=http,https','--output',str(body),'--write-out','%{http_code}\n%{url_effective}\n%{content_type}',url]
            try:
                result=subprocess.run(command,capture_output=True,text=True,timeout=22)
                fields=result.stdout.split('\n');code=fields[0] if fields else '000'
                return {'code':code,'effective':fields[1] if len(fields)>1 else url,'type':fields[2] if len(fields)>2 else '', 'body':body.read_bytes() if body.exists() else b'','error':result.stderr.strip() if result.returncode else ''}
            except subprocess.TimeoutExpired:return {'code':'000','effective':url,'type':'','body':b'','error':'curl process exceeded22-second guard'}
    def fetch(self,urls):
        todo=sorted(set(urls)-self.cache.keys())
        with ThreadPoolExecutor(max_workers=4) as pool:
            for url,result in zip(todo,pool.map(self.curl,todo)):
                self.cache[url]=result
                if result['code']!='200' or result['error']:self.fail(url,'HTTP '+result['code']+(' / '+result['error'] if result['error'] else ''))
                else:print('HTTP200',url+(' → '+result['effective'] if result['effective']!=url else ''),flush=True)
    def run(self):
        for name in ('README.md','docs/DEVPOST.md'):
            document=ROOT/name
            if not document.is_file():self.fail(name,'missing source document');continue
            for link in sorted(markdown_links(document.read_text())):self.add(link,name,document=document)
        pages=[urljoin(self.site,path) for path in ('','product.html','integrations.html','demo.html')]
        for url in pages:self.add_public(url,'hosted public page')
        for path in ('product','example','integrations','healthz'):self.add_public(urljoin(self.site,path),'user-reported route')
        self.fetch(pages)
        for page in pages:
            result=self.cache.get(public_url(page),{})
            if result.get('code')!='200':continue
            if 'html' not in result.get('type','').lower():self.fail(page,'public page is not HTML');continue
            for link in html(result['body'].decode('utf-8',errors='replace')).links:self.add(link,page,base=result['effective'])
        self.fetch(self.urls)
        for url,fragments in sorted(self.fragments.items()):
            result=self.cache.get(url,{})
            if result.get('code')!='200':continue
            if 'html' not in result.get('type','').lower():
                for fragment in sorted(fragments):print('ANCHOR_UNTESTED',url+'#'+fragment,'— non-HTML response',flush=True)
                continue
            ids=html(result['body'].decode('utf-8',errors='replace')).ids
            for fragment in sorted(fragments):
                self.public_anchors+=1
                if fragment not in ids and 'user-content-'+fragment not in ids:self.fail(url+'#'+fragment,'anchor absent from returned HTML')
        for url in sorted(self.local_only):print('LOCAL_ONLY_UNTESTED',url,'— requires a separately running local workspace',flush=True)
        for link in sorted(self.other):print('SCHEME_UNTESTED',link,flush=True)
        passed=sum(r['code']=='200' and not r['error'] for r in self.cache.values())
        print(f'SUMMARY public={len(self.cache)} HTTP200={passed} local_files={self.local_count} local_anchors={self.local_anchors} public_anchors={self.public_anchors} local_only_untested={len(self.local_only)} failures={len(self.failures)}',flush=True)
        print('Filesystem/HTTP checks do not establish sign-in, live integrations, video availability or submission readiness.',flush=True)
        return 1 if self.failures else 0

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--site',default=DEFAULT_SITE,help='Public recorded-site base URL');args=parser.parse_args()
    if not shutil.which('curl'):parser.error('curl is required')
    if urlsplit(args.site).scheme not in ('http','https') or local_address(args.site):parser.error('--site must identify a public HTTP(S) site, not a local setup service')
    try:public_url(args.site)
    except ValueError as exc:parser.error(str(exc))
    return Check(args.site).run()
if __name__=='__main__':raise SystemExit(main())
