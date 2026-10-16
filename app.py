"""
Netflix CineHub - Flask Backend
Fetches live data from TMDB API with Netflix-style categories, search, and details.
Falls back to built-in mock data if the API key is missing or unreachable.
"""

import os
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv

# Load variables from .env
load_dotenv()

app = Flask(__name__)

TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
TMDB_BASE    = "https://api.themoviedb.org/3"
TMDB_IMG     = "https://image.tmdb.org/t/p"

# HTTP session with robust retry & keep-alive
session = requests.Session()
retries = Retry(total=3, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
})

# In-memory category cache: { "timestamp": float, "categories": list, "all_movies": list }
_CACHE = {"timestamp": 0, "categories": [], "all_movies": []}
CACHE_TTL = 900  # 15 minutes

# Built-in fallback mock data
MOCK_MOVIES = [
    {"id":1,"title":"Inception","year":2010,"rating":8.8,"genre":["Sci-Fi","Action","Thriller"],"director":"Christopher Nolan","duration":"148 min","poster":"https://image.tmdb.org/t/p/w500/9gk7adHYeDvHkCSEqAvQNLV5Uge.jpg","backdrop":"https://image.tmdb.org/t/p/original/s3TBrRGB1iav7gFOCNx3H31MoES.jpg","overview":"A thief who steals corporate secrets through dream-sharing technology is given the inverse task of planting an idea into the mind of a C.E.O.","trailer_query":"Inception+2010+official+trailer"},
    {"id":2,"title":"Interstellar","year":2014,"rating":8.6,"genre":["Sci-Fi","Adventure","Drama"],"director":"Christopher Nolan","duration":"169 min","poster":"https://image.tmdb.org/t/p/w500/gEU2QniE6E77NI6lCU6MxlNBvIx.jpg","backdrop":"https://image.tmdb.org/t/p/original/xJHokMbljvjADYdit5fK5VQsXEG.jpg","overview":"A team of explorers travel through a wormhole in space in an attempt to ensure humanity's survival.","trailer_query":"Interstellar+2014+official+trailer"},
    {"id":3,"title":"The Dark Knight","year":2008,"rating":9.0,"genre":["Action","Crime","Drama"],"director":"Christopher Nolan","duration":"152 min","poster":"https://image.tmdb.org/t/p/w500/qJ2tW6WMUDux911r6m7haRef0WH.jpg","backdrop":"https://image.tmdb.org/t/p/original/nMKdUUepR0i5zn0y1T4CejdrycO.jpg","overview":"When the menace known as the Joker wreaks havoc on Gotham, Batman must accept one of the greatest psychological and physical tests.","trailer_query":"The+Dark+Knight+2008+official+trailer"},
    {"id":4,"title":"Spider-Man: Into the Spider-Verse","year":2018,"rating":8.4,"genre":["Animation","Action","Adventure"],"director":"Bob Persichetti, Peter Ramsey","duration":"117 min","poster":"https://image.tmdb.org/t/p/w500/iiZZdoQBEYBv6id8su7ImL0oCbD.jpg","backdrop":"https://image.tmdb.org/t/p/original/7du3Z1JFYKBsRMH4NP8I9fGb3i4.jpg","overview":"Teen Miles Morales becomes Spider-Man of his universe and must join five spider-powered individuals from other dimensions.","trailer_query":"Spider-Man+Into+the+Spider-Verse+2018+official+trailer"},
    {"id":5,"title":"Dune: Part Two","year":2024,"rating":8.5,"genre":["Sci-Fi","Adventure","Drama"],"director":"Denis Villeneuve","duration":"166 min","poster":"https://image.tmdb.org/t/p/w500/1pdfLvkbY9ohJlCjQH2CZjjYVvJ.jpg","backdrop":"https://image.tmdb.org/t/p/original/xOMo8BRK7PfcJv9JCnx7s5hj0PX.jpg","overview":"Paul Atreides unites with Chani and the Fremen while seeking revenge against the conspirators who destroyed his family.","trailer_query":"Dune+Part+Two+2024+official+trailer"},
    {"id":6,"title":"Oppenheimer","year":2023,"rating":8.3,"genre":["Biography","Drama","History"],"director":"Christopher Nolan","duration":"180 min","poster":"https://image.tmdb.org/t/p/w500/8Gxv8gSFCU0XGDykEGv7zR1n2ua.jpg","backdrop":"https://image.tmdb.org/t/p/original/rLb2cwF3Pazuxaj0sRXQ037tGI1.jpg","overview":"The story of American scientist J. Robert Oppenheimer and his role in the development of the atomic bomb.","trailer_query":"Oppenheimer+2023+official+trailer"},
    {"id":7,"title":"The Shawshank Redemption","year":1994,"rating":9.3,"genre":["Drama"],"director":"Frank Darabont","duration":"142 min","poster":"https://image.tmdb.org/t/p/w500/lyQBXzOQSuE59IsHyhrp0qIiPAz.jpg","backdrop":"https://image.tmdb.org/t/p/original/kXfqcdQKsToO0OUXHcrrNCHDBzO.jpg","overview":"Two convicts form a friendship, seeking consolation and redemption through basic human goodness over several years.","trailer_query":"The+Shawshank+Redemption+1994+official+trailer"},
    {"id":8,"title":"Parasite","year":2019,"rating":8.5,"genre":["Drama","Thriller"],"director":"Bong Joon-ho","duration":"132 min","poster":"https://image.tmdb.org/t/p/w500/7IiTTgloJzvGI1TAYymCfbfl3vT.jpg","backdrop":"https://image.tmdb.org/t/p/original/ApiBzeaa95TNYliSbQ8pJv4Nalx.jpg","overview":"Greed and class discrimination threaten the newly formed symbiotic relationship between the wealthy Park family and the destitute Kim clan.","trailer_query":"Parasite+2019+official+trailer"},
    {"id":9,"title":"Everything Everywhere All at Once","year":2022,"rating":7.8,"genre":["Action","Comedy","Sci-Fi"],"director":"Daniels","duration":"139 min","poster":"https://image.tmdb.org/t/p/w500/w3LxiVYdWWRvEVdn5RYq6jIqkb1.jpg","backdrop":"https://image.tmdb.org/t/p/original/ss0Os3uWJfQAENILHZUdX8Tt1OC.jpg","overview":"An aging Chinese immigrant is swept up in an insane adventure in which she alone can save the world by exploring other universes.","trailer_query":"Everything+Everywhere+All+at+Once+2022+official+trailer"},
    {"id":10,"title":"The Matrix","year":1999,"rating":8.7,"genre":["Action","Sci-Fi"],"director":"Wachowski Sisters","duration":"136 min","poster":"https://image.tmdb.org/t/p/w500/f89U3ADr1oiB1s9GkdPOEpXUk5H.jpg","backdrop":"https://image.tmdb.org/t/p/original/fNG7i7RqMErkcqhohV2a6cV1Ehy.jpg","overview":"When a stranger leads computer hacker Neo to a forbidding underworld, he discovers the life he knows is an elaborate deception.","trailer_query":"The+Matrix+1999+official+trailer"},
    {"id":11,"title":"Avengers: Endgame","year":2019,"rating":8.4,"genre":["Action","Adventure","Drama"],"director":"Russo Brothers","duration":"181 min","poster":"https://image.tmdb.org/t/p/w500/or06FN3Dka5tukK1e9sl16pB3iy.jpg","backdrop":"https://image.tmdb.org/t/p/original/7RyHsO4yDXtBv1zUU3mTpHeQ0d5.jpg","overview":"After the devastating events of Infinity War, the Avengers assemble once more to undo Thanos actions.","trailer_query":"Avengers+Endgame+2019+official+trailer"},
    {"id":12,"title":"Pulp Fiction","year":1994,"rating":8.9,"genre":["Crime","Drama"],"director":"Quentin Tarantino","duration":"154 min","poster":"https://image.tmdb.org/t/p/w500/d5iIlFn5s0ImszYzBPb8JPIfbXD.jpg","backdrop":"https://image.tmdb.org/t/p/original/suaEOtk1N1sgg2MTM7oZd2cfVp3.jpg","overview":"The lives of two mob hitmen, a boxer, a gangster and his wife intertwine in four tales of violence and redemption.","trailer_query":"Pulp+Fiction+1994+official+trailer"},
]

# Genre mapping
GENRE_MAP = {
    28: "Action", 12: "Adventure", 16: "Animation", 35: "Comedy",
    80: "Crime", 99: "Documentary", 18: "Drama", 10751: "Family",
    14: "Fantasy", 36: "History", 27: "Horror", 10402: "Music",
    9648: "Mystery", 10749: "Romance", 878: "Sci-Fi", 10770: "TV Movie",
    53: "Thriller", 10752: "War", 37: "Western", 10759: "Action & Adventure",
    10762: "Kids", 10765: "Sci-Fi & Fantasy"
}

# Netflix Category row definitions
CATEGORY_DEFS = [
    {"id": "trending", "title": "🔥 Trending This Week", "path": "/trending/movie/week", "badge": "Hot"},
    {"id": "top_rated", "title": "⭐ All-Time Masterpieces", "path": "/movie/top_rated", "badge": "Critically Acclaimed"},
    {"id": "now_playing", "title": "🎬 Now In Theatres", "path": "/movie/now_playing", "badge": "New"},
    {"id": "action", "title": "💥 High-Octane Action & Adventure", "path": "/discover/movie?with_genres=28&sort_by=popularity.desc", "badge": "Adrenaline"},
    {"id": "scifi", "title": "🚀 Sci-Fi & Cyberpunk", "path": "/discover/movie?with_genres=878&sort_by=popularity.desc", "badge": "Mind Bending"},
    {"id": "horror", "title": "👻 Thrillers & Chilling Horror", "path": "/discover/movie?with_genres=27&sort_by=popularity.desc", "badge": "Edge of Seat"},
    {"id": "animation", "title": "✨ Spectacular Animation", "path": "/discover/movie?with_genres=16&sort_by=popularity.desc", "badge": "Visuals"},
    {"id": "comedy", "title": "🍿 Comedy Hits & Feel-Good", "path": "/discover/movie?with_genres=35&sort_by=popularity.desc", "badge": "Must Watch"},
]


def _tmdb_get(path: str, params: dict = None) -> dict | None:
    """Make a GET request to the TMDB API using persistent session."""
    if not TMDB_API_KEY or TMDB_API_KEY == "your_tmdb_api_key_here":
        return None
    try:
        base_params = {"api_key": TMDB_API_KEY, "language": "en-US"}
        if params:
            base_params.update(params)
        url = f"{TMDB_BASE}{path}"
        resp = session.get(url, params=base_params, timeout=7)
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None


def _shape_movie(raw: dict, fetch_details: bool = False) -> dict:
    """Convert a raw TMDB movie object into our app's standard shape."""
    movie_id = raw.get("id", 0)

    director = "Director info available in details"
    duration = "N/A"

    if fetch_details:
        credits_data = _tmdb_get(f"/movie/{movie_id}/credits") or {}
        crew = credits_data.get("crew", [])
        directors = [p["name"] for p in crew if p.get("job") == "Director"]
        if directors:
            director = ", ".join(directors)

        details = _tmdb_get(f"/movie/{movie_id}") or {}
        runtime = details.get("runtime") or 0
        if runtime:
            duration = f"{runtime} min"

    title    = raw.get("title", "Unknown")
    year_str = raw.get("release_date", "")[:4]
    year     = int(year_str) if year_str.isdigit() else 0
    rating   = round(raw.get("vote_average", 0), 1)
    overview = raw.get("overview", "")
    poster   = f"{TMDB_IMG}/w500{raw['poster_path']}" if raw.get("poster_path") else ""
    backdrop = f"{TMDB_IMG}/original{raw['backdrop_path']}" if raw.get("backdrop_path") else (poster or "")

    genre_ids = raw.get("genre_ids", [])
    genres = [GENRE_MAP.get(gid, "Other") for gid in genre_ids] or ["Feature"]

    trailer_query = "+".join((title + " " + year_str + " official trailer").split())

    return {
        "id":            movie_id,
        "title":         title,
        "year":          year,
        "rating":        rating,
        "genre":         genres,
        "director":      director,
        "duration":      duration,
        "poster":        poster,
        "backdrop":      backdrop,
        "overview":      overview,
        "trailer_query": trailer_query,
        "source":        "tmdb",
    }


def _get_all_categories():
    """Fetch all category rows from TMDB (with in-memory cache)."""
    now = time.time()
    if _CACHE["categories"] and (now - _CACHE["timestamp"] < CACHE_TTL):
        return _CACHE["categories"], _CACHE["all_movies"]

    key_ok = bool(TMDB_API_KEY and TMDB_API_KEY != "your_tmdb_api_key_here")
    if not key_ok:
        # Mock categories
        cats = [
            {"id": "trending", "title": "🔥 Trending Movies", "badge": "Popular", "movies": MOCK_MOVIES[:6]},
            {"id": "classics", "title": "⭐ Critically Acclaimed", "badge": "Masterpieces", "movies": MOCK_MOVIES[6:12]},
        ]
        return cats, MOCK_MOVIES

    categories = []
    seen_ids = set()
    all_movies = []

    for cat_def in CATEGORY_DEFS:
        path = cat_def["path"]
        params = {}
        if "?" in path:
            path_part, query_part = path.split("?", 1)
            path = path_part
            for pair in query_part.split("&"):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    params[k] = v

        data = _tmdb_get(path, params)
        raw_results = data.get("results", []) if data else []
        shaped_movies = []
        for r in raw_results:
            if r.get("poster_path"):
                m = _shape_movie(r, fetch_details=False)
                shaped_movies.append(m)
                if m["id"] not in seen_ids:
                    seen_ids.add(m["id"])
                    all_movies.append(m)

        if shaped_movies:
            categories.append({
                "id": cat_def["id"],
                "title": cat_def["title"],
                "badge": cat_def.get("badge", ""),
                "movies": shaped_movies
            })

    if categories:
        _CACHE["timestamp"] = now
        _CACHE["categories"] = categories
        _CACHE["all_movies"] = all_movies
        return categories, all_movies

    return [], []


# ── Routes ──

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/categories")
def get_categories():
    """Return all Netflix category rows with 140+ movies."""
    categories, all_movies = _get_all_categories()
    return jsonify({
        "success": True,
        "count_categories": len(categories),
        "total_movies": len(all_movies),
        "categories": categories,
        "source": "tmdb" if (TMDB_API_KEY and TMDB_API_KEY != "your_tmdb_api_key_here") else "mock"
    })


@app.route("/api/movies")
def get_movies():
    """Search or return all movies flat."""
    q = request.args.get("q", "").strip()
    genre = request.args.get("genre", "").strip()

    # If search query provided and live TMDB key available:
    if q and TMDB_API_KEY and TMDB_API_KEY != "your_tmdb_api_key_here":
        data = _tmdb_get("/search/movie", {"query": q, "include_adult": "false"})
        if data and data.get("results"):
            movies = [_shape_movie(m, fetch_details=False) for m in data["results"] if m.get("poster_path")]
            return jsonify({"success": True, "count": len(movies), "movies": movies, "source": "tmdb"})

    # Otherwise return from loaded catalogue
    _, all_movies = _get_all_categories()
    if not all_movies:
        all_movies = MOCK_MOVIES

    results = all_movies
    if q:
        ql = q.lower()
        results = [
            m for m in results
            if ql in m["title"].lower()
            or ql in m.get("director", "").lower()
            or any(ql in g.lower() for g in m.get("genre", []))
        ]

    if genre:
        results = [m for m in results if genre in m.get("genre", [])]

    return jsonify({"success": True, "count": len(results), "movies": results, "source": "tmdb" if TMDB_API_KEY else "mock"})


@app.route("/api/movies/<int:movie_id>")
def get_movie(movie_id):
    """Return full movie detail including director and runtime."""
    if TMDB_API_KEY and TMDB_API_KEY != "your_tmdb_api_key_here":
        raw = _tmdb_get(f"/movie/{movie_id}")
        if raw and raw.get("id"):
            raw["genre_ids"] = [g["id"] for g in raw.get("genres", [])]
            shaped = _shape_movie(raw, fetch_details=True)
            return jsonify({"success": True, "movie": shaped, "source": "tmdb"})

    movie = next((m for m in MOCK_MOVIES if m["id"] == movie_id), None)
    if movie is None:
        return jsonify({"success": False, "error": "Movie not found"}), 404
    return jsonify({"success": True, "movie": movie, "source": "mock"})


@app.route("/api/status")
def api_status():
    """Health-check endpoint."""
    key_set = bool(TMDB_API_KEY and TMDB_API_KEY != "your_tmdb_api_key_here")
    return jsonify({
        "tmdb_key_configured": key_set,
        "data_source": "tmdb" if key_set else "mock",
    })


if __name__ == "__main__":
    key_ok = TMDB_API_KEY and TMDB_API_KEY != "your_tmdb_api_key_here"
    print("\n[*] Netflix CineHub is running!")
    print(f"   Data source : {'TMDB Live API (140+ movies in Netflix rows)' if key_ok else 'Mock data'}")
    print("   Open        : http://127.0.0.1:5000\n")
    app.run(debug=True, host="0.0.0.0", port=5000)