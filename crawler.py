import json
import urllib.parse
import requests
import feedparser
import time

# 요청하신 4개의 카테고리로 명칭 및 순서 변경
CATEGORIES = {
    "동국대학교 NEWS": "동국대학교 OR 동국대",
    "대학교 NEWS": "대학 OR 대학교",
    "교육부 NEWS": "교육부",
    "기재부 NEWS": "기획재정부 OR 재정경제부 OR 기획예산처"
}

def crawl_news():
    all_news = []
    
    for category_name, query in CATEGORIES.items():
        encoded_query = urllib.parse.quote(query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        feed = feedparser.parse(rss_url)
        
        # AI 요약이 없으므로 속도 제한 없이 8건 수집
        entries = feed.entries[:8]
        
        for entry in entries:
            title = entry.title
            link = entry.link
            
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                pub_date = time.strftime("%Y-%m-%d", entry.published_parsed)
            else:
                pub_date = entry.get("published", "")
            
            source = "출처 모름"
            clean_title = title
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                clean_title = parts[0]
                source = parts[1]

            all_news.append({
                "title": clean_title,
                "link": link,
                "source": source,
                "date": pub_date,
                "category": category_name
            })

    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(all_news, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    crawl_news()
