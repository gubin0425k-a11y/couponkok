/* 쿠폰콕 — 정적 프론트엔드 (의존성 없음) */
(() => {
  "use strict";

  const TYPE_LABEL = {
    signup: "신규·첫구매",
    card: "카드·간편결제",
    member: "멤버십·대상자 전용",
    code: "코드 입력형",
    link: "전용 링크형",
  };
  const TYPE_ORDER = ["signup", "card", "member", "code", "link"];

  /* 4대 모음ZIP의 표시 설정. 개수·대표 브랜드는 실제 데이터에서 채운다. */
  const ZIP_META = {
    travel: {
      keyword: "여행",
      lead: "항공·숙소·투어·교통",
      tone: "#d9e8fa",
      accent: "#2f5bea",
      art: "assets/zip-travel.webp",
      artFallback: "assets/zip-travel.png",
      artAlt: "지도와 항공권을 담은 여행 가방 일러스트",
      preferred: ["트립닷컴", "KKday", "클룩", "NOL(야놀자)", "아고다"],
    },
    deal: {
      keyword: "쇼핑·직구",
      lead: "종합몰·해외 직구",
      tone: "#fbe3d2",
      accent: "#cc5522",
      art: "assets/zip-deal.webp",
      artFallback: "assets/zip-deal.png",
      artAlt: "택이 달린 택배 상자와 쇼핑백 일러스트",
      preferred: ["알리익스프레스", "테무", "조마샵", "레고", "케이스티파이"],
    },
    living: {
      keyword: "생활",
      lead: "식품·배달·리빙·뷰티",
      tone: "#dcebd9",
      accent: "#3f8a4c",
      art: "assets/zip-living.webp",
      artFallback: "assets/zip-living.png",
      artAlt: "장바구니에 담긴 우유·채소와 쿠폰 일러스트",
      preferred: ["마켓컬리", "오늘의집", "쿠팡이츠", "펫프렌즈", "클럽클리오"],
    },
    fashion: {
      keyword: "패션",
      lead: "의류·잡화·명품",
      tone: "#e6dff5",
      accent: "#7a4fd0",
      art: "assets/zip-fashion.webp",
      artFallback: "assets/zip-fashion.png",
      artAlt: "옷걸이에 걸린 티셔츠와 스니커즈 일러스트",
      preferred: ["무신사", "지그재그", "H&M", "24S", "크림"],
    },
  };
  const ZIP_ORDER = ["travel", "deal", "living", "fashion"];

  const CONSENT_KEY = "coupon-kok:notice-agreed";
  const state = { view: "home", zip: null, type: "all", platform: "all", q: "" };

  let DATA = null;
  let platformById = new Map();
  let pendingLink = null;
  let lastFocused = null;
  let consentMemory = false;

  const $ = (id) => document.getElementById(id);
  const el = (tag, props = {}, children = []) => {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(props)) {
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else if (k === "children") { for (const ch of [].concat(v)) if (ch) node.appendChild(ch); }
      else if (k === "html") node.innerHTML = v;
      else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v);
    }
    for (const child of [].concat(children)) if (child) node.appendChild(child);
    return node;
  };
  const nf = (n) => Number(n || 0).toLocaleString("ko-KR");

  const formatDate = (iso) => {
    if (!iso) return "-";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "-";
    const p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}.${p(d.getMonth() + 1)}.${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
  };

  const matchesQuery = (c, q) => {
    if (!q) return true;
    const hay = [c.platform, c.benefit, c.section, c.condition, c.code, TYPE_LABEL[c.type]]
      .filter(Boolean).join(" ").toLowerCase();
    return q.split(/\s+/).every((word) => hay.includes(word));
  };

  const zipOf = (c) => c.zip || (platformById.get(c.platform_id) || {}).zip || "deal";

  /* ---------- 모음ZIP 카드 ---------- */
  const ARROW =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h13"/><path d="M12 5.5 18.5 12 12 18.5"/></svg>';

  function zipSummary() {
    const list = Array.isArray(DATA.zips) ? DATA.zips : [];
    if (list.length) return list;
    return ZIP_ORDER.map((key) => {
      const ps = DATA.platforms.filter((p) => zipOf(p) === key);
      const ids = new Set(ps.map((p) => p.id));
      return {
        key,
        label: `${ZIP_META[key].keyword} 쿠폰`,
        platforms: ps.length,
        coupons: DATA.coupons.filter((c) => ids.has(c.platform_id)).length,
      };
    });
  }

  function pickBrands(key) {
    const inZip = DATA.platforms
      .filter((p) => zipOf(p) === key)
      .sort((a, b) => (b.count || 0) - (a.count || 0));
    const names = inZip.map((p) => p.name);
    const picked = [];
    for (const name of (ZIP_META[key] || {}).preferred || []) {
      if (names.includes(name) && !picked.includes(name)) picked.push(name);
      if (picked.length >= 5) break;
    }
    for (const name of names) {
      if (picked.length >= 5) break;
      if (!picked.includes(name)) picked.push(name);
    }
    return picked;
  }

  function buildZipCard(zip, index) {
    const key = zip.key;
    const meta = ZIP_META[key] || { keyword: zip.label || key, lead: "", tone: "#eef2ff", accent: "#2f5bea" };
    const brands = pickBrands(key);
    const card = el("a", {
      class: `zip-card${index % 2 ? " flip" : ""}`,
      href: `#/zip/${key}`,
      "aria-label": `${zip.label || meta.keyword} — ${nf(zip.coupons)}개 모아보기`,
    });
    card.style.setProperty("--tone", meta.tone);
    card.style.setProperty("--zip-accent", meta.accent);

    const text = el("div", { class: "zip-text" }, [
      el("span", { class: "zip-kicker", text: `${String(index + 1).padStart(2, "0")} · ${meta.lead}` }),
      el("h3", { class: "zip-title" }, [
        el("span", { class: "line line1", text: meta.keyword }),
        el("span", { class: "line line2" }, [
          document.createTextNode("쿠폰 "),
          el("span", { class: "zipword", text: "모음ZIP" }),
        ]),
      ]),
      el("p", { class: "zip-brands", text: brands.join(" · ") }),
      el("span", { class: "zip-cta", html: `쿠폰 ${nf(zip.coupons)}개 보기 ${ARROW}` }),
    ]);

    const art = el("div", { class: "zip-art" }, [
      el("picture", {}, [
        el("source", { type: "image/webp", srcset: meta.art }),
        el("img", {
          src: meta.artFallback,
          alt: meta.artAlt || "",
          width: "720",
          height: "720",
          loading: index === 0 ? "eager" : "lazy",
          decoding: "async",
        }),
      ]),
    ]);

    card.append(text, art);
    return card;
  }

  function renderHome() {
    const zips = zipSummary();
    $("zip-list").replaceChildren(...zips.map(buildZipCard));
    $("stat-platforms").textContent = nf(DATA.platforms.length);
    $("stat-coupons").textContent = nf(DATA.coupons.length);
    const allLink = document.querySelector(".home-foot a");
    if (allLink) allLink.textContent = `전체 쿠폰 ${nf(DATA.coupons.length)}개 한 번에 보기`;
  }

  /* ---------- 목록 필터 ---------- */
  const inView = (c) => (state.zip ? zipOf(c) === state.zip : true);
  const baseSet = () => DATA.coupons.filter((c) => inView(c) && matchesQuery(c, state.q));
  const typedSet = () => baseSet().filter((c) => (state.type === "all" ? true : c.type === state.type));
  const finalSet = () => typedSet().filter((c) => (state.platform === "all" ? true : c.platform_id === state.platform));

  function renderTypeChips() {
    const pool = baseSet();
    const counts = new Map();
    for (const c of pool) counts.set(c.type, (counts.get(c.type) || 0) + 1);
    const items = [
      el("button", {
        class: "chip", type: "button",
        "aria-pressed": String(state.type === "all"),
        text: `유형 전체 ${nf(pool.length)}`,
        onclick: () => { state.type = "all"; renderAll(); },
      }),
    ];
    for (const type of TYPE_ORDER) {
      if (!counts.get(type)) continue;
      items.push(
        el("button", {
          class: "chip", type: "button",
          "aria-pressed": String(state.type === type),
          onclick: () => { state.type = state.type === type ? "all" : type; renderAll(); },
          children: [document.createTextNode(TYPE_LABEL[type]), el("em", { text: nf(counts.get(type)) })],
        })
      );
    }
    $("type-chips").replaceChildren(...items);
  }

  function renderPlatformChips() {
    const pool = typedSet();
    const counts = new Map();
    for (const c of pool) counts.set(c.platform_id, (counts.get(c.platform_id) || 0) + 1);
    const order = DATA.platforms.map((p) => p.id).filter((id) => counts.has(id));
    const items = [
      el("button", {
        class: "chip", type: "button",
        "aria-pressed": String(state.platform === "all"),
        text: `전체 플랫폼 ${nf(pool.length)}`,
        onclick: () => { state.platform = "all"; renderAll(); },
      }),
    ];
    for (const id of order) {
      const meta = platformById.get(id);
      items.push(
        el("button", {
          class: "chip", type: "button",
          "aria-pressed": String(state.platform === id),
          onclick: () => { state.platform = id; renderAll(); },
          children: [
            document.createTextNode(meta ? meta.name : id),
            el("em", { text: nf(counts.get(id)) }),
          ],
        })
      );
    }
    $("platform-chips").replaceChildren(...items);
  }

  /* ---------- 쿠폰 카드 ---------- */
  const ICON_COPY = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2.5"/><path d="M15 5.5V5a2 2 0 0 0-2-2H5.5A2.5 2.5 0 0 0 3 5.5V13a2 2 0 0 0 2 2h.5"/></svg>';
  const ICON_GO = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 17 17 7"/><path d="M9 7h8v8"/></svg>';

  function buildCard(c) {
    const top = el("div", { class: "card-top" }, [
      el("span", { class: `badge ${c.type}`, text: TYPE_LABEL[c.type] }),
      c.section ? el("span", { class: "section-tag", text: c.section, title: c.section }) : null,
    ]);

    const rows = el("dl", { class: "rows" }, [
      el("div", { class: "row" }, [
        el("dt", { text: "적용 방법" }),
        el("dd", { class: "clamp2", text: c.apply, title: c.apply }),
      ]),
      el("div", { class: "row expiry" }, [
        el("dt", { text: "사용 기한" }),
        el("dd", {
          class: c.expiry && c.expiry.includes("무기한") ? "none" : "",
          text: c.expiry || "무기한",
        }),
      ]),
    ]);

    const foot = el("div", { class: "card-foot" });
    if (c.code) {
      const copyBtn = el("button", {
        class: "copy", type: "button", "aria-label": `${c.code} 코드 복사`, html: ICON_COPY,
        onclick: () => copyText(c.code, copyBtn),
      });
      foot.appendChild(el("span", { class: "code-box" }, [el("code", { text: c.code }), copyBtn]));
    }

    const kids = [top, el("h3", { text: c.benefit })];
    if (c.condition) kids.push(el("p", { class: "cond", text: c.condition }));
    kids.push(rows, foot);

    const card = el("article", { class: `card${c.code ? "" : " no-code"}` }, kids);
    const go = el("a", {
      class: "go",
      href: c.link || c.source,
      target: "_blank",
      rel: "noopener noreferrer nofollow",
      html: `전용 링크 바로가기 ${ICON_GO}`,
      "aria-label": `${c.platform} 전용 링크 열기 (새 탭)`,
    });
    foot.appendChild(go);
    return card;
  }

  function renderList() {
    const list = finalSet();
    const groupsByPlatform = new Map();
    for (const c of list) {
      if (!groupsByPlatform.has(c.platform_id)) groupsByPlatform.set(c.platform_id, []);
      groupsByPlatform.get(c.platform_id).push(c);
    }

    $("count").innerHTML = `<b>${nf(list.length)}</b>개 쿠폰`;
    $("empty").hidden = list.length > 0;

    const groups = [];
    for (const [id, coupons] of groupsByPlatform) {
      const meta = platformById.get(id);
      const head = el("div", { class: "platform-head" }, [
        el("h2", { text: meta ? meta.name : coupons[0].platform }),
        el("span", { class: "cat", text: zipLabel(meta ? zipOf(meta) : "deal") }),
        el("span", { class: "num", text: `${coupons.length}개` }),
        state.platform === "all"
          ? el("button", {
              class: "filter-link", type: "button", text: "이 플랫폼만 보기",
              onclick: () => { state.platform = id; renderAll(); },
            })
          : null,
      ]);
      groups.push(el("section", { class: "platform-group" }, [
        head,
        el("div", { class: "grid" }, coupons.map(buildCard)),
      ]));
    }
    $("content").replaceChildren(...groups);
  }

  function zipLabel(key) {
    const found = zipSummary().find((z) => z.key === key);
    return found ? found.label : "";
  }

  function renderHeader() {
    const zips = zipSummary();
    const zip = state.zip ? zips.find((z) => z.key === state.zip) : null;
    let title = "전체 쿠폰";
    if (zip && state.q) title = `${zip.label} · ‘${state.q}’`;
    else if (zip) title = zip.label;
    else if (state.q) title = `‘${state.q}’ 검색 결과`;

    const pool = finalSet();
    $("view-title").textContent = title;
    $("view-sub").textContent = `${nf(groupsOf(pool))}개 플랫폼 · ${nf(pool.length)}개 쿠폰`;
  }

  const groupsOf = (list) => new Set(list.map((c) => c.platform_id)).size;

  function renderAll() {
    const isHome = state.view === "home" && !state.q && !state.zip;
    $("home").hidden = !isHome;
    $("results").hidden = isHome;
    if (isHome) {
      renderHome();
      return;
    }
    renderHeader();
    renderTypeChips();
    renderPlatformChips();
    renderList();
  }

  /* ---------- 첫 방문 고지 ---------- */
  const hasConsent = () => {
    try { return localStorage.getItem(CONSENT_KEY) === "1"; } catch (_) { return consentMemory; }
  };
  const saveConsent = () => {
    consentMemory = true;
    try { localStorage.setItem(CONSENT_KEY, "1"); } catch (_) { /* 저장이 막힌 브라우저 */ }
  };

  function openLink(href) {
    // "noopener"을 옵션으로 넘기면 성공해도 null이 돌아와 두 번 열리므로,
    // 창을 열고 나서 opener만 직접 끊는다.
    let win = null;
    try { win = window.open(href, "_blank"); } catch (_) { win = null; }
    if (win) {
      try { win.opener = null; } catch (_) { /* 건널 수 없는 창 */ }
      return;
    }
    // 팝업이 막히면 링크 클릭으로 한 번 더 시도해 사용자가 갇힌 채 남지 않게 한다.
    const a = document.createElement("a");
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  function closeModal() {
    const modal = $("notice");
    modal.hidden = true;
    document.body.style.overflow = "";
    pendingLink = null;
    if (lastFocused && lastFocused.focus) lastFocused.focus();
  }

  function showNotice(trigger) {
    const modal = $("notice");
    lastFocused = trigger || document.activeElement;
    modal.hidden = false;
    document.body.style.overflow = "hidden";
    $("notice-agree").focus();
  }

  function initNotice() {
    $("notice-agree").addEventListener("click", () => {
      const href = pendingLink;
      saveConsent();
      closeModal();
      if (href) openLink(href);
    });
    $("notice-decline").addEventListener("click", closeModal);
    $("notice").addEventListener("click", (event) => {
      if (event.target === $("notice")) closeModal();
    });
    document.addEventListener("keydown", (event) => {
      if ($("notice").hidden) return;
      if (event.key === "Escape") { closeModal(); return; }
      // 모달 밖으로 탭 포커스가 새지 않게 한다.
      if (event.key === "Tab") {
        const focusables = [$("notice-decline"), $("notice-agree")];
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        else if (!focusables.includes(document.activeElement)) { event.preventDefault(); first.focus(); }
      }
    });

    // 쿠폰 버튼(전용 링크)을 처음 누를 때 한 번만 고지한다.
    document.addEventListener("click", (event) => {
      const link = event.target.closest ? event.target.closest("a.go") : null;
      if (!link || hasConsent()) return;
      event.preventDefault();
      pendingLink = link.getAttribute("href");
      showNotice(link);
    });
  }

  function copyText(text, button) {
    const done = () => {
      toast(`코드 ${text} 복사됨`);
      const old = button.getAttribute("aria-label");
      button.setAttribute("aria-label", "복사됨");
      setTimeout(() => button.setAttribute("aria-label", old || "코드 복사"), 1200);
    };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(done).catch(() => fallback());
    } else fallback();

    function fallback() {
      const area = document.createElement("textarea");
      area.value = text;
      area.setAttribute("readonly", "");
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      try { document.execCommand("copy"); done(); } catch (_) { toast("복사에 실패했습니다. 코드를 직접 선택해 주세요."); }
      document.body.removeChild(area);
    }
  }

  let toastTimer;
  function toast(message) {
    const node = $("toast");
    node.textContent = message;
    node.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => node.classList.remove("show"), 1600);
  }

  /* ---------- 화면 전환 ---------- */
  function routeFromHash() {
    const raw = (location.hash || "").replace(/^#/, "");
    const zipMatch = raw.match(/^\/zip\/([a-z]+)$/);
    if (zipMatch && ZIP_META[zipMatch[1]]) return { view: "list", zip: zipMatch[1] };
    if (raw === "/all") return { view: "list", zip: null };
    return { view: "home", zip: null };
  }

  function applyRoute() {
    const route = routeFromHash();
    state.view = route.view;
    state.zip = route.zip;
    state.type = "all";
    state.platform = "all";
    if (route.view === "home") {
      state.q = "";
      $("search").value = "";
    }
    renderAll();
    if (route.view === "home") window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function goHome() {
    if (location.hash && location.hash !== "#/") location.hash = "#/";
    else applyRoute();
  }

  /* ---------- 시작 ---------- */
  function boot(data) {
    DATA = data;
    DATA.coupons = data.coupons.map((c) => ({ ...c }));
    DATA.platforms = data.platforms.map((p) => ({ ...p }));
    platformById = new Map(DATA.platforms.map((p) => [p.id, { ...p, zip: p.zip || "deal" }]));

    const stamp = formatDate(data.generated_at);
    $("updated").textContent = `업데이트 ${stamp}`;
    $("updated-foot").textContent = stamp;

    initNotice();
    applyRoute();

    let timer;
    const onSearch = (event) => {
      clearTimeout(timer);
      const value = event.target.value.trim().toLowerCase();
      timer = setTimeout(() => {
        state.q = value;
        state.type = "all";
        state.platform = "all";
        if (value) {
          state.view = "list";
          renderAll();
        } else if (state.zip) {
          renderAll();
        } else {
          goHome();
        }
      }, 140);
    };
    $("search").addEventListener("input", onSearch);
    $("search").addEventListener("search", onSearch);

    $("back-btn").addEventListener("click", goHome);
    $("all-btn").addEventListener("click", (event) => {
      event.preventDefault();
      $("search").value = "";
      state.q = "";
      state.type = "all";
      state.platform = "all";
      if (location.hash === "#/all") {
        state.view = "list";
        state.zip = null;
        renderAll();
      } else {
        location.hash = "#/all";
      }
    });

    window.addEventListener("hashchange", applyRoute);
  }

  fetch("./data/coupons.json", { cache: "no-cache" })
    .then((res) => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    })
    .then(boot)
    .catch((err) => {
      $("updated").textContent = "데이터를 불러오지 못했습니다";
      $("status-dot").style.background = "#e0554d";
      $("home").hidden = true;
      $("results").hidden = false;
      $("content").replaceChildren(
        el("p", { class: "empty", text: `쿠폰 데이터를 불러오지 못했습니다 (${err.message}). 잠시 후 새로고침해 주세요.` })
      );
    });
})();
