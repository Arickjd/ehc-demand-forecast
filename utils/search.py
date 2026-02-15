import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re

class GoogleSearch:
    def __init__(self, api_key, cx):
        self.api_key = api_key
        self.cx = cx

    def parse_snippet_date(self, snippet):
        """
        Extrai a data do snippet e retorna (data, snippet_sem_data)
        """
        if not snippet:
            return None, snippet

        # Datas absolutas (Ex: Sep 21, 2025)
        abs_date_match = re.search(r'([A-Z][a-z]{2} \d{1,2}, \d{4})', snippet)
        if abs_date_match:
            try:
                dt = datetime.strptime(abs_date_match.group(1), '%b %d, %Y')
                snippet_clean = snippet.replace(abs_date_match.group(1), '').strip()
                return dt.strftime('%Y-%m-%d'), snippet_clean
            except:
                pass

        # Datas relativas (Ex: "2 days ago", "3 weeks ago")
        rel_match = re.search(r'(\d+)\s+(day|week|month|year)s?\s+ago', snippet)
        if rel_match:
            num = int(rel_match.group(1))
            unit = rel_match.group(2)
            dt = datetime.now()
            if unit == 'day':
                dt -= timedelta(days=num)
            elif unit == 'week':
                dt -= timedelta(weeks=num)
            elif unit == 'month':
                dt -= timedelta(days=num*30)
            elif unit == 'year':
                dt -= timedelta(days=num*365)
            snippet_clean = snippet.replace(rel_match.group(0), '').strip()
            return dt.strftime('%Y-%m-%d'), snippet_clean

        return None, snippet

    def search(self, query, site=None, after=None, before=None, num_results=10):
        final_query = query
        if site:
            if type(site) == list:
                site = f"({" OR ".join(f"site:{s}" for s in site)}) AND "
            else:
                site = f"site:{site} "
            final_query = f"{site} {final_query}"
        if after:
            final_query += f" after:{after}"
        if before:
            final_query += f" before:{before}"

        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": self.api_key,
            "cx": self.cx,
            "q": final_query,
            "num": num_results
        }

        response = requests.get(url, params=params)
        data = response.json()
        results = []

        for item in data.get("items", []):
            link = item.get("link")
            snippet = item.get("snippet")
            date = item.get("pagemap", {}).get("metatags", [{}])[0].get("article:published_time")

            # Extrair título completo via BeautifulSoup
            try:
                page = requests.get(link, timeout=5)
                soup = BeautifulSoup(page.content, "html.parser")
                full_title = soup.title.string.strip() if soup.title else item.get("title")
            except Exception:
                full_title = item.get("title")

            # Extrair data do snippet e remover do texto
            if not date:
                date, snippet = self.parse_snippet_date(snippet)

            results.append({
                "title": full_title,
                "link": link,
                "snippet": re.sub(r'^\.{3,}\s*', '', snippet),
                "date": date
            })

        return results