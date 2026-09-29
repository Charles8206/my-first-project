import os
import json
import time
import urllib.parse
import requests
import feedparser
from bs4 import BeautifulSoup

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

CATEGORIES = {
    "대학": "대학 OR 대학교",
    "교육부": "교육부",
    "기재부": "기획재정부 OR 재정경제부 OR 기획예산처"
}

def extract_article_text(url):
    """기사 원문 링크에서 본문 텍스트 일부 추출"""
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
    """Gemini 1.5 Flash-8B(가장 가볍고 빠른 무료 모델) 직접 호출"""
    if not GEMINI_API_KEY:
        return "API 키가 인식되지 않았습니다."

    # 구글 공식 권장 빠르고 가벼운 모델 강제 지정
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-8b:generateContent?key={GEMINI_API_KEY}"
    
    context = content if len(content) > 100 else title
    prompt = (
        f"기사 제목: {title}\n"
        f"기사 내용: {context}\n\n"
        "지시사항:\n"
        "1. 기사의 핵심 사실을 2~3줄의 간결한 한국어로 요약하세요.\n"
        "2. 서두나 맺음말, 기호 없이 내용만 바로 작성하세요."
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 200}
    }

    try:
        # 응답 대기 시간을 20초로 넉넉하게 연장
        response = requests.post(api_url, json=payload, timeout=20)
        if response.status_code == 200:
            res_json = response.json()
            return res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
        else:
            try:
                err_msg = response.json().get("error", {}).get("message", "알 수 없는 오류")
            except:
                err_msg = response.text
            return f"API 오류 ({response.status_code}): {err_msg}"
    except Exception as e:
        return f"요약 처리 중 오류 발생: {str(e)}"

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
            
            # API 제한 방지 대기
            time.sleep(4.5)

    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(all_news, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    crawl_news()
