import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data.movies import MOVIES, USER_RATINGS


# ── BUILD FEATURE MATRIX ─────────────────────────────────────────
def build_content_features(movies):
    """
    Combine genres, director, cast, description into a single
    weighted text blob per movie, then TF-IDF vectorize.
    """
    docs = []
    for m in movies:
        genre_str   = " ".join(m["genres"]) * 3          # weight genres 3x
        director    = m["director"].replace(" ", "_") * 2 # weight director 2x
        cast_str    = " ".join(c.replace(" ", "_") for c in m["cast"])
        desc        = m["description"]
        year_bucket = f"era_{m['year'] // 10 * 10}"       # decade grouping
        doc = f"{genre_str} {director} {cast_str} {desc} {year_bucket}"
        docs.append(doc)
    return docs


# ── CONTENT-BASED FILTERING ──────────────────────────────────────
class ContentBasedRecommender:
    def __init__(self, movies):
        self.movies   = movies
        self.id_to_idx = {m["id"]: i for i, m in enumerate(movies)}
        docs           = build_content_features(movies)
        self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self.tfidf_matrix = self.vectorizer.fit_transform(docs)

    def recommend(self, movie_id, top_n=6):
        if movie_id not in self.id_to_idx:
            return []
        idx   = self.id_to_idx[movie_id]
        sims  = cosine_similarity(self.tfidf_matrix[idx], self.tfidf_matrix).flatten()
        sims[idx] = 0  # exclude self
        top_indices = np.argsort(sims)[::-1][:top_n]
        results = []
        for i in top_indices:
            movie = self.movies[i].copy()
            movie["score"]      = round(float(sims[i]) * 100, 1)
            movie["match_reason"] = _explain_match(self.movies[idx], movie)
            results.append(movie)
        return results


# ── COLLABORATIVE FILTERING ──────────────────────────────────────
class CollaborativeRecommender:
    def __init__(self, movies, user_ratings):
        self.movies       = movies
        self.user_ratings = user_ratings
        self.id_to_idx    = {m["id"]: i for i, m in enumerate(movies)}
        self.matrix       = self._build_matrix()

    def _build_matrix(self):
        users  = list(self.user_ratings.keys())
        n_u    = len(users)
        n_m    = len(self.movies)
        mat    = np.zeros((n_u, n_m))
        for ui, user in enumerate(users):
            for movie_id, rating in self.user_ratings[user].items():
                if movie_id in self.id_to_idx:
                    mat[ui][self.id_to_idx[movie_id]] = rating
        self.users = users
        return mat

    def recommend_for_ratings(self, user_ratings_dict, top_n=6):
        """Given a dict of {movie_id: rating}, find similar users and recommend."""
        n_m    = len(self.movies)
        user_vec = np.zeros(n_m)
        for movie_id, rating in user_ratings_dict.items():
            if movie_id in self.id_to_idx:
                user_vec[self.id_to_idx[movie_id]] = rating

        # Cosine similarity between new user and all existing users
        rated_mask = user_vec > 0
        if rated_mask.sum() == 0:
            return []

        sims = cosine_similarity([user_vec], self.matrix)[0]
        # Weighted average of ratings from similar users
        scores = np.zeros(n_m)
        weight_sum = np.zeros(n_m)
        for ui, sim in enumerate(sims):
            if sim <= 0:
                continue
            for mi in range(n_m):
                if self.matrix[ui][mi] > 0:
                    scores[mi]     += sim * self.matrix[ui][mi]
                    weight_sum[mi] += sim

        predicted = np.zeros(n_m)
        for mi in range(n_m):
            if weight_sum[mi] > 0:
                predicted[mi] = scores[mi] / weight_sum[mi]

        # Zero out already-rated movies
        for movie_id in user_ratings_dict:
            if movie_id in self.id_to_idx:
                predicted[self.id_to_idx[movie_id]] = 0

        top_indices = np.argsort(predicted)[::-1][:top_n]
        results = []
        for i in top_indices:
            if predicted[i] == 0:
                continue
            movie = self.movies[i].copy()
            movie["score"]        = round(float(predicted[i]) / 10 * 100, 1)
            movie["match_reason"] = "Liked by users with similar taste"
            results.append(movie)
        return results


# ── GENRE-BASED FILTERING ────────────────────────────────────────
class GenreRecommender:
    def __init__(self, movies):
        self.movies = movies

    def recommend(self, genres, top_n=6, exclude_ids=None):
        exclude_ids = exclude_ids or []
        scored = []
        for m in self.movies:
            if m["id"] in exclude_ids:
                continue
            overlap = len(set(m["genres"]) & set(genres))
            if overlap > 0:
                score = (overlap / len(genres)) * 60 + (m["rating"] / 10) * 40
                mc = m.copy()
                mc["score"]        = round(score, 1)
                mc["match_reason"] = f"Matches {overlap} of your preferred genres"
                scored.append(mc)
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_n]


# ── HYBRID RECOMMENDER ───────────────────────────────────────────
class HybridRecommender:
    def __init__(self):
        self.content_rec = ContentBasedRecommender(MOVIES)
        self.collab_rec  = CollaborativeRecommender(MOVIES, USER_RATINGS)
        self.genre_rec   = GenreRecommender(MOVIES)

    def recommend_by_movie(self, movie_id, top_n=6):
        return self.content_rec.recommend(movie_id, top_n)

    def recommend_by_ratings(self, ratings, top_n=6):
        return self.collab_rec.recommend_for_ratings(ratings, top_n)

    def recommend_by_genres(self, genres, top_n=6, exclude_ids=None):
        return self.genre_rec.recommend(genres, top_n, exclude_ids)

    def recommend_hybrid(self, movie_id, user_ratings, top_n=6):
        """Blend content-based (60%) + collaborative (40%)."""
        cb = self.content_rec.recommend(movie_id, top_n * 2)
        cf = self.collab_rec.recommend_for_ratings(user_ratings, top_n * 2)

        scores = {}
        for r in cb:
            scores[r["id"]] = {"movie": r, "score": r["score"] * 0.6, "source": "content"}
        for r in cf:
            if r["id"] in scores:
                scores[r["id"]]["score"] += r["score"] * 0.4
                scores[r["id"]]["source"] = "hybrid"
            else:
                scores[r["id"]] = {"movie": r, "score": r["score"] * 0.4, "source": "collab"}

        ranked = sorted(scores.values(), key=lambda x: x["score"], reverse=True)[:top_n]
        results = []
        for entry in ranked:
            m = entry["movie"].copy()
            m["score"]  = round(entry["score"], 1)
            m["source"] = entry["source"]
            results.append(m)
        return results

    def get_all_genres(self):
        genres = set()
        for m in MOVIES:
            genres.update(m["genres"])
        return sorted(genres)

    def get_movie_by_id(self, movie_id):
        for m in MOVIES:
            if m["id"] == movie_id:
                return m
        return None

    def search(self, query):
        q = query.lower()
        results = []
        for m in MOVIES:
            score = 0
            if q in m["title"].lower():     score += 10
            if q in m["director"].lower():  score += 5
            if any(q in g.lower() for g in m["genres"]): score += 3
            if any(q in c.lower() for c in m["cast"]):   score += 4
            if score > 0:
                mc = m.copy()
                mc["score"] = score
                results.append(mc)
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:8]


# ── HELPER ───────────────────────────────────────────────────────
def _explain_match(source, target):
    shared_genres = set(source["genres"]) & set(target["genres"])
    if source["director"] == target["director"]:
        return f"Same director: {source['director']}"
    if shared_genres:
        return f"Similar genre: {', '.join(list(shared_genres)[:2])}"
    shared_cast = set(source["cast"]) & set(target["cast"])
    if shared_cast:
        return f"Shared cast: {list(shared_cast)[0]}"
    return "Similar themes and style"


# ── SINGLETON ────────────────────────────────────────────────────
recommender = HybridRecommender()
