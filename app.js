/* 쿠폰라이브러리 — 정적 프론트엔드 (의존성 없음) */
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
  const CATEGORY_LABEL = { shopping: "쇼핑", travel: "여행", fashion: "패션", card: "카드혜택" };
  const CATEGORY_ORDER = ["all", "shopping", "travel", "fashion", "card"];

  const state = { category: "all", platform: "all", type: "all", q: "" };
  let DATA = null;
  let platformById = new Map();

  const $ = (id) => document.getElementById(id);
  const el = (tag, props = {}, children = []) => {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(props)) {
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else if (k === "html") node.innerHTML = v;
      else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v);
    }
    for (const child of [].concat(children)) if (child) node.appendChild(child);
    return node;
  };

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

  const inCategory = (c) => (state.category === "all" ? true : state.category === "card" ? c.type === "card" : c.category === state.category);

  const baseSet = () => DATA.coupons.filter((c) => inCategory(c) && matchesQuery(c, state.q));
  const platformSet = () => baseSet().filter((c) => (state.type === "all" ? true : c.type === state.type));
  const finalSet = () =>
    platformSet().filter((c) => (state.platform === "all" ? true : c.platform_id === state.platform));

  /* ---------- 필터 UI ---------- */
  function renderCategoryTabs() {
    const counts = { all: 0, shopping: 0, travel: 0, fashion: 0, card: 0 };
    for (const c of DATA.coupons) {
      counts.all += 1;
      counts[c.category] = (counts[c.category] || 0) + 1;
      if (c.type === "card") counts.card += 1;
    }
    const nav = $("category-tabs");
    nav.replaceChildren(
      ...CATEGORY_ORDER.filter((key) => key === "all" || counts[key] > 0).map((key) =>
        el("button", {
          class: "tab",
          role: "tab",
          "aria-selected": String(state.category === key),
          text: `${CATEGORY_LABEL[key] || "전체"} ${counts[key].toLocaleString("ko-KR")}`,
          onclick: () => {
            state.category = key;
            state.platform = "all";
            state.type = "all";
            renderAll();
          },
        })
      )
    );
  }

  function renderPlatformChips() {
    const pool = baseSet().filter((c) => (state.type === "all" ? true : c.type === state.type));
    const counts = new Map();
    for (const c of pool) counts.set(c.platform_id, (counts.get(c.platform_id) || 0) + 1);
    const order = DATA.platforms.map((p) => p.id).filter((id) => counts.has(id));
    const box = $("platform-chips");
    const items = [
      el("button", {
        class: "chip",
        "aria-pressed": String(state.platform === "all"),
        text: `전체 플랫폼 ${pool.length.toLocaleString("ko-KR")}`,
        onclick: () => { state.platform = "all"; renderAll(); },
      }),
    ];
    for (const id of order) {
      const meta = platformById.get(id);
      items.push(
        el("button", {
          class: "chip",
          "aria-pressed": String(state.platform === id),
          onclick: () => { state.platform = id; renderAll(); },
          children: [document.createTextNode(meta ? meta.name : id), el("em", { text: String(counts.get(id)) })],
        })
      );
    }
    box.replaceChildren(...items);
  }

  function renderTypeChips() {
    const pool = baseSet();
    const counts = new Map();
    for (const c of pool) counts.set(c.type, (counts.get(c.type) || 0) + 1);
    const box = $("type-chips");
    const items = [
      el("button", {
        class: "chip",
        "aria-pressed": String(state.type === "all"),
        text: `유형 전체 ${pool.length.toLocaleString("ko-KR")}`,
        onclick: () => { state.type = "all"; renderAll(); },
      }),
    ];
    for (const type of TYPE_ORDER) {
      if (!counts.get(type)) continue;
      items.push(
        el("button", {
          class: "chip",
          "aria-pressed": String(state.type === type),
          onclick: () => { state.type = state.type === type ? "all" : type; renderAll(); },
          children: [document.createTextNode(TYPE_LABEL[type]), el("em", { text: String(counts.get(type)) })],
        })
      );
    }
    box.replaceChildren(...items);
  }

  /* ---------- 카드 ---------- */
  const ICON_COPY = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9"><rect x="9" y="9" width="11" height="11" rx="2.5"/><path d="M15 5.5V5a2 2 0 0 0-2-2H5.5A2.5 2.5 0 0 0 3 5.5V13a2 2 0 0 0 2 2h.5"/></svg>';
  const ICON_GO = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17 17 7"/><path d="M9 7h8v8"/></svg>';

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

  function buildCard(c, showPlatform) {
    const top = el("div", { class: "card-top" }, [
      el("span", { class: `badge ${c.type}`, text: TYPE_LABEL[c.type] }),
      showPlatform ? el("span", { class: "section-tag", text: c.platform }) : null,
      c.section ? el("span", { class: "section-tag", text: c.section }) : null,
    ]);

    const rows = el("dl", { class: "rows" }, [
      el("div", { class: "row" }, [
        el("dt", { text: "적용 방법" }),
        el("dd", { class: "clamp2", text: c.apply, title: c.apply }),
      ]),
      el("div", { class: "row expiry" }, [
        el("dt", { text: "사용 기한" }),
        el("dd", { class: c.expiry && c.expiry.includes("표기 없음") ? "none" : "", text: c.expiry || "사용 기한 표기 없음" }),
      ]),
    ]);

    const foot = el("div", { class: "card-foot" });
    if (c.code) {
      const copyBtn = el("button", {
        class: "copy",
        type: "button",
        "aria-label": `${c.code} 코드 복사`,
        html: ICON_COPY,
        onclick: () => copyText(c.code, copyBtn),
      });
      foot.appendChild(
        el("span", { class: "code-box" }, [el("code", { text: c.code }), copyBtn])
      );
    }

    const kids = [top, el("h3", { text: c.benefit })];
    if (c.condition) kids.push(el("p", { class: "cond", text: c.condition }));
    kids.push(rows, foot);

    const card = el("article", { class: `card${c.code ? "" : " no-code"}` }, kids);

    // 주 동작: 전용 링크(새 탭). 앱이 설치된 기기에서는 https 링크가 앱으로 이어질 수 있다.
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

  /* ---------- 목록 ---------- */
  function renderList() {
    const list = finalSet();
    $("count").innerHTML = `<b>${list.length.toLocaleString("ko-KR")}</b>개 쿠폰`;
    $("empty").hidden = list.length > 0;
    const content = $("content");

    if (!list.length) { content.replaceChildren(); return; }

    if (state.platform !== "all") {
      const meta = platformById.get(state.platform);
      const group = el("section", { class: "platform-group" }, [
        el("div", { class: "platform-head" }, [
          el("h2", { text: meta ? meta.name : state.platform }),
          el("span", { class: "cat", text: CATEGORY_LABEL[meta ? meta.category : ""] || "" }),
          el("span", { class: "num", text: `${list.length}개` }),
        ]),
      ]);
      group.appendChild(el("div", { class: "grid" }, list.map((c) => buildCard(c, false))));
      content.replaceChildren(group);
      return;
    }

    const byPlatform = new Map();
    for (const c of list) {
      if (!byPlatform.has(c.platform_id)) byPlatform.set(c.platform_id, []);
      byPlatform.get(c.platform_id).push(c);
    }
    const groups = [];
    for (const [id, coupons] of byPlatform) {
      const meta = platformById.get(id);
      const head = el("div", { class: "platform-head" }, [
        el("h2", { text: meta ? meta.name : coupons[0].platform }),
        el("span", { class: "cat", text: CATEGORY_LABEL[meta ? meta.category : ""] || "" }),
        el("span", { class: "num", text: `${coupons.length}개` }),
        el("button", {
          class: "filter-link",
          type: "button",
          text: "이 플랫폼만 보기",
          onclick: () => { state.platform = id; renderAll(); },
        }),
      ]);
      groups.push(
        el("section", { class: "platform-group" }, [head, el("div", { class: "grid" }, coupons.map((c) => buildCard(c, false)))])
      );
    }
    content.replaceChildren(...groups);
  }

  let toastTimer;
  function toast(message) {
    const node = $("toast");
    node.textContent = message;
    node.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => node.classList.remove("show"), 1600);
  }

  function renderAll() {
    renderCategoryTabs();
    renderPlatformChips();
    renderTypeChips();
    renderList();
  }

  /* ---------- 시작 ---------- */
  function boot(data) {
    DATA = data;
    platformById = new Map(data.platforms.map((p) => [p.id, p]));
    const stamp = formatDate(data.generated_at);
    $("updated").textContent = `업데이트 ${stamp}`;
    $("updated-foot").textContent = stamp;
    renderAll();

    let timer;
    $("search").addEventListener("input", (event) => {
      clearTimeout(timer);
      const value = event.target.value.trim().toLowerCase();
      timer = setTimeout(() => {
        state.q = value;
        state.platform = "all";
        renderAll();
      }, 140);
    });
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
      $("content").replaceChildren(
        el("p", { class: "empty", text: `쿠폰 데이터를 불러오지 못했습니다 (${err.message}). 잠시 후 새로고침해 주세요.` })
      );
    });
})();
