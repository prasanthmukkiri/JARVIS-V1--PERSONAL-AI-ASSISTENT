"""
News fetcher action - Get current news from multiple sources
Uses NewsAPI and other sources for trending news
"""
import requests
import json
from datetime import datetime, timedelta


def get_india_news():
    """Fetch trending news from India"""
    try:
        # Using NewsData.io free API (alternative to NewsAPI)
        url = "https://newsdata.io/api/1/news"
        params = {
            "country": "in",
            "language": "en",
            "sort": "recency",
            "apikey": "demo"  # Replace with actual API key
        }
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get("results", [])[:5]
    except Exception:
        pass
    return []


def get_south_india_news():
    """Fetch news from South India (TN, KA, KL, AP, TS)"""
    try:
        # Using search query for South India
        url = "https://newsdata.io/api/1/news"
        params = {
            "q": "Tamil Nadu OR Karnataka OR Kerala OR Andhra OR Telangana",
            "country": "in",
            "language": "en",
            "sort": "recency",
            "apikey": "demo"
        }
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get("results", [])[:5]
    except Exception:
        pass
    return []


def get_international_news():
    """Fetch international trending news"""
    try:
        url = "https://newsdata.io/api/1/news"
        params = {
            "language": "en",
            "sort": "recency",
            "apikey": "demo"
        }
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get("results", [])[:5]
    except Exception:
        pass
    return []


def format_news_article(article):
    """Format a single news article"""
    return {
        "title": article.get("title", "N/A"),
        "description": article.get("description", ""),
        "link": article.get("link", "#"),
        "source": article.get("source_id", "Unknown"),
        "pubDate": article.get("pubDate", ""),
        "image": article.get("image_url", "")
    }


def fetch_all_news():
    """Fetch all news and format for display"""
    return {
        "india": [format_news_article(a) for a in get_india_news()],
        "south_india": [format_news_article(a) for a in get_south_india_news()],
        "international": [format_news_article(a) for a in get_international_news()],
        "timestamp": datetime.now().isoformat()
    }


def news_fetcher(parameters=None, player=None):
    """Main action handler for news fetching"""
    try:
        news_data = fetch_all_news()
        return json.dumps(news_data)
    except Exception as e:
        return json.dumps({"error": str(e), "news": {}})
