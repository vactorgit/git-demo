import subprocess, sys, re, html, hashlib, os
from html.parser import HTMLParser
class T(HTMLParser):
    def __init__(s):
        super().__init__(); s.out=[]; s.skip=0
    def handle_starttag(s,t,a):
        if t in ("script","style","noscript","svg","nav","footer"): s.skip+=1
        if t in ("p","br","li","h1","h2","h3","h4","tr","div"): s.out.append("\n")
    def handle_endtag(s,t):
        if t in ("script","style","noscript","svg","nav","footer") and s.skip: s.skip-=1
    def handle_data(s,d):
        if not s.skip: s.out.append(d)
def fetch(url, outdir):
    r = subprocess.run(["curl","-sS","-L","--max-time","40","-A","Mozilla/5.0 (compatible; ResearchFetch/1.0)","-w","\n__HTTP__%{http_code}",url],capture_output=True,text=True)
    body = r.stdout
    code = body.rsplit("__HTTP__",1)[-1].strip() if "__HTTP__" in body else "?"
    body = body.rsplit("__HTTP__",1)[0]
    p=T(); p.feed(body)
    text = html.unescape("".join(p.out))
    text = re.sub(r"[ \t]+"," ",text); text = re.sub(r"\n\s*\n+","\n",text)
    name = re.sub(r"[^A-Za-z0-9]+","_",url.split("//",1)[-1])[:80]
    path = os.path.join(outdir, name + ".txt")
    open(path,"w").write(text)
    print(code, len(text), path)
if __name__=="__main__":
    out=sys.argv[1]
    for u in sys.argv[2:]:
        fetch(u,out)
