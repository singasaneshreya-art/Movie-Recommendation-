from flask import Flask, request, jsonify, render_template, session
from recommender import recommender
from data.movies import MOVIES
import os

app = Flask(__name__)
app.secret_key = "nexmovie_secret_2024"


# ── ROUTES ───────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/movies")
def get_movies():
    """Return all movies (lightweight — no description)."""
    light = []
    for m in MOVIES:
        light.append({
            "id":      m["id"],
            "title":   m["title"],
            "year":    m["year"],
            "genres":  m["genres"],
            "rating":  m["rating"],
            "director":m["director"],
            "poster":  m["poster"],
        })
    return jsonify(light)


@app.route("/api/movie/<int:movie_id>")
def get_movie(movie_id):
    """Return full movie details."""
    m = recommender.get_movie_by_id(movie_id)
    if not m:
        return jsonify({"error": "Movie not found"}), 404
    return jsonify(m)


@app.route("/api/recommend/content", methods=["POST"])
def recommend_content():
    """Content-based: recommend by movie similarity."""
    data     = request.get_json(silent=True) or {}
    movie_id = data.get("movie_id")
    top_n    = data.get("top_n", 6)
    if not movie_id:
        return jsonify({"error": "movie_id required"}), 400
    results = recommender.recommend_by_movie(int(movie_id), top_n)
    return jsonify({
        "method":       "Content-Based Filtering",
        "technique":    "TF-IDF + Cosine Similarity",
        "based_on":     recommender.get_movie_by_id(movie_id),
        "results":      results,
        "count":        len(results)
    })


@app.route("/api/recommend/collaborative", methods=["POST"])
def recommend_collaborative():
    """Collaborative filtering: recommend by user rating pattern."""
    data    = request.get_json(silent=True) or {}
    ratings = data.get("ratings", {})     # {movie_id: rating}
    top_n   = data.get("top_n", 6)
    if not ratings:
        return jsonify({"error": "ratings dict required"}), 400
    # Convert keys to int
    ratings_int = {int(k): int(v) for k, v in ratings.items()}
    results = recommender.recommend_by_ratings(ratings_int, top_n)
    return jsonify({
        "method":    "Collaborative Filtering",
        "technique": "User-Based Cosine Similarity",
        "results":   results,
        "count":     len(results)
    })


@app.route("/api/recommend/genre", methods=["POST"])
def recommend_genre():
    """Genre-based: filter by preferred genres."""
    data   = request.get_json(silent=True) or {}
    genres = data.get("genres", [])
    top_n  = data.get("top_n", 6)
    exclude = data.get("exclude_ids", [])
    if not genres:
        return jsonify({"error": "genres list required"}), 400
    results = recommender.recommend_by_genres(genres, top_n, exclude)
    return jsonify({
        "method":    "Genre-Based Filtering",
        "technique": "Genre Overlap + Rating Score",
        "results":   results,
        "count":     len(results)
    })


@app.route("/api/recommend/hybrid", methods=["POST"])
def recommend_hybrid():
    """Hybrid: blend content + collaborative."""
    data     = request.get_json(silent=True) or {}
    movie_id = data.get("movie_id")
    ratings  = data.get("ratings", {})
    top_n    = data.get("top_n", 6)
    if not movie_id or not ratings:
        return jsonify({"error": "movie_id and ratings required"}), 400
    ratings_int = {int(k): int(v) for k, v in ratings.items()}
    results = recommender.recommend_hybrid(int(movie_id), ratings_int, top_n)
    return jsonify({
        "method":    "Hybrid Recommendation",
        "technique": "Content-Based (60%) + Collaborative (40%)",
        "based_on":  recommender.get_movie_by_id(movie_id),
        "results":   results,
        "count":     len(results)
    })


@app.route("/api/search")
def search():
    """Search movies by title, director, cast, genre."""
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
    results = recommender.search(q)
    return jsonify(results)


@app.route("/api/genres")
def get_genres():
    return jsonify(recommender.get_all_genres())


@app.route("/api/top_rated")
def top_rated():
    n = int(request.args.get("n", 8))
    sorted_movies = sorted(MOVIES, key=lambda m: m["rating"], reverse=True)[:n]
    return jsonify(sorted_movies)


if __name__ == "__main__":
    print("\n🎬 NexMovie Recommendation System")
    print("   Running at: http://127.0.0.1:5000\n")
    app.run(debug=True, port=5000)
