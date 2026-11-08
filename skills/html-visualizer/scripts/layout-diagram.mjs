#!/usr/bin/env node
/**
 * 結構圖自動排版：寫一份簡短的圖描述，程式用 dagre 算座標，輸出照 structure-diagrams.md 規則的 SVG 片段。
 *
 * 為什麼有這支：手算座標最常出的錯是線穿過節點、標籤壓線、viewBox 切到字——都是座標算錯，
 * 不是設計錯。節點連線圖（流程圖／依賴圖／狀態機）交給程式排，作者只寫「誰連到誰」。
 *
 * 用法：node layout-diagram.mjs <描述檔> [-o 輸出檔] [--explore]
 *   描述檔：.txt（下面的行格式）或 .json；輸出預設印到 stdout
 *   --explore：svg 加 class xplore、外面包 <div class="xp" data-explore>（§6.7 探索層，CSS/JS 另外貼）
 *
 * 行格式（一行一件事，# 開頭是註解）：
 *   title: 每週整理排程流程          ← <title>，也是 aria 標題
 *   desc: 兩句話講流向                ← <desc>（選填）
 *   dir: TB                           ← TB 上到下（預設）／LR 左到右
 *   id: weekly                        ← marker 與 class 前綴（選填，預設取檔名）
 *   node <id> <形狀> <文字> [| accent] [| kind=<類別>]
 *       形狀：box 方框・round 圓角膠囊（起迄）・diamond 菱形判斷・dashed 虛線框（可選／例外）
 *       文字太長會自動換行；要指定斷行寫 \n
 *   <from> -> <to> [: 標籤]           ← 實線
 *   <from> -.-> <to> [: 標籤]         ← 虛線（例外、回頭路、非同步）
 *   <from> ==> <to> [: 標籤]          ← 強調主線（每張 ≤2 條）
 *   group <id> <分區名> : <節點id> <節點id> …   ← 虛線分區框（選填）
 *
 * JSON 格式：{ "title", "desc", "dir", "id",
 *   "nodes": [{"id","text","shape","accent","kind"}],
 *   "edges": [{"from","to","label","style":"solid|dashed|accent"}],
 *   "groups": [{"id","label","nodes":[…]}] }
 *
 * 顏色一律 CSS 變數（--ivory --paper --slate --g100 --g300 --g500 --g700 --clay --clay-d --clay-soft），
 * 字型繼承 var(--sans)。座標全部寫絕對值（不用 transform），svg-text-check.mjs 才量得準。
 */
import fs from "node:fs";
import path from "node:path";
import dagre from "./vendor/dagre.mjs";

// ── 參數 ──────────────────────────────────────────
const args = process.argv.slice(2);
const flag = (n) => args.includes(n);
const opt = (n) => {
  const i = args.indexOf(n);
  return i >= 0 ? args[i + 1] : null;
};
const specFile = args.find((a, i) => !a.startsWith("-") && args[i - 1] !== "-o");
if (!specFile) {
  console.error("用法：node layout-diagram.mjs <描述檔.txt|.json> [-o 輸出檔] [--explore]");
  process.exit(64);
}
const die = (m) => {
  console.error("✗ " + m);
  process.exit(1);
};
const warn = (m) => console.error("! " + m);

// ── 讀描述 ────────────────────────────────────────
function parseText(src) {
  const spec = { nodes: [], edges: [], groups: [] };
  src.split(/\r?\n/).forEach((raw, ln) => {
    const line = raw.replace(/^\s+|\s+$/g, "");
    if (!line || line.startsWith("#")) return;
    const where = `第 ${ln + 1} 行`;
    let m;
    if ((m = line.match(/^(title|desc|dir|id)\s*[:：]\s*(.*)$/i))) {
      spec[m[1].toLowerCase()] = m[2].trim();
    } else if ((m = line.match(/^node\s+(\S+)\s+(\S+)\s+(.+)$/))) {
      const [text, ...opts] = m[3].split(/\s*\|\s*/);
      const n = { id: m[1], shape: m[2], text: text.trim() };
      opts.forEach((o) => {
        if (o === "accent") n.accent = true;
        else if (o.startsWith("kind=")) n.kind = o.slice(5);
        else die(`${where} 看不懂的節點選項「${o}」`);
      });
      spec.nodes.push(n);
    } else if ((m = line.match(/^group\s+(\S+)\s+(.+?)\s*[:：]\s*(.+)$/))) {
      spec.groups.push({ id: m[1], label: m[2], nodes: m[3].split(/\s+/) });
    } else if ((m = line.match(/^(\S+)\s+(-\.->|==>|->)\s+(\S+)(?:\s*[:：]\s*(.+))?$/))) {
      const style = m[2] === "->" ? "solid" : m[2] === "==>" ? "accent" : "dashed";
      spec.edges.push({ from: m[1], to: m[3], label: (m[4] || "").trim(), style });
    } else die(`${where} 看不懂：「${line}」`);
  });
  return spec;
}

const src = fs.readFileSync(specFile, "utf8");
const spec = src.trim().startsWith("{") ? JSON.parse(src) : parseText(src);
spec.nodes = spec.nodes || [];
spec.edges = spec.edges || [];
spec.groups = spec.groups || [];
const DIR = (spec.dir || "TB").toUpperCase();
if (!["TB", "LR"].includes(DIR)) die(`dir 只支援 TB 或 LR（收到 ${spec.dir}）`);
const SLUG = (spec.id || path.basename(specFile).replace(/\.[^.]+$/, "")).replace(/[^A-Za-z0-9_-]/g, "") || "dg";
const TITLE = spec.title || "結構圖";
const SHAPES = { box: 1, round: 1, diamond: 1, dashed: 1 };

const byId = {};
spec.nodes.forEach((n) => {
  if (!n.id) die("有節點沒有 id");
  if (byId[n.id]) die(`節點 id 重複：${n.id}`);
  n.shape = n.shape || "box";
  if (!SHAPES[n.shape]) die(`節點 ${n.id} 的形狀「${n.shape}」不認得（box／round／diamond／dashed）`);
  byId[n.id] = n;
});
spec.edges.forEach((e) => {
  if (!byId[e.from]) die(`線 ${e.from}→${e.to}：找不到節點「${e.from}」`);
  if (!byId[e.to]) die(`線 ${e.from}→${e.to}：找不到節點「${e.to}」`);
  if (e.from === e.to) die(`線 ${e.from}→${e.to}：不支援自己連自己`);
  e.style = e.style || "solid";
});
if (spec.nodes.length > 12) warn(`節點 ${spec.nodes.length} 個，超過預算 9（structure-diagrams.md §4），考慮拆成總覽＋細部`);
if (spec.edges.length > 14) warn(`連線 ${spec.edges.length} 條，超過預算 12，考慮拆圖`);

// ── 量字與換行 ────────────────────────────────────
// 沒有瀏覽器可量，用字寬估算：中日韓全形 1em、拉丁約 0.55～0.62em；估寬一律偏大一點，寧可框鬆不可字出框。
const isWide = (ch) => {
  const c = ch.codePointAt(0);
  return (c >= 0x2e80 && c <= 0x9fff) || (c >= 0xac00 && c <= 0xd7af) || (c >= 0xf900 && c <= 0xfaff) || (c >= 0xfe30 && c <= 0xfe4f) || (c >= 0xff00 && c <= 0xff60) || (c >= 0xffe0 && c <= 0xffe6);
};
function textWidth(s, size, bold) {
  let w = 0;
  for (const ch of s) {
    if (isWide(ch)) w += 1;
    else if (ch === " ") w += 0.3;
    else if (/[A-Z0-9@#%&MW]/.test(ch)) w += 0.66;
    else if (/[il.,:;'|!]/.test(ch)) w += 0.3;
    else w += 0.56;
  }
  return w * size * (bold ? 1.06 : 1.0) * 1.04;
}
// 行首不能出現的字、行尾不能出現的字（避頭尾）
const NO_START = new Set([..."，。、？！：；」』）》〉】…,.?!:;)]}％%"]);
const NO_END = new Set([..."「『（《〈【([{"]);
function units(s) {
  // 拉丁字詞、短引號「…」（≤8 字）當一個單位不拆，其餘一字一單位
  const out = [];
  const re = /「[^」]{1,8}」|[A-Za-z0-9_\-./+#@%]+|\s+|./gsu;
  let m;
  while ((m = re.exec(s))) out.push(m[0]);
  // 避頭尾：把行首禁字併進前一個單位、行尾禁字併進後一個單位
  const merged = [];
  for (const u of out) {
    if (merged.length && NO_START.has([...u][0]) && u.length === 1) merged[merged.length - 1] += u;
    else if (merged.length && NO_END.has([...merged[merged.length - 1]].slice(-1)[0])) merged[merged.length - 1] += u;
    else merged.push(u);
  }
  return merged;
}
// 平衡換行：行數取最少可行，再讓每行寬度盡量一樣（不是塞滿第一行、最後一行剩一兩個字）
function wrap(text, size, bold, maxW) {
  const lines = [];
  for (const para of String(text).split(/\\n|\n/)) {
    const us = units(para.trim());
    const ws = us.map((u) => textWidth(u, size, bold));
    const n = us.length;
    const total = ws.reduce((a, b) => a + b, 0);
    if (total <= maxW || n <= 1) {
      lines.push(para.trim());
      continue;
    }
    const lineW = (i, j) => {
      // us[i..j) 一行；行首行尾空白不算
      let a = i,
        b = j;
      while (a < b && /^\s+$/.test(us[a])) a++;
      while (b > a && /^\s+$/.test(us[b - 1])) b--;
      let w = 0;
      for (let k = a; k < b; k++) w += ws[k];
      return w;
    };
    const breakBonus = (j) => {
      // 在標點後、空白處斷比較自然
      const prev = us[j - 1] || "";
      if (/^\s+$/.test(us[j] || "") || /\s$/.test(prev)) return -((size * 2) ** 2);
      if (/[，、。；：？！,;:]$/.test(prev)) return -((size * 3) ** 2);
      return 0;
    };
    let best = null;
    for (let k = Math.ceil(total / maxW); k <= n && !best; k++) {
      const target = total / k;
      // dp[l][j]：前 j 個單位排成 l 行的最小代價
      const dp = Array.from({ length: k + 1 }, () => new Array(n + 1).fill(Infinity));
      const from = Array.from({ length: k + 1 }, () => new Array(n + 1).fill(-1));
      dp[0][0] = 0;
      for (let l = 1; l <= k; l++)
        for (let j = 1; j <= n; j++)
          for (let i = l - 1; i < j; i++) {
            if (dp[l - 1][i] === Infinity) continue;
            const w = lineW(i, j);
            if (w > maxW && j - i > 1) continue;
            const c = dp[l - 1][i] + (w - target) ** 2 + (j < n ? breakBonus(j) : 0);
            if (c < dp[l][j]) {
              dp[l][j] = c;
              from[l][j] = i;
            }
          }
      if (dp[k][n] < Infinity) {
        const cuts = [];
        let j = n;
        for (let l = k; l > 0; l--) {
          const i = from[l][j];
          cuts.unshift(us.slice(i, j).join("").trim());
          j = i;
        }
        best = cuts;
      }
    }
    lines.push(...(best || [para.trim()]));
  }
  return lines;
}

// ── 節點尺寸 ──────────────────────────────────────
const FS = 13, // 節點字級（§5：節點名 13px 600）
  LS = 12, // 標籤字級
  LH = 18; // 行高
for (const n of spec.nodes) {
  const maxW = n.shape === "diamond" ? 8.2 * FS : 12.4 * FS;
  n.lines = wrap(n.text, FS, true, maxW);
  if (n.lines.length > 3) warn(`節點 ${n.id} 換成 ${n.lines.length} 行，超過三行上限（§6.3），考慮縮短字`);
  n.tw = Math.max(...n.lines.map((l) => textWidth(l, FS, true)));
  n.th = n.lines.length * LH;
  if (n.shape === "diamond") {
    // 文字框（tw×th）要整個落在菱形內：tw/w + th/h ≤ 1，再各留邊
    n.h = Math.max(64, Math.round(n.th + 44));
    n.w = Math.round(Math.max((n.tw + 12) / (1 - (n.th + 4) / n.h), n.h * 1.5));
  } else {
    n.w = Math.round(Math.max(n.tw + 32, 96) + (n.shape === "round" ? 12 : 0));
    n.h = Math.max(44, n.th + 24);
  }
}

// ── 標籤尺寸 ──────────────────────────────────────
for (const e of spec.edges) {
  if (!e.label) continue;
  e.lw = Math.ceil(textWidth(e.label, LS, false)) + 8; // 遮罩寬＝字寬＋8
  e.lh = 16;
}

// ── dagre 排版 ────────────────────────────────────
const g = new dagre.graphlib.Graph({ compound: spec.groups.length > 0, multigraph: true });
const hasLabels = spec.edges.some((e) => e.label);
g.setGraph({ rankdir: DIR, nodesep: 40, edgesep: 24, ranksep: hasLabels ? 64 : 48, marginx: 0, marginy: 0 });
g.setDefaultEdgeLabel(() => ({}));
spec.nodes.forEach((n) => g.setNode(n.id, { width: n.w, height: n.h }));
spec.groups.forEach((gr) => {
  g.setNode("__grp_" + gr.id, { paddingTop: 28 });
  gr.nodes.forEach((id) => {
    if (!byId[id]) die(`分區 ${gr.id} 裡的節點「${id}」不存在`);
    g.setParent(id, "__grp_" + gr.id);
  });
});
spec.edges.forEach((e, i) => {
  const lab = {};
  if (e.label) {
    // 標籤佔位置中於線上；實際畫在線的一側（TB 右側、LR 上方），所以佔位要兩倍寬／高
    if (DIR === "TB") Object.assign(lab, { width: 2 * (e.lw + 6), height: e.lh + 6, labelpos: "c" });
    else Object.assign(lab, { width: e.lw + 12, height: 2 * (e.lh + 6), labelpos: "c" });
  }
  g.setEdge(e.from, e.to, lab, "e" + i);
});
dagre.layout(g);

// ── 軸向抽象：A＝層方向（TB 的 y、LR 的 x），C＝同層方向 ─────
const TB = DIR === "TB";
const A = (p) => (TB ? p.y : p.x);
const C = (p) => (TB ? p.x : p.y);
const P = (a, c) => (TB ? { x: c, y: a } : { x: a, y: c });
spec.nodes.forEach((n) => {
  const d = g.node(n.id);
  n.x = d.x;
  n.y = d.y;
  n.halfA = (TB ? n.h : n.w) / 2;
  n.halfC = (TB ? n.w : n.h) / 2;
});
const key = (v) => Math.round(v * 2) / 2;
// 每層的「帶」：該層實體節點與標籤在層方向上佔的半寬
const band = new Map();
const bump = (a, half) => band.set(key(a), Math.max(band.get(key(a)) || 0, half));
spec.nodes.forEach((n) => bump(A(n), n.halfA));
spec.edges.forEach((e, i) => {
  const d = g.edge(e.from, e.to, "e" + i);
  e.pts = d.points.slice(1, -1); // 去掉 dagre 算的框邊交點，端點自己接
  e.pts.forEach((p) => bump(A(p), 0));
  if (e.label) {
    e.lx = d.x;
    e.ly = d.y;
    bump(TB ? d.y : d.x, TB ? e.lh / 2 + 2 : e.lw / 2 + 2);
  }
});

// ── 接點分配：同一邊多條線各有接點（規則 4），菱形多出口優先從左右角出 ─────
// 每條線的端點：src／dst，各記從哪一邊出入（lo＝上／左、hi＝下／右、side＝菱形側角）
spec.edges.forEach((e) => {
  const s = byId[e.from],
    t = byId[e.to];
  const firstA = e.pts.length ? A(e.pts[0]) : A(t);
  const lastA = e.pts.length ? A(e.pts[e.pts.length - 1]) : A(s);
  e.srcSide = firstA >= A(s) ? "hi" : "lo";
  e.dstSide = lastA <= A(t) ? "lo" : "hi";
  e.srcToward = e.pts.length ? C(e.pts[0]) : C(t);
  e.dstToward = e.pts.length ? C(e.pts[e.pts.length - 1]) : C(s);
});
function sameRankBlocked(n, c1, c2) {
  // 菱形側角水平出去到 c2 的這段，同層有沒有別的節點擋在中間
  const lo = Math.min(c1, c2),
    hi = Math.max(c1, c2);
  return spec.nodes.some((o) => o !== n && Math.abs(A(o) - A(n)) < n.halfA + o.halfA && C(o) + o.halfC > lo && C(o) - o.halfC < hi);
}
for (const n of spec.nodes) {
  for (const side of ["lo", "hi"]) {
    const ends = [];
    spec.edges.forEach((e) => {
      if (e.from === n.id && e.srcSide === side) ends.push({ e, end: "src", toward: e.srcToward });
      if (e.to === n.id && e.dstSide === side) ends.push({ e, end: "dst", toward: e.dstToward });
    });
    if (!ends.length) continue;
    ends.sort((a, b) => a.toward - b.toward);
    let rest = ends;
    if (n.shape === "diamond" && side === "hi") {
      // 菱形出口：最左那條往左偏就從左角出、最右那條往右偏就從右角出，其餘從下角
      const outs = ends.filter((x) => x.end === "src");
      if (outs.length >= 2 || ends.length >= 2) {
        const L = ends[0],
          R = ends[ends.length - 1];
        const take = (x, sgn) => {
          const vc = C(n) + sgn * n.halfC;
          // 只有對面那端在側角外側才從側角出；在菱形範圍內就從斜邊直直往下，否則橫線會藏在菱形底下
          if (x.end !== "src" || (x.toward - vc) * sgn < 0 || sameRankBlocked(n, vc, x.toward)) return false;
          x.e.srcPort = { side: true, a: A(n), c: vc, cNext: x.toward };
          return true;
        };
        rest = ends.filter((x) => !((x === L && take(L, -1)) || (x === R && ends.length > 1 && take(R, +1))));
      }
    }
    const N = rest.length;
    const sgn = side === "hi" ? 1 : -1;
    // 接點先放在「對面那一端的正上下方」（線可以直直走、少一個彎），夾在框內；
    // 相鄰接點不到 12px 就改成平均分散在這一邊（規則 4）
    const lim = n.shape === "diamond" ? n.halfC * 0.75 : n.halfC - 10;
    let cs = rest.map((x) => Math.max(C(n) - lim, Math.min(C(n) + lim, x.toward)));
    const tight = cs.some((c, k) => k > 0 && c - cs[k - 1] < 12);
    if (tight) {
      const span = n.shape === "diamond" ? n.halfC * 0.9 : n.halfC * 2;
      if (N > 1 && span / (N + 1) < 12) warn(`節點 ${n.id} 同一邊 ${N} 條線，接點間距不到 12px`);
      cs = rest.map((x, k) =>
        n.shape === "diamond"
          ? C(n) + (N === 1 ? 0 : -span / 2 + (span * k) / (N - 1))
          : C(n) - n.halfC + (span * (k + 1)) / (N + 1),
      );
    }
    rest.forEach((x, k) => {
      const c = cs[k];
      const a =
        n.shape === "diamond"
          ? A(n) + sgn * n.halfA * (1 - Math.abs(c - C(n)) / n.halfC) // 落在斜邊上
          : A(n) + sgn * n.halfA;
      const port = { side: false, a, c };
      if (x.end === "src") x.e.srcPort = port;
      else x.e.dstPort = port;
    });
  }
}

// ── 走線：正交、層間的水平段分軌道（規則 1、3） ─────
// 站點序列：src 接點 → dagre 的中繼點（每層一個，dagre 已替它們在層內留好位置）→ dst 接點
const rankKeys = [...band.keys()].sort((a, b) => a - b);
const gapOf = (a1, a2) => {
  const lo = Math.min(a1, a2),
    hi = Math.max(a1, a2);
  return { lo: lo + (band.get(key(lo)) || 0), hi: hi - (band.get(key(hi)) || 0), k: key(lo) + "~" + key(hi) };
};
const jogs = new Map(); // 間隙 → 這個間隙裡要水平移動的段
spec.edges.forEach((e, i) => {
  const s = byId[e.from],
    t = byId[e.to];
  const stations = [];
  const sp = e.srcPort;
  stations.push({ a: A(s), c: sp.side ? sp.cNext : sp.c });
  e.pts.forEach((p) => stations.push({ a: A(p), c: C(p) }));
  stations.push({ a: A(t), c: e.dstPort.c });
  e.stations = stations;
  e.segs = [];
  for (let k = 0; k < stations.length - 1; k++) {
    const s1 = stations[k],
      s2 = stations[k + 1];
    // 最後一段只差幾 px：把終點接點挪過去，不要畫一個看不出來的小折（框裡挪 6px 仍在框內）
    if (k === 0 && !sp.side && Math.abs(s1.c - s2.c) < 6 && Math.abs(s2.c - C(s)) < s.halfC * (s.shape === "diamond" ? 0.8 : 1) - 4) {
      // 第一段同理：起點接點挪到下一站正上下方（菱形要重算斜邊上的位置）
      sp.c = s1.c = s2.c;
      if (s.shape === "diamond") sp.a = A(s) + Math.sign(sp.a - A(s)) * s.halfA * (1 - Math.abs(sp.c - C(s)) / s.halfC);
    }
    const last = k === stations.length - 2 && t.shape !== "diamond";
    if (Math.abs(s1.c - s2.c) < 0.5 || (last && Math.abs(s1.c - s2.c) < 6 && Math.abs(s1.c - C(t)) < t.halfC - 4)) {
      s2.c = s1.c;
      if (last) e.dstPort.c = s1.c;
      e.segs.push(null);
      continue;
    }
    const gap = gapOf(s1.a, s2.a);
    const seg = { e, gap, c1: s1.c, c2: s2.c, pos: null };
    if (!jogs.has(gap.k)) jogs.set(gap.k, []);
    jogs.get(gap.k).push(seg);
    e.segs.push(seg);
  }
});
for (const [, segs] of jogs) {
  // 區間著色：水平範圍重疊的段放不同軌道
  segs.sort((a, b) => Math.min(a.c1, a.c2) - Math.min(b.c1, b.c2));
  const tracks = [];
  for (const s of segs) {
    const lo = Math.min(s.c1, s.c2) - 10,
      hi = Math.max(s.c1, s.c2) + 10;
    let t = tracks.findIndex((end) => end < lo);
    if (t < 0) {
      t = tracks.length;
      tracks.push(hi);
    } else tracks[t] = hi;
    s.track = t;
  }
  const { lo, hi } = segs[0].gap;
  const T = tracks.length;
  const step = (hi - lo) / (T + 1);
  if (T > 1 && step < 12) warn(`有一層間隙塞了 ${T} 條橫向線，間距不到 12px`);
  segs.forEach((s) => (s.pos = lo + step * (s.track + 1)));
}
// 組出每條線的折點
spec.edges.forEach((e) => {
  const sp = e.srcPort,
    dp = e.dstPort;
  const pts = [];
  if (sp.side) {
    pts.push(P(sp.a, sp.c));
    pts.push(P(sp.a, sp.cNext));
  } else pts.push(P(sp.a, sp.c));
  e.segs.forEach((seg, k) => {
    if (!seg) return;
    pts.push(P(seg.pos, seg.c1));
    pts.push(P(seg.pos, seg.c2));
  });
  pts.push(P(dp.a, dp.c));
  // 拿掉重複點與共線中間點
  const clean = [];
  for (const p of pts) {
    const q = clean[clean.length - 1];
    if (q && Math.abs(q.x - p.x) < 0.5 && Math.abs(q.y - p.y) < 0.5) continue;
    clean.push(p);
  }
  for (let k = clean.length - 2; k > 0; k--) {
    const a = clean[k - 1],
      b = clean[k],
      c = clean[k + 1];
    if ((Math.abs(a.x - b.x) < 0.5 && Math.abs(b.x - c.x) < 0.5) || (Math.abs(a.y - b.y) < 0.5 && Math.abs(b.y - c.y) < 0.5)) clean.splice(k, 1);
  }
  e.route = clean;
  // 標籤放在「穿過標籤層的那一段」上：TB 放線右側、LR 放線上方（規則 2：離線 6px、有遮罩）
  if (e.label) {
    const la = TB ? e.ly : e.lx;
    let lc = TB ? e.lx : e.ly;
    for (let k = 0; k < clean.length - 1; k++) {
      const p = clean[k],
        q = clean[k + 1];
      const along = TB ? Math.abs(p.x - q.x) < 0.5 : Math.abs(p.y - q.y) < 0.5;
      if (!along) continue;
      const a1 = Math.min(A(p), A(q)),
        a2 = Math.max(A(p), A(q));
      if (la >= a1 - 1 && la <= a2 + 1) {
        lc = C(p);
        break;
      }
    }
    if (TB) e.lab = { x: lc + 6, y: la - e.lh / 2, w: e.lw, h: e.lh, tx: lc + 10, ty: la + 4, anchor: "start" };
    else e.lab = { x: la - e.lw / 2, y: lc - 6 - e.lh, w: e.lw, h: e.lh, tx: la, ty: lc - 10, anchor: "middle" };
  }
});

// ── 自檢：線段有沒有穿過不相干的節點（規則 5） ─────
spec.edges.forEach((e) => {
  for (let k = 0; k < e.route.length - 1; k++) {
    const p = e.route[k],
      q = e.route[k + 1];
    for (const n of spec.nodes) {
      if (n.id === e.from || n.id === e.to) continue;
      const x1 = n.x - n.w / 2 + 1,
        x2 = n.x + n.w / 2 - 1,
        y1 = n.y - n.h / 2 + 1,
        y2 = n.y + n.h / 2 - 1;
      const sx1 = Math.min(p.x, q.x),
        sx2 = Math.max(p.x, q.x),
        sy1 = Math.min(p.y, q.y),
        sy2 = Math.max(p.y, q.y);
      if (sx2 > x1 && sx1 < x2 && sy2 > y1 && sy1 < y2) warn(`線 ${e.from}→${e.to} 穿過節點 ${n.id}`);
    }
  }
});

// ── 算 viewBox：內容 bbox 每邊 +24，寬高進位到 4 的倍數 ─────
let minX = Infinity,
  minY = Infinity,
  maxX = -Infinity,
  maxY = -Infinity;
const grow = (x1, y1, x2, y2) => {
  minX = Math.min(minX, x1);
  minY = Math.min(minY, y1);
  maxX = Math.max(maxX, x2);
  maxY = Math.max(maxY, y2);
};
spec.nodes.forEach((n) => grow(n.x - n.w / 2, n.y - n.h / 2, n.x + n.w / 2, n.y + n.h / 2));
spec.edges.forEach((e) => {
  e.route.forEach((p) => grow(p.x, p.y, p.x, p.y));
  if (e.lab) grow(e.lab.x, e.lab.y, e.lab.x + e.lab.w, e.lab.y + e.lab.h);
});
const groupBoxes = spec.groups.map((gr) => {
  const d = g.node("__grp_" + gr.id);
  const b = { gr, x: d.x - d.width / 2, y: d.y - d.height / 2, w: d.width, h: d.height };
  grow(b.x, b.y - 8, b.x + b.w, b.y + b.h);
  return b;
});
const PAD = 24;
const ox = PAD - minX,
  oy = PAD - minY;
const W = Math.ceil((maxX - minX + 2 * PAD) / 4) * 4;
const H = Math.ceil((maxY - minY + 2 * PAD) / 4) * 4;
const X = (v) => +(v + ox).toFixed(1);
const Y = (v) => +(v + oy).toFixed(1);

// ── 輸出 SVG ──────────────────────────────────────
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
function roundedPath(pts, r0 = 8) {
  let d = `M ${X(pts[0].x)},${Y(pts[0].y)}`;
  for (let k = 1; k < pts.length - 1; k++) {
    const a = pts[k - 1],
      b = pts[k],
      c = pts[k + 1];
    const l1 = Math.hypot(b.x - a.x, b.y - a.y),
      l2 = Math.hypot(c.x - b.x, c.y - b.y);
    const r = Math.max(0, Math.min(r0, l1 / 2, l2 / 2));
    const p1 = { x: b.x - ((b.x - a.x) / l1) * r, y: b.y - ((b.y - a.y) / l1) * r };
    const p2 = { x: b.x + ((c.x - b.x) / l2) * r, y: b.y + ((c.y - b.y) / l2) * r };
    d += ` L ${X(p1.x)},${Y(p1.y)} Q ${X(b.x)},${Y(b.y)} ${X(p2.x)},${Y(p2.y)}`;
  }
  const z = pts[pts.length - 1];
  return d + ` L ${X(z.x)},${Y(z.y)}`;
}
const cls = "ad-" + SLUG;
const S = `svg.${cls}`;
const kindOf = (n) => n.kind || (n.accent ? "accent" : { box: "step", round: "terminal", diamond: "decision", dashed: "optional" }[n.shape]);
const nodeCls = (n) => ["box", n.shape === "dashed" ? "opt" : "", n.shape === "round" ? "term" : "", n.accent ? "acc" : ""].filter(Boolean).join(" ");

const out = [];
const explore = flag("--explore");
if (explore) out.push(`<div class="xp" data-explore>`);
out.push(`<div class="figure ad-fig">`);
out.push(`<style>
  /* layout-diagram.mjs 產生：顏色只用頁面 token，深色主題或品牌換色會跟著變 */
  div.ad-fig { width: 100%; max-width: 100%; min-width: 0; overflow-x: auto; background: var(--ivory); border: 1px solid var(--g300); border-radius: 10px; }
  ${S} { display: block; width: ${W}px; max-width: none; height: auto; margin: 0 auto; font-family: var(--sans); }
  ${S} .bg, ${S} .mask { fill: var(--ivory); }
  ${S} .box { fill: var(--paper); stroke: var(--g500); stroke-width: 1.2; }
  ${S} .box.term { fill: var(--g100); }
  ${S} .box.opt { stroke-dasharray: 4 3; }
  ${S} .box.acc { fill: var(--clay-soft); stroke: var(--clay); stroke-width: 1.5; }
  ${S} .ln { fill: none; stroke: var(--g500); stroke-width: 1.4; }
  ${S} .ln.dash { stroke-dasharray: 5 4; }
  ${S} .ln.acc { stroke: var(--clay-d); stroke-width: 1.6; }
  ${S} .hit { fill: none; stroke: transparent; stroke-width: 14; }
  ${S} .grp { fill: var(--slate); fill-opacity: 0.02; stroke: var(--g300); stroke-dasharray: 4 4; }
  ${S} .mk { fill: var(--g500); }
  ${S} .mk.acc { fill: var(--clay-d); }
  ${S} text { font-size: ${LS}px; fill: var(--g700); }
  ${S} text.n { font-size: ${FS}px; font-weight: 600; fill: var(--slate); }
  ${S} text.gl { font-size: ${LS}px; font-weight: 600; fill: var(--g500); }
</style>`);
out.push(
  `<svg class="${cls}${explore ? " xplore" : ""}" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-labelledby="${SLUG}-title${spec.desc ? ` ${SLUG}-desc` : ""}">`,
);
out.push(`  <title id="${SLUG}-title">${esc(TITLE)}</title>`);
if (spec.desc) out.push(`  <desc id="${SLUG}-desc">${esc(spec.desc)}</desc>`);
out.push(`  <defs>
    <marker id="${SLUG}-arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon class="mk" points="0 0, 8 3, 0 6"/></marker>
    <marker id="${SLUG}-arrow-accent" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon class="mk acc" points="0 0, 8 3, 0 6"/></marker>
  </defs>`);
out.push(`  <rect class="bg" width="100%" height="100%"/>`);
// z-order：背景 → 分區 → 線 → 標籤 → 節點
groupBoxes.forEach((b) => {
  const lw = Math.ceil(textWidth(b.gr.label, LS, true)) + 8;
  out.push(`  <g class="group" data-id="grp-${esc(b.gr.id)}">`);
  out.push(`    <rect class="grp" x="${X(b.x)}" y="${Y(b.y)}" width="${b.w.toFixed(1)}" height="${b.h.toFixed(1)}" rx="8"/>`);
  out.push(`    <rect class="mask" x="${X(b.x + 12)}" y="${Y(b.y - 8)}" width="${lw}" height="16"/>`);
  out.push(`    <text class="gl" x="${X(b.x + 16)}" y="${Y(b.y + 4)}">${esc(b.gr.label)}</text>`);
  out.push(`  </g>`);
});
spec.edges.forEach((e) => {
  const d = roundedPath(e.route);
  const mk = e.style === "accent" ? `${SLUG}-arrow-accent` : `${SLUG}-arrow`;
  const lc = e.style === "dashed" ? " dash" : e.style === "accent" ? " acc" : "";
  out.push(`  <g class="edge" data-from="${esc(e.from)}" data-to="${esc(e.to)}" data-label="${esc(e.label || "")}">`);
  out.push(`    <path class="hit" d="${d}"/>`);
  out.push(`    <path class="ln${lc}" d="${d}" marker-end="url(#${mk})"/>`);
  out.push(`  </g>`);
});
spec.edges.forEach((e) => {
  if (!e.lab) return;
  const l = e.lab;
  out.push(`  <g class="elabel">`);
  out.push(`    <rect class="mask" x="${X(l.x)}" y="${Y(l.y)}" width="${l.w}" height="${l.h}"/>`);
  out.push(`    <text x="${X(l.tx)}" y="${Y(l.ty)}"${l.anchor === "middle" ? ' text-anchor="middle"' : ""}>${esc(e.label)}</text>`);
  out.push(`  </g>`);
});
spec.nodes.forEach((n) => {
  const title = n.lines.join("");
  out.push(`  <g class="node" data-id="${esc(n.id)}" data-kind="${esc(kindOf(n))}" data-title="${esc(title)}">`);
  const x0 = n.x - n.w / 2,
    y0 = n.y - n.h / 2;
  if (n.shape === "diamond") {
    const pts = [
      [n.x, n.y - n.h / 2],
      [n.x + n.w / 2, n.y],
      [n.x, n.y + n.h / 2],
      [n.x - n.w / 2, n.y],
    ]
      .map(([x, y]) => `${X(x)},${Y(y)}`)
      .join(" ");
    // x／y 屬性對多邊形無作用，只給探索層找路徑編號的位置用（放在左角）
    out.push(`    <polygon class="${nodeCls(n)}" points="${pts}" x="${X(x0)}" y="${Y(n.y)}"/>`);
  } else {
    const rx = n.shape === "round" ? n.h / 2 : 6;
    out.push(`    <rect class="${nodeCls(n)}" x="${X(x0)}" y="${Y(y0)}" width="${n.w}" height="${n.h}" rx="${rx}"/>`);
  }
  const top = n.y - n.th / 2;
  const spans = n.lines
    .map((l, k) => `<tspan x="${X(n.x)}" y="${Y(top + LH * k + LH / 2 + 4.5)}">${esc(l)}</tspan>`)
    .join("");
  out.push(`    <text class="n" text-anchor="middle">${spans}</text>`);
  out.push(`  </g>`);
});
out.push(`</svg>`);
out.push(`</div>`);
if (explore) out.push(`</div>`);

const html = out.join("\n") + "\n";
const outFile = opt("-o");
if (outFile) {
  fs.writeFileSync(outFile, html);
  console.error(`✓ ${spec.nodes.length} 個節點、${spec.edges.length} 條線 → ${outFile}（viewBox ${W}×${H}）`);
} else process.stdout.write(html);
