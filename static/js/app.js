// ── STATE ──────────────────────────────────────────────────────
const state = {
  movies:        [],
  userRatings:   {},      // { movie_id: rating }
  selectedGenres: new Set(),
  currentMovieId: null,
};

// ── INIT ───────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  await loadMovies();
  setupNav();
  setupSearch();
  renderTopRated();
  renderRateList();
  renderGenreSelector();
  renderHeroReel();
});

// ── DATA ───────────────────────────────────────────────────────
async function loadMovies() {
  const res = await fetch("/api/movies");
  state.movies = await res.json();
}

// ── NAV ────────────────────────────────────────────────────────
function setupNav() {
  document.querySelectorAll(".nav-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
    });
  });
}

// ── HERO REEL ──────────────────────────────────────────────────
function renderHeroReel() {
  const picks = [1, 8, 2]; // Dark Knight, Spirited Away, Inception
  const reel  = document.getElementById("heroReel");
  picks.forEach(id => {
    const m = state.movies.find(x => x.id === id);
    if (!m) return;
    const card = el("div", "reel-card", `
      <div class="reel-poster">${renderPoster(m.poster, 'reel-poster')}</div>
      <div class="reel-title">${m.title}</div>
    `);
    reel.appendChild(card);
  });
}

// ── TOP RATED GRID ─────────────────────────────────────────────
async function renderTopRated() {
  const res    = await fetch("/api/top_rated?n=12");
  const movies = await res.json();
  const grid   = document.getElementById("topRatedGrid");
  grid.innerHTML = "";
  movies.forEach(m => grid.appendChild(movieCard(m, onMovieClick)));
}

function onMovieClick(movie) {
  state.currentMovieId = movie.id;
  getContentRecs(movie);
}

// ── MOVIE CARD ─────────────────────────────────────────────────
function movieCard(m, onClick, showScore = false) {
  const card = document.createElement("div");
  card.className = "movie-card";
  card.innerHTML = `
    <div class="card-poster">
      ${renderPoster(m.poster, 'card-poster')}
      <div class="card-rating">⭐ ${m.rating}</div>
      ${showScore && m.score ? `<div class="card-score">${m.score}%</div>` : ""}
    </div>
    <div class="card-body">
      <div class="card-title">${m.title}</div>
      <div class="card-year">${m.year} · ${m.director?.split(" ").slice(-1)[0]}</div>
      <div class="card-genres">${(m.genres || []).slice(0, 2).map(g => `<span class="genre-chip">${g}</span>`).join("")}</div>
      ${m.match_reason ? `<div style="font-size:10px;color:var(--gold);margin-top:8px;">✦ ${m.match_reason}</div>` : ""}
    </div>
  `;
  card.addEventListener("click", () => {
    if (onClick) onClick(m);
    else openModal(m.id);
  });
  card.addEventListener("dblclick", () => openModal(m.id));
  return card;
}

// ── CONTENT-BASED RECS ─────────────────────────────────────────
async function getContentRecs(movie) {
  const panel = document.getElementById("recPanel");
  panel.style.display = "block";
  document.getElementById("recGrid").innerHTML = loader();
  document.getElementById("recBasedOn").textContent = movie.title;
  document.getElementById("recMethod").textContent  = "Content-Based Filtering";
  document.getElementById("recTechnique").textContent = "TF-IDF + Cosine Similarity on genres, director, cast & description";
  panel.scrollIntoView({ behavior: "smooth", block: "start" });

  const res  = await fetch("/api/recommend/content", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ movie_id: movie.id, top_n: 6 })
  });
  const data = await res.json();
  const grid = document.getElementById("recGrid");
  grid.innerHTML = "";
  if (!data.results?.length) { grid.innerHTML = `<p style="color:var(--text-muted)">No recommendations found.</p>`; return; }
  data.results.forEach(m => grid.appendChild(movieCard(m, null, true)));
}

function closeRecPanel() {
  document.getElementById("recPanel").style.display = "none";
  state.currentMovieId = null;
}

// ── RATE LIST ──────────────────────────────────────────────────
function renderRateList() {
  const list = document.getElementById("rateList");
  list.innerHTML = "";
  state.movies.forEach(m => {
    const item = el("div", "rate-item", `
      <div class="rate-poster">${renderPoster(m.poster, 'rate-poster')}</div>
      <div class="rate-info">
        <div class="rate-title">${m.title}</div>
        <div class="rate-meta">${m.year} · ${m.genres?.slice(0,2).join(", ")}</div>
      </div>
      <div class="star-row" data-id="${m.id}">
        ${[1,2,3,4,5,6,7,8,9,10].map(n => `<button class="star" data-v="${n}" title="${n}/10">★</button>`).join("")}
      </div>
    `);
    const stars = item.querySelectorAll(".star");
    stars.forEach(star => {
      star.addEventListener("click", () => setRating(m.id, parseInt(star.dataset.v), stars));
      star.addEventListener("mouseenter", () => highlightStars(stars, parseInt(star.dataset.v)));
      star.addEventListener("mouseleave",  () => highlightStars(stars, state.userRatings[m.id] || 0));
    });
    list.appendChild(item);
  });
}

function setRating(movieId, value, stars) {
  state.userRatings[movieId] = value;
  highlightStars(stars, value);
  stars[0].closest(".rate-item").classList.add("rated");
  updateRatingsSummary();
  document.getElementById("getRecsBtn").disabled = Object.keys(state.userRatings).length < 2;
}

function highlightStars(stars, value) {
  stars.forEach((s, i) => s.classList.toggle("active", i < value));
}

function updateRatingsSummary() {
  const box = document.getElementById("ratingsSummary");
  const entries = Object.entries(state.userRatings);
  if (!entries.length) { box.innerHTML = `<p class="empty-msg">Start rating movies →</p>`; return; }
  box.innerHTML = entries.map(([id, r]) => {
    const m = state.movies.find(x => x.id === parseInt(id));
    return `<div class="rating-item">
      <span class="summary-info">${renderPoster(m?.poster, 'summary-poster')} <span class="summary-title">${m?.title || "Movie"}</span></span>
      <span class="rating-stars">${"★".repeat(Math.round(r / 2))}</span>
    </div>`;
  }).join("");
}

function clearRatings() {
  state.userRatings = {};
  document.querySelectorAll(".rate-item").forEach(i => i.classList.remove("rated"));
  document.querySelectorAll(".star").forEach(s => s.classList.remove("active"));
  updateRatingsSummary();
  document.getElementById("getRecsBtn").disabled = true;
  document.getElementById("collabRecPanel").style.display = "none";
}

async function getCollabRecs() {
  const panel = document.getElementById("collabRecPanel");
  panel.style.display = "block";
  document.getElementById("collabRecGrid").innerHTML = loader();
  panel.scrollIntoView({ behavior: "smooth", block: "start" });

  const res  = await fetch("/api/recommend/collaborative", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ratings: state.userRatings, top_n: 6 })
  });
  const data = await res.json();
  const grid = document.getElementById("collabRecGrid");
  grid.innerHTML = "";
  if (!data.results?.length) {
    grid.innerHTML = `<p style="color:var(--text-muted);padding:20px">Try rating more movies for better results.</p>`;
    return;
  }
  data.results.forEach(m => grid.appendChild(movieCard(m, null, true)));
}

// ── GENRE FILTER ───────────────────────────────────────────────
async function renderGenreSelector() {
  const res    = await fetch("/api/genres");
  const genres = await res.json();
  const box    = document.getElementById("genreSelector");
  genres.forEach(g => {
    const btn = el("button", "genre-btn", g);
    btn.addEventListener("click", () => {
      btn.classList.toggle("selected");
      state.selectedGenres.has(g) ? state.selectedGenres.delete(g) : state.selectedGenres.add(g);
    });
    box.appendChild(btn);
  });
}

function clearGenres() {
  state.selectedGenres.clear();
  document.querySelectorAll(".genre-btn").forEach(b => b.classList.remove("selected"));
  document.getElementById("genreRecPanel").style.display = "none";
}

async function getGenreRecs() {
  if (!state.selectedGenres.size) { showToast("Select at least one genre"); return; }
  const panel = document.getElementById("genreRecPanel");
  panel.style.display = "block";
  document.getElementById("genreRecGrid").innerHTML = loader();
  panel.scrollIntoView({ behavior: "smooth", block: "start" });

  const res  = await fetch("/api/recommend/genre", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ genres: [...state.selectedGenres], top_n: 8 })
  });
  const data = await res.json();
  const grid = document.getElementById("genreRecGrid");
  grid.innerHTML = "";
  data.results?.forEach(m => grid.appendChild(movieCard(m, null, true)));
}

// ── SEARCH ─────────────────────────────────────────────────────
function setupSearch() {
  const input   = document.getElementById("searchInput");
  const results = document.getElementById("searchResults");
  let   timer;

  input.addEventListener("input", () => {
    clearTimeout(timer);
    const q = input.value.trim();
    if (q.length < 2) { results.classList.remove("open"); return; }
    timer = setTimeout(async () => {
      const res  = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      results.innerHTML = "";
      if (!data.length) { results.classList.remove("open"); return; }
      data.forEach(m => {
        const item = el("div", "search-result-item", `
          <span class="sri-poster">${renderPoster(m.poster, 'sri-poster')}</span>
          <div>
            <div class="sri-title">${m.title}</div>
            <div class="sri-meta">${m.year} · ${m.genres?.slice(0,2).join(", ")}</div>
          </div>
        `);
        item.addEventListener("click", () => {
          results.classList.remove("open");
          input.value = "";
          openModal(m.id);
        });
        results.appendChild(item);
      });
      results.classList.add("open");
    }, 220);
  });

  document.addEventListener("click", e => {
    if (!e.target.closest(".search-wrap")) results.classList.remove("open");
  });
}

// ── MODAL ──────────────────────────────────────────────────────
async function openModal(movieId) {
  const overlay = document.getElementById("modalOverlay");
  const content = document.getElementById("modalContent");
  overlay.classList.add("open");
  content.innerHTML = `<div class="loader"><div class="loader-dots"><span></span><span></span><span></span></div></div>`;

  const res = await fetch(`/api/movie/${movieId}`);
  const m   = await res.json();

  content.innerHTML = `
    <div class="modal-split">
      <div class="modal-left">
        <div class="modal-poster">${renderPoster(m.poster, 'modal-poster')}</div>
      </div>
      <div class="modal-right">
        <div class="modal-rating">⭐ ${m.rating} / 10</div>
        <h2 class="modal-title">${m.title}</h2>
        <div class="modal-year-dir">${m.year} · Directed by ${m.director}</div>
        <div class="modal-genres">${m.genres.map(g => `<span class="modal-genre-chip">${g}</span>`).join("")}</div>
        <p class="modal-desc">${m.description}</p>
        <p class="modal-cast"><strong>Cast:</strong> ${m.cast.join(", ")}</p>
        <div class="modal-actions">
          <button class="primary-btn" onclick="closeModal(); getContentRecs(${JSON.stringify(m).replace(/"/g,'&quot;')})">
            Find Similar Movies
          </button>
        </div>
      </div>
    </div>
  `;
}

function closeModal() {
  document.getElementById("modalOverlay").classList.remove("open");
}

document.addEventListener("keydown", e => { if (e.key === "Escape") closeModal(); });

// ── UTILS ──────────────────────────────────────────────────────
function el(tag, className, html = "") {
  const e = document.createElement(tag);
  e.className = className;
  e.innerHTML = html;
  return e;
}

function loader() {
  return `<div class="loader"><div class="loader-dots"><span></span><span></span><span></span></div> Finding recommendations…</div>`;
}

function showToast(msg) {
  const t = el("div", "toast", msg);
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2400);
}

function renderPoster(poster, className) {
  if (poster && (poster.startsWith("http") || poster.includes("/"))) {
    return `<img src="${poster}" class="${className}-img" alt="poster" />`;
  }
  return poster || "🎬";
}
