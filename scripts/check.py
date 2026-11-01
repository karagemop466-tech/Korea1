from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote
class Check(HTMLParser):
 def __init__(self): super().__init__(); self.errors=[]; self.row=False; self.body=False; self.link=False
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='tbody': self.body=True
  if tag=='tr' and self.body: self.row=True; self.link=False
  if tag=='a':
   href=a.get('href','')
   if self.row and href.startswith('https://'): self.link=True
   if href and not urlsplit(href).scheme and not href.startswith('#') and not Path(unquote(urlsplit(href).path)).exists(): self.errors.append('missing link '+href)
  if tag=='link' and a.get('href') and not Path(a['href']).exists(): self.errors.append('missing asset '+a['href'])
 def handle_endtag(self,tag):
  if tag=='tr' and self.row:
   if not self.link: self.errors.append('table row lacks external source')
   self.row=False
  if tag=='tbody': self.body=False
errors=[]
for p in Path('.').glob('*.html'):
 c=Check(); c.feed(p.read_text()); errors += [f'{p}: {e}' for e in c.errors]
if errors: raise SystemExit('\n'.join(errors))
print('Local links, assets and table source links OK')
