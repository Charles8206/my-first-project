import os
import json
import time
import urllib.parse
import requests
import feedparser
from bs4 import BeautifulSoup

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
VALID_MODEL = None  # 테스트를 통과한 확실한 모델을 저장할 변수

CATEGORIES = {
    "대학": "대학 OR 대학교",
    "교육부": "교육부",
    "기재부": "기획재정부 OR 재정경제부 OR 기획예산처"
}

def extract_article_text(url):
    """기사 원문 링크에서 본문 텍스트 추출"""
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

def find_working_model():
    """사용자의 API 키로 확실하게 작동하는 모델을 스스로 찾아냅니다."""
    if not GEMINI_API_KEY:
        return None
    
    # 구글에서 지원하는 대표적인 모델 이름 후보군
    models_to_test = [
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-pro",
        "gemini-1.0-pro",
        "gemini-1.5-pro"
    ]
    
    # 가벼운 테스트 요청
    payload = {"contents": [{"parts": [{"text": "안녕하세요"}]}]}
    
    for model in models_to_test:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        try:
            res = requests.post(url, json=payload, timeout=5)
            if res.status_code == 200:
                return model  # 성공하면 해당 모델 이름을 반환하고 즉시 종료
        except:
            continue
            
    return "gemini-pro" # 만약 모두 실패하더라도 가장 기본 모델로 강제 할당

def summarize_with_gemini(title, content):
    """자동으로 찾은 API 모델을 호출하여 핵심 요약 생성"""
    global VALID_MODEL
    if not GEMINI_API_KEY:
        return "API 키가 설정되지 않았습니다."

    # 크롤러가 시작될 때 최초 1회만 작동하는 모델을 찾아서 고정시킵니다.
    if not VALID_MODEL:
        VALID_MODEL = find_working_model()
        
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{VALID_MODEL}:generateContent?key={GEMINI_API_KEY}"
    
    context = content if len(content) > 100 else title
    prompt = (
        f"기사 제목: {title}\n"
        f"기사 내용: {context}\n\n"
        "지시사항:\n"
        "1. 기사의 핵심 사실을 2~3줄의 간결한 한국어로 요약하세요.\n"
        "2. 서두나 맺음말 없이 바로 내용만 작성하세요."
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 200}
    }

    try:
        response = requests.post(api_url, json=payload, timeout=15)
        if response.status_code == 200:
            return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        else:
            try:
                err_msg = response.json().get("error", {}).get("message", "알 수 없는 오류")
            except:
                err_msg = response.text
            return f"API 오류 ({response.status_code}) - 사용된 모델({VALID_MODEL}): {err_msg}"
    except Exception as e:
        return f"네트워크/시간초과 오류가 발생했습니다."

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
