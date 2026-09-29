# 매일 실행: python crawler.py  -> news.json 생성 -> dashboard.html 이 자동으로 불러옴
import feedparser, json, urllib.parse, datetime
TOPICS = {"대학교":"대학 OR 대학교 OR 글로컬대학",
          "교육부":"교육부",
          "기재부(재정경제부·기획예산처)":"재정경제부 OR 기획예산처 OR 기획재정부"}
out = {"updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "items": []}
for cat, q in TOPICS.items():
    url = "https://news.google.com/rss/search?q=" + urllib.parse.quote(q + " when:1d") + "&hl=ko&gl=KR&ceid=KR:ko"
    for e in feedparser.parse(url).entries[:15]:
        out["items"].append({"cat":cat,"title":e.title,"link":e.link,
                             "src":e.get("source",{}).get("title",""),"date":e.get("published","")})
json.dump(out, open("news.json","w",encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(out["items"]), "건 저장")
