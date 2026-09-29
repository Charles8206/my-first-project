import os
import json
import time
import urllib.parse
import requests
import feedparser
from bs4 import BeautifulSoup

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
BEST_MODEL = None  # 자동 감지된 모델을 저장할 변수

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

def get_best_model(api_key):
    """현재 API 키로 권한이 있는 가장 최신의 지원 모델을 자동으로 찾아냅니다."""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            models = res.json().get("models", [])
            # generateContent(텍스트 생성)를 지원하는 모델들만 추려냄
            valid_models = [m["name"] for m in models if "generateContent" in m.get("supportedGenerationMethods", [])]
            
            # 구글의 최신 모델 순서대로 우선순위 확인 (2026년 기준 3.5, 3.0 등)
            for pref in ["models/gemini-3.5-flash", "models/gemini-3.1-flash", "models/gemini-3.0-flash", "models/gemini-2.5-flash", "models/gemini-2.0-flash", "models/gemini-1.5-flash-latest"]:
                if pref in valid_models:
                    return pref
            # 우선순위 목록에 없으면 그냥 구글이 허락한 첫 번째 모델을 강제로 사용
            if valid_models:
                return valid_models[0]
    except Exception:
        pass
    return "models/gemini-3.5-flash" # 만약 자동 감지에 실패할 경우 사용할 2026년 최신 기본값

def summarize_with_gemini(title, content):
    """자동으로 찾은 API 모델을 호출하여 핵심 요약 생성"""
    global BEST_MODEL
    if not GEMINI_API_KEY:
        return "API 키가 설정되지 않았거나 인식되지 않았습니다."

    # 최초 1회만 모델을 감지하고 저장해둠 (속도 향상)
    if not BEST_MODEL:
        BEST_MODEL = get_best_model(GEMINI_API_KEY)
        
    api_url = f"https://generativelanguage.googleapis.com/v1beta/{BEST_MODEL}:generateContent?key={GEMINI_API_KEY}"
    
    context = content if len(content) > 100 else title
    prompt = (
        f"기사 제목: {title}\n"
        f"기사 내용: {context}\n\n"
        "지시사항:\n"
        "1. 기사의 가장 핵심적인 사실과 쟁점을 2~3줄의 간결한 한국어로 요약하세요.\n"
        "2. '이 기사는~', '요약하자면' 같은 불필요한 서두 없이 번호나 글머리 기호 없이 바로 작성하세요."
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 200}
    }

    try:
        response = requests.post(api_url, json=payload, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            return res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
        else:
            try:
                err_msg = response.json().get("error", {}).get("message", "알 수 없는 오류")
            except:
                err_msg = response.text
            return f"API 오류 ({response.status_code}) - 감지된 모델({BEST_MODEL}): {err_msg}"
    except Exception as e:
        return "요약 처리 시간 초과 또는 네트워크 오류가 발생했습니다."

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
            
            # API 호출 제한 방지 4.5초 대기 
            time.sleep(4.5)

    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(all_news, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    crawl_news()
