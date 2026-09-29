import os
import json
import time
import urllib.parse
import requests
import feedparser
from bs4 import BeautifulSoup

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# 부처 및 대학별 검색 키워드 (분야당 최신 8건 수집)
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
            # 불필요한 태그 제거
            for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
                tag.extract()
            paragraphs = soup.find_all("p")
            text = " ".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 30])
            return text[:1500] # 상위 1,500자 추출
    except Exception:
        pass
    return ""

def summarize_with_gemini(title, content):
    """Gemini API를 호출하여 기사 핵심 2~3줄 요약 생성"""
    if not GEMINI_API_KEY:
        return "API 키가 설정되지 않아 요약을 생성할 수 없습니다."

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    context = content if len(content) > 100 else title
    prompt = (
        f"기사 제목: {title}\n"
        f"기사 내용: {context}\n\n"
        "지시사항:\n"
        "1. 기사의 가장 핵심적인 사실과 쟁점을 2~3줄의 간결한 한국어로 요약하세요.\n"
        "2. '이 기사는~', '요약하자면' 같은 불필요한 서두 없이 본문 내용만 번호나 글머리 기호 없이 바로 작성하세요."
    )

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 200
        }
    }

    try:
        response = requests.post(api_url, json=payload, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            summary = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
            return summary
        else:
            return "본문 요약 생성 중 일시적인 오류가 발생했습니다."
    except Exception as e:
        return "요약 처리 시간 초과 또는 네트워크 오류가 발생했습니다."

def crawl_news():
    all_news = []
    
    for category_name, query in CATEGORIES.items():
        encoded_query = urllib.parse.quote(query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        feed = feedparser.parse(rss_url)
        
        # 카테고리당 최대 8건 수집 (API 호출 속도 및 할당량 고려)
        entries = feed.entries[:8]
        
        for entry in entries:
            title = entry.title
            link = entry.link
            pub_date = entry.get("published", "")
            
            # 출처 분리
            source = "출처 모름"
            clean_title = title
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                clean_title = parts[0]
                source = parts[1]

            # 본문 추출 및 AI 요약
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
            
            # Gemini 무료 API 호출 간격 유지 (안정적인 실행)
            time.sleep(1.2)

    # news.json 파일 저장
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(all_news, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    crawl_news()
