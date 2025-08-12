from flask import Flask, request, jsonify, render_template, g
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)
CORS(app)

@app.route("/")
def index():
    return render_template("index.html")

def parse_quality(quality_str: str) -> int:
    """Parses a quality string (e.g., '1080p') into an integer."""
    if not quality_str:
        return 0
    match = re.search(r'(\d+)', quality_str)
    if match:
        return int(match.group(1))
    return 0

@app.route("/api/search")
def search_movies():
    """Step 1: Search for movies on MovieLinkHub"""
    query = request.args.get('query')
    if not query:
        return jsonify({"error": "Query parameter is required"}), 400

    try:
        search_url = f"https://movielinkhub.fun/?s={query}"
        response = requests.get(search_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        results = []
        for item in soup.select('.result-item'):
            title_tag = item.select_one('.title a')
            if not title_tag:
                continue

            result = {
                "title": title_tag.get_text(strip=True),
                "url": title_tag['href'],
                "year": item.select_one('.year').get_text(strip=True) if item.select_one('.year') else "N/A",
                "type": item.select_one('.movies').get_text(strip=True) if item.select_one('.movies') else "Unknown",
                "description": item.select_one('.contenido p').get_text(strip=True) if item.select_one('.contenido p') else "",
                "thumbnail": item.select_one('img')['src'] if item.select_one('img') else ""
            }
            results.append(result)

        return jsonify({"query": query, "results": results})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/download-links")
def get_download_links():
    """Step 2: Get download links from movie page, selecting the best quality."""
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "URL parameter is required"}), 400

    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        download_blocks = soup.select("tr[id^='link-']")
        best_link = None
        max_quality = -1
        selected_block_html = ""

        for block in download_blocks:
            quality_tag = block.select_one('.qua')
            quality_text = quality_tag.get_text(strip=True) if quality_tag else ""
            current_quality = parse_quality(quality_text)

            if current_quality > max_quality:
                link_tag = block.select_one("a[href*='/links/']")
                if link_tag:
                    max_quality = current_quality
                    best_link = link_tag['href']
                    selected_block_html = str(block)

        if not best_link:
            button = soup.select_one("button.downbtn")
            if button:
                link_tag = button.find_parent('a')
                if link_tag and link_tag.has_attr('href'):
                    best_link = link_tag['href']

        if not best_link:
            return jsonify({"error": "Download link not found on the page."}), 404

        download_page_url = best_link
        download_response = requests.get(download_page_url)
        download_response.raise_for_status()

        final_url_match = re.search(r'https?://linkedmoviehub\.top[^\s\'"]+', download_response.text)
        if not final_url_match:
            return jsonify({"error": "Final download page URL not found on intermediate page."}), 404
        
        final_url = final_url_match.group(0)

        quality_info = {
            "quality": "Unknown",
            "size": "Unknown",
            "language": "Unknown"
        }
        
        if selected_block_html:
            quality_match = re.search(r'class=[\'"]qua[\'"]>([^<]+)', selected_block_html)
            size_match = re.search(r'class=[\'"]siz[\'"]>\[([^\]]+)', selected_block_html)
            lang_match = re.search(r'class=[\'"]lan[\'"]>\(([^\)]+)', selected_block_html)

            if quality_match:
                quality_info["quality"] = quality_match.group(1).strip()
            if size_match:
                quality_info["size"] = size_match.group(1).strip()
            if lang_match:
                quality_info["language"] = lang_match.group(1).strip()

        return jsonify({
            "intermediate_page_url": download_page_url,
            "final_page_url": final_url,
            "selected_quality_info": quality_info
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/final-links")
def get_final_download_links():
    """Step 3: Get all download options from the final page"""
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "URL parameter is required"}), 400

    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        quality_sections = {}
        for quality_div in soup.select('div.quality'):
            quality = quality_div.find('h2').get_text(strip=True)
            links = []
            for link in quality_div.find_next('center').select('a.down-btn'):
                provider = link.get_text(strip=True)
                url = link['href']
                links.append({
                    "provider": provider,
                    "url": url
                })
            if links:
                quality_sections[quality] = links

        if not quality_sections:
            return jsonify({"error": "No download links found"}), 404

        return jsonify(quality_sections)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/src")
def search_and_get_all_links():
    """Combined endpoint to search for a movie and get all download links."""
    query = request.args.get('query')
    if not query:
        return jsonify({"error": "Query parameter is required"}), 400

    try:
        # Use a context to pass the query to the search_movies function
        with app.test_request_context(f'/?query={query}'):
            g.query = query
            search_response = search_movies()
        
        if isinstance(search_response, tuple): # Error occurred
            return search_response
        search_results = search_response.get_json().get("results", [])

        if not search_results:
            return jsonify({
                "ok": True,
                "developer": "Tofazzal Hossain",
                "results": []
            })

        final_results = []
        for movie in search_results:
            movie_url = movie.get("url")
            if not movie_url:
                continue

            try:
                with app.test_request_context(f'/?url={movie_url}'):
                    download_page_info_response = get_download_links()
                
                if isinstance(download_page_info_response, tuple):
                    continue
                download_page_info = download_page_info_response.get_json()
                final_page_url = download_page_info.get("final_page_url")

                if not final_page_url:
                    continue

                with app.test_request_context(f'/?url={final_page_url}'):
                    final_links_response = get_final_download_links()

                if isinstance(final_links_response, tuple):
                    continue
                final_links_by_quality = final_links_response.get_json()

                download_links_formatted = []
                for quality, links_list in final_links_by_quality.items():
                    # The structure from get_final_download_links is already a list of dicts
                    urls = [link["url"] for link in links_list]
                    download_links_formatted.append({
                        "quality": quality,
                        "links": urls
                    })
                
                final_results.append({
                    "title": movie.get("title"),
                    "year": movie.get("year"),
                    "type": movie.get("type"),
                    "poster": movie.get("thumbnail"),
                    "downloadLink": download_links_formatted
                })

            except Exception as e:
                print(f"Failed to process movie '{movie.get('title')}': {e}")
                continue
        
        return jsonify({
            "ok": True,
            "developer": "Mahir Labib",
            "results": final_results
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
