#!/usr/bin/env python3
"""Free-tier static RSS collector. Optional Gemini scoring; never requires paid services."""
import hashlib, html, json, os, re, sys, time
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent
FEEDS=ROOT/'feeds.json'
OUTPUT=ROOT/'articles.json'
KEYWORDS={'after effects':15,'motion design':14,'motion graphics':14,'animation':7,'keyframe':9,'expression':8,'script':7,'plugin':7,'adobe':5,'kinetic typography':10,'ui animation':10,'compositing':5,'ai video':8,'video generation':8,'generative ai':6,'animation workflow':8,'ae ':4}
REJECT={'hiring','job opening','giveaway','looking for work','for hire'}

def clean(text):
    text=re.sub(r'<[^>]+>',' ',str(text or ''))
    return re.sub(r'\s+',' ',html.unescape(text)).strip()[:800]

def child_text(el, names):
    for c in el.iter():
        if c is el: continue
        tag=c.tag.split('}')[-1].lower()
        if tag in names and c.text and c.text.strip():return c.text.strip()
    return ''

def fetch_bytes(url):
    req=Request(url,headers={'User-Agent':'MotionSignalReader/1.0 (+RSS research; personal project)','Accept':'application/rss+xml,application/atom+xml,application/xml,text/xml,*/*'})
    with urlopen(req,timeout=14) as resp:
        if resp.status != 200:raise ValueError('status '+str(resp.status))
        content=resp.read(8000000)
    return content

def fetch(url):
    return ET.fromstring(fetch_bytes(url))

def feed_entries(feed):
    if feed.get('type') != 'adobe_news':
        entries = list(parse_entries(fetch(feed['url'])))
        if not entries:
            raise ValueError('配信から記事を読み取れませんでした')
        return entries
    data = json.loads(fetch_bytes(feed['url']))
    cards = data.get('cards')
    if not isinstance(cards, list) or not cards:
        raise ValueError('Adobeニュース一覧の形式が変わりました')
    entries = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    for card in cards:
        area = card.get('contentArea', {})
        date = iso_date(card.get('cardDate', ''))
        url = area.get('url', '')
        if not date or datetime.fromisoformat(date) < cutoff: continue
        if urlparse(url).hostname != 'news.adobe.com': continue
        if not re.search(r'/news/\d{4}/\d{2}/', urlparse(url).path): continue
        entries.append((area.get('title', ''), url, area.get('description', ''), date))
    if not entries:
        raise ValueError('Adobe公式の直近90日のニュースを取得できませんでした')
    return entries

def parse_entries(root):
    for entry in root.iter():
        if entry.tag.split('}')[-1].lower() not in ('item','entry'): continue
        title=child_text(entry,{'title'})
        link=child_text(entry,{'link'})
        if not link:
            for c in entry:
                if c.tag.split('}')[-1]=='link' and c.attrib.get('href') and c.attrib.get('rel','alternate')=='alternate':
                    link=c.attrib['href'];break
        desc=child_text(entry,{'summary','description','content','encoded'})
        published=child_text(entry,{'published','updated','pubdate','date'})
        if title and link and urlparse(link).scheme in ('https','http'):
            yield title,link,desc,published

def iso_date(value):
    try:
        dt=parsedate_to_datetime(value)
        return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()
    except Exception:pass
    try:return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc).isoformat()
    except Exception:return None

STUDIOS = ('buck', 'ordinary folk', 'giant ant', 'manvsmachine', 'man vs machine', 'tendril', 'nuke', 'animade', 'odd fellows', 'oddfellows', 'hornet', 'psyop', 'framestore', 'the mill', 'mill+', 'nexus', 'nørlum', 'future deluxe', 'territory studio', 'panoply', 'builders club', 'blinkink', 'aardman', 'black kite', 'axis studios', 'woodblock', 'onesal', 'view', 'bleed', 'golden wolf')
QUESTION = re.compile(r"\?|help|issue|error|problem|crash|not working|won.t|can.t|how (do|can|to)|why |beginner|roast|feedback|judge|hiring|job opening|for hire|giveaway|ethics|エラー|不具合|質問|助け|できない", re.I)
TOOLS = re.compile(r"script|plugin|plug-in|extension|preset|tool|release|update|new feature|what.s new|beta|launch|introduc|スクリプト|プラグイン|新機能|アップデート", re.I)
VIDEO = re.compile(r"after effects|\bae\b|premiere|davinci|resolve|cinema 4d|blender|animation|motion|composit|vfx|video|redshift|octane", re.I)
ANNOUNCEMENT = re.compile(r"releas|launch|introduc|new feature|what.s new|now available|free (script|plugin|tool)|made (a|an|my) (script|plugin|tool)|built (a|an) (script|plugin|tool)", re.I)

def select_item(title, summary, source):
    text = title + ' ' + summary
    if source == 'Adobe公式ニュース':
        if re.search(r'partnership|strategic alliance|financial results|revenue', title, re.I): return None
        if re.search(r'after effects|premiere|firefly|creative cloud|substance|creative agent', text, re.I) and re.search(r'new|launch|introduc|expand|release|transform|update|announc', text, re.I):
            return ('release', 'ai' if 'firefly' in title.lower() else 'tools', 85, 'Adobe公式の新機能・提供条件を確認し、制作環境への導入を検討できます。')
        return None
    if source == 'CG Channel — Releases':
        if VIDEO.search(text) and re.search(r'releas|launch|unveil|new feature|now available|free again', title, re.I):
            return ('release', 'tools', 80, '制作ソフトの新バージョン・新機能を確認できます。対応環境は提供元で確認してください。')
        return None
    if QUESTION.search(title): return None
    if source == 'Stash — Studio Films':
        if any(re.search(r'(?<!\w)' + re.escape(name) + r'(?!\w)', text, re.I) for name in STUDIOS):
            return ('studio', 'design', 78, 'スタジオ作品の演出・質感・モーション表現を制作の参考にできます。')
        return None
    if source == 'Toolfarm — Tools & Updates' and TOOLS.search(text) and VIDEO.search(text):
        return ('tool', 'tools', 75, '紹介されているツールや新機能が制作工程の短縮に役立つか確認できます。')
    if source == 'Reddit After Effects' and TOOLS.search(title) and ANNOUNCEMENT.search(title):
        return ('tool', 'tools', 65, '公開された制作ツール・新機能を確認できます。対応バージョンと提供元を確認してください。')
    return None

def score_item(title, summary, category):
    return 0 if QUESTION.search(title) else 65

def build(feeds,previous):
    seen={}
    active_sources={f['name'] for f in feeds}
    for a in previous:
        if not isinstance(a,dict) or not a.get('id'): continue
        if a.get('source') not in active_sources: continue
        choice=select_item(a.get('title',''),a.get('summary',''),a.get('source',''))
        if choice:
            a.update(kind=choice[0],category=choice[1],score=choice[2],use_case=choice[3])
            seen[a['id']]=a
    sources=[]
    for feed in feeds:
        name=feed['name'];url=feed['url'];count=0
        try:
            entries=feed_entries(feed)
            for title,link,desc,date in entries:
                title=clean(title);desc=clean(desc);date=iso_date(date)
                if not date: continue
                aid=hashlib.sha256(link.encode()).hexdigest()[:20]
                choice=select_item(title,desc,name)
                if not choice:continue
                kind,category,sc,use_case=choice
                article={'id':aid,'title':title,'summary':desc[:350] or '詳細は元の記事をご確認ください。','url':link,'source':name,'category':category,'kind':kind,'published':date,'score':sc,'evaluation':'keyword_heuristic','use_case':use_case,'caution':'キーワードによる自動評価です。内容の正確性や再現性は未検証です。','demo':False}
                if aid in seen:
                    old=seen[aid]
                    if old.get('title') == title and old.get('summary') == article['summary']:
                        for field in ('title_ja','summary_ja','translation'):
                            if field in old: article[field]=old[field]
                    if old.get('evaluation')=='gemini':
                        for field in ('score','evaluation','use_case','caution','summary'):article[field]=old[field]
                seen[aid]=article;count+=1
            sources.append({'name':name,'status':'ok','items':count,'scanned':len(entries)})
            print(f'OK {name}: {count}')
        except Exception as e:
            sources.append({'name':name,'status':'error','items':0,'reason':str(e)[:120]})
            print(f'WARN {name}: {e}',file=sys.stderr)
        time.sleep(.25)
    articles=sorted(seen.values(),key=lambda a:a.get('published',''),reverse=True)[:250]
    return articles,sources

def gemini_enrich(items):
    key=os.environ.get('GEMINI_API_KEY','').strip()
    if not key: return 0
    model=os.environ.get('GEMINI_MODEL','gemini-2.5-flash-lite')
    # Limited to 8 new articles per run to stay conservative on free quotas.
    candidates=[a for a in items if a.get('evaluation')!='gemini'][:8]
    if not candidates:return 0
    endpoint='https://generativelanguage.googleapis.com/v1beta/models/'+model+':generateContent'
    prompt=('あなたは映像制作情報の編集者。記事のタイトルと概要の情報だけを使い、元記事を検証したと偽らず、制作実用性と新規性を0～100で保守的に評価。各記事に日本語の短い活用方法(use_case)、注意点(caution)、日本語での概要(summary)を返す。曖昧な内容は過大評価しない。JSON配列で id,score,use_case,caution,summary のみ出力。情報:\n'+json.dumps([{k:a[k] for k in ('id','title','summary','category','source')} for a in candidates],ensure_ascii=False))
    payload={'contents':[{'parts':[{'text':prompt}]}],'generationConfig':{'responseMimeType':'application/json','temperature':0.1}}
    try:
        req=Request(endpoint,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','x-goog-api-key':key},method='POST')
        with urlopen(req,timeout=35) as response:res=json.load(response)
        raw=res['candidates'][0]['content']['parts'][0]['text']
        rows=json.loads(raw)
        if not isinstance(rows,list):raise ValueError('invalid response')
        byid={a['id']:a for a in candidates};done=0
        for row in rows:
            if not isinstance(row,dict) or row.get('id') not in byid:continue
            a=byid[row['id']]
            a['score']=max(0,min(100,int(row.get('score',a['score']))))
            for f in ('use_case','caution','summary'):
                val=clean(row.get(f,''))
                if val:a[f]=val[:350]
            a['evaluation']='gemini';done+=1
        return done
    except Exception as e:
        print('WARN Gemini skipped:',str(e)[:200],file=sys.stderr)
        return 0

def main():
    feeds=json.loads(FEEDS.read_text())
    previous=[]
    if OUTPUT.exists():
        try:previous=json.loads(OUTPUT.read_text()).get('articles',[])
        except (ValueError,TypeError):pass
    articles,sources=build(feeds,previous)
    if not any(s['status']=='ok' for s in sources):
        raise RuntimeError('すべての収集元が失敗しました。前回のデータを保持します。')
    enriched=gemini_enrich(articles)
    data={'generated_at':datetime.now(timezone.utc).isoformat(),'articles':articles,'sources':sources,'mode':'rss_gemini' if enriched else 'rss_only','notice':'公式ニュース・公開RSSの抜粋と自動評価です。一次情報を必ず確認してください。'}
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print('Saved:',len(articles),'AI evaluated:',enriched,'successful sources:',sum(s['status']=='ok' for s in sources))
    # Transient failures must not wipe already collected records; no fatal on individual feeds.
if __name__=='__main__':main()
