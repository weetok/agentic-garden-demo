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

async function loadOverview() {
  const [plantingMap, derived] = await Promise.all([
    fetch("data/planting_map.json").then((r) => r.json()),
    fetch("data/derived.json").then((r) => r.json()),
  ]);
  renderMetrics(derived);
  renderBedMap(plantingMap, derived);
  renderAdvice(derived);
}

loadOverview().catch((err) => console.error("Failed to load overview data:", err));
