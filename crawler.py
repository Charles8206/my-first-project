import os
import json
import time
import urllib.parse
import requests
import feedparser
from bs4 import BeautifulSoup
import google.generativeai as genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
AI_MODEL = None

CATEGORIES = {
    "대학": "대학 OR 대학교",
    "교육부": "교육부",
    "기재부": "기획재정부 OR 재정경제부 OR 기획예산처"
}

def extract_article_text(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        res = requests.get(url, headers=headers, timeout=5, allow_redirects=True)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, "html.html" if "html.html" in res.text else "html.parser")
            for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
                tag.extract()
            paragraphs = soup.find_all("p")
            text = " ".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 30])
            return text[:1500] 
    except Exception:
        pass
    return ""

def summarize_with_gemini(title, content):
    global AI_MODEL
    if not GEMINI_API_KEY:
        return "API 키가 설정되지 않았습니다."

    if AI_MODEL is None:
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            AI_MODEL = genai.GenerativeModel("gemini-3.8-flash")
        except Exception as e:
            return f"AI 초기화 실패: {str(e)}"

    context = content if len(content) > 100 else title
    prompt = (
        f"기사 제목: {title}\n"
        f"기사 내용: {context}\n\n"
        "지시사항:\n"
        "1. 기사의 핵심 사실을 2~3줄의 간결한 한국어로 요약하세요.\n"
        "2. 서두나 맺음말 없이 바로 내용만 작성하세요."
    )

    try:
        response = AI_MODEL.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"요약 에러 발생: {str(e)}"

def crawl_news():
    all_news = []
    
    for category_name, query in CATEGORIES.items():
        encoded_query = urllib.parse.quote(query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        feed = feedparser.parse(rss_url)
        
        entries = feed.entries[:8]
        
        for entry in entries:
            title = entry.title
            link = entry.link
            
            # ★ 구글의 지저분한 영문 날짜를 깔끔한 연-월-일 형식으로 변환
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

            body_text = extract_article_text(link)
            ai_summary = summarize_with_gemini(clean_title, body_text)

            all_news.append({
                "title": clean_title,
                "link": link,
                "source": source,
                "date": pub_date,
                "category": category_name,
                "summary": ai_summary
            })
            
            # 1분에 5건 속도 제한 우회용 대기 시간
            time.sleep(15)

    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(all_news, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    crawl_news()
