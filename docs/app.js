const tabs = document.querySelectorAll(".tab");
const panels = document.querySelectorAll(".panel");

function activateTab(name) {
  tabs.forEach((tab) => {
    tab.setAttribute("aria-selected", String(tab.dataset.tab === name));
  });
  panels.forEach((panel) => {
    panel.hidden = panel.id !== `panel-${name}`;
  });
}

tabs.forEach((tab) => {
  tab.addEventListener("click", () => activateTab(tab.dataset.tab));
});

const SVG_NS = "http://www.w3.org/2000/svg";
const STRESS_COLOURS = { ok: "var(--colour-stress-ok)", watch: "var(--colour-stress-watch)", act: "var(--colour-stress-act)" };

function renderMetrics(derived) {
  document.querySelectorAll("[data-metric]").forEach((el) => {
    const value = derived.headline_metrics[el.dataset.metric];
    if (value !== undefined) el.textContent = value;
  });
}

function renderBedMap(plantingMap, derived) {
  const stressByBed = Object.fromEntries(derived.beds.map((b) => [b.bed_id, b.stress]));
  const { width_m, length_m } = plantingMap.plot;
  const flipY = (y_m, h_m) => length_m - y_m - h_m;

  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${width_m} ${length_m}`);

  plantingMap.infrastructure.forEach((item) => {
    const { x_m, y_m, w_m, h_m } = item.position;
    const rect = document.createElementNS(SVG_NS, "rect");
    rect.setAttribute("x", x_m);
    rect.setAttribute("y", flipY(y_m, h_m));
    rect.setAttribute("width", w_m);
    rect.setAttribute("height", h_m);
    rect.setAttribute("class", "bed-map-infra");
    const title = document.createElementNS(SVG_NS, "title");
    title.textContent = item.name;
    rect.appendChild(title);
    svg.appendChild(rect);
  });

  plantingMap.beds.forEach((bed) => {
    const { x_m, y_m, w_m, h_m } = bed.position;
    const stress = stressByBed[bed.id];
    const rect = document.createElementNS(SVG_NS, "rect");
    rect.setAttribute("x", x_m);
    rect.setAttribute("y", flipY(y_m, h_m));
    rect.setAttribute("width", w_m);
    rect.setAttribute("height", h_m);
    rect.setAttribute("fill", STRESS_COLOURS[stress] || "#ccc");
    rect.setAttribute("class", "bed-map-bed");
    const title = document.createElementNS(SVG_NS, "title");
    title.textContent = `${bed.name} — ${stress}`;
    rect.appendChild(title);
    svg.appendChild(rect);
  });

  document.getElementById("bed-map-svg").replaceChildren(svg);
}

function renderAdvice(derived) {
  const container = document.getElementById("advice-content");
  container.replaceChildren();

  const headline = document.createElement("p");
  headline.className = "advice-headline";
  headline.textContent = derived.advice.headline;
  container.appendChild(headline);

  const why = document.createElement("ul");
  why.className = "advice-why";
  derived.advice.why.forEach((reason) => {
    const li = document.createElement("li");
    li.textContent = reason;
    why.appendChild(li);
  });
  container.appendChild(why);
}

function cumulative(values) {
  let running = 0;
  return values.map((v) => (running += v));
}

function renderTrendsChart(derived) {
  const series = derived.daily_series;
  const labels = series.map((d) => d.date);
  const cumEt = cumulative(series.map((d) => d.et_mm));
  const cumSiteRain = cumulative(series.map((d) => d.rain_site_mm));
  const cumRegionalRain = cumulative(series.map((d) => d.rain_regional_mm));

  // Mark the day the site-vs-regional rain gap is widest — a single highlighted
  // point on the shared x-axis, no chart plugin required.
  let maxGapIndex = 0;
  let maxGap = -Infinity;
  cumSiteRain.forEach((v, i) => {
    const gap = cumRegionalRain[i] - v;
    if (gap > maxGap) {
      maxGap = gap;
      maxGapIndex = i;
    }
  });
  const divergenceMarker = series.map((_, i) => (i === maxGapIndex ? cumSiteRain[i] : null));

  new Chart(document.getElementById("trends-chart"), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Cumulative ET (mm)",
          data: cumEt,
          borderColor: "#d9534f",
          backgroundColor: "rgba(217, 83, 79, 0.12)",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.15,
        },
        {
          label: "Cumulative site rain (mm)",
          data: cumSiteRain,
          borderColor: "#3f7d3f",
          backgroundColor: "rgba(63, 125, 63, 0.15)",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.15,
          fill: 0,
        },
        {
          label: "Cumulative regional rain (mm)",
          data: cumRegionalRain,
          borderColor: "#6b6b62",
          borderDash: [5, 4],
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.15,
          fill: false,
        },
        {
          label: "Widest site-vs-regional gap",
          data: divergenceMarker,
          borderColor: "transparent",
          backgroundColor: "#e8b64c",
          pointRadius: 6,
          pointHoverRadius: 7,
          showLine: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        y: { title: { display: true, text: "mm, cumulative" } },
      },
      plugins: {
        legend: { position: "bottom" },
      },
    },
  });

  document.getElementById("trends-note").textContent =
    `Widest divergence on ${labels[maxGapIndex]}: ${maxGap.toFixed(1)} mm more fell regionally than on site, cumulative to that day. The shaded band is the site's water deficit (ET ahead of rainfall).`;
}

// Minimal parser for the briefing's fixed, constrained subset of markdown
// (headings, bullets, one table, plain paragraphs, a footer line) — see
// contracts/briefing.format.md rule 5. Not a general markdown renderer.
function parseBriefing(markdown) {
  const root = document.createDocumentFragment();
  let paragraphBuffer = [];
  let list = null;
  let table = null;
  let tableBody = null;

  const flushParagraph = () => {
    if (paragraphBuffer.length) {
      const p = document.createElement("p");
      p.textContent = paragraphBuffer.join(" ");
      root.appendChild(p);
      paragraphBuffer = [];
    }
  };
  const flushList = () => {
    if (list) {
      root.appendChild(list);
      list = null;
    }
  };
  const flushTable = () => {
    if (table) {
      root.appendChild(table);
      table = null;
      tableBody = null;
    }
  };
  const flushAll = () => {
    flushParagraph();
    flushList();
    flushTable();
  };

  markdown.replace(/\r\n/g, "\n").split("\n").forEach((line) => {
    if (line.startsWith("# ")) {
      flushAll();
      const h1 = document.createElement("h1");
      h1.textContent = line.slice(2).trim();
      root.appendChild(h1);
    } else if (line.startsWith("## ")) {
      flushAll();
      const h2 = document.createElement("h2");
      h2.textContent = line.slice(3).trim();
      root.appendChild(h2);
    } else if (line.startsWith("- ")) {
      flushParagraph();
      flushTable();
      if (!list) list = document.createElement("ul");
      const li = document.createElement("li");
      li.textContent = line.slice(2).trim();
      list.appendChild(li);
    } else if (line.startsWith("|")) {
      flushParagraph();
      flushList();
      const cells = line.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      if (cells.every((c) => /^-+$/.test(c))) return; // header separator row
      if (!table) {
        table = document.createElement("table");
        const thead = document.createElement("thead");
        const headRow = document.createElement("tr");
        cells.forEach((c) => {
          const th = document.createElement("th");
          th.textContent = c;
          headRow.appendChild(th);
        });
        thead.appendChild(headRow);
        table.appendChild(thead);
        tableBody = document.createElement("tbody");
        table.appendChild(tableBody);
      } else {
        const row = document.createElement("tr");
        cells.forEach((c) => {
          const td = document.createElement("td");
          td.textContent = c;
          row.appendChild(td);
        });
        tableBody.appendChild(row);
      }
    } else if (line.startsWith("Generated by ")) {
      flushAll();
      const footer = document.createElement("p");
      footer.className = "briefing-footer";
      footer.textContent = line.trim();
      root.appendChild(footer);
    } else if (line.trim() === "") {
      flushAll();
    } else {
      paragraphBuffer.push(line.trim());
    }
  });
  flushAll();
  return root;
}

async function loadBriefing() {
  const text = await fetch("data/briefing.md").then((r) => r.text());
  document.getElementById("briefing-content").replaceChildren(parseBriefing(text));
}

async function loadOverview() {
  const [plantingMap, derived] = await Promise.all([
    fetch("data/planting_map.json").then((r) => r.json()),
    fetch("data/derived.json").then((r) => r.json()),
  ]);
  renderMetrics(derived);
  renderBedMap(plantingMap, derived);
  renderAdvice(derived);
  renderTrendsChart(derived);
}

loadOverview().catch((err) => console.error("Failed to load overview data:", err));
loadBriefing().catch((err) => console.error("Failed to load briefing:", err));
