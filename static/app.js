const API_SEARCH = "/api/search";
const API_AIRPORTS = "/api/airports";

const createElement = (tag, className) => {
  const el = document.createElement(tag);
  if (className) el.className = className;
  return el;
};

const debounce = (fn, delay = 300) => {
  let timeout;
  return (...args) => {
    clearTimeout(timeout);
    timeout = setTimeout(() => fn(...args), delay);
  };
};

class AirportSelector {
  constructor(container, options = {}) {
    this.container = container;
    this.tagsEl = container.querySelector(".tags");
    this.input = container.querySelector("input");
    this.dropdown = container.querySelector(".dropdown");
    this.allowEverywhere = options.allowEverywhere;
    this.selected = [];
    this.results = [];

    this.input.addEventListener("input", debounce(this.handleInput.bind(this)));
    this.input.addEventListener("focus", () => {
      if (this.results.length) {
        this.showDropdown();
      }
    });

    document.addEventListener("click", (event) => {
      if (!this.container.contains(event.target)) {
        this.hideDropdown();
      }
    });

    if (options.defaults) {
      options.defaults.forEach((item) => this.addTag(item));
    }
  }

  async handleInput(event) {
    const query = event.target.value.trim();
    if (query.length < 2) {
      this.hideDropdown();
      return;
    }

    const response = await fetch(`${API_AIRPORTS}?query=${encodeURIComponent(query)}`);
    if (!response.ok) {
      this.results = [];
      this.hideDropdown();
      return;
    }

    this.results = await response.json();
    this.renderDropdown();
  }

  renderDropdown() {
    this.dropdown.innerHTML = "";

    if (this.allowEverywhere && this.selected.length === 0) {
      const li = createElement("li");
      li.textContent = "🌍 Ovunque (cerca in tutto il mondo)";
      li.addEventListener("click", () => {
        this.selected = [];
        this.addTag({
          code: "EVERYWHERE",
          label: "Ovunque",
          title: "Ovunque",
          entityType: "SPECIAL",
        });
        this.input.value = "";
        this.hideDropdown();
      });
      this.dropdown.appendChild(li);
    }

    this.results.forEach((airport) => {
      const li = createElement("li");
      const icon = this.getEntityIcon(airport.entityType);
      const title = `${icon} ${airport.title} (${airport.skyId})`;
      const meta = airport.subtitle ? ` - ${airport.subtitle}` : "";
      li.innerHTML = `<span>${title}</span><span class="meta">${meta}</span>`;
      li.addEventListener("click", () => {
        this.addTag({
          code: airport.skyId,
          label: airport.skyId,
          title: airport.title,
          entityType: airport.entityType,
        });
        this.input.value = "";
        this.hideDropdown();
      });
      this.dropdown.appendChild(li);
    });

    if (this.dropdown.children.length) {
      this.showDropdown();
    } else {
      this.hideDropdown();
    }
  }

  getEntityIcon(type) {
    const icons = {
      AIRPORT: "✈️",
      CITY: "🏙️",
      COUNTRY: "🌍",
    };
    return icons[type] || "📍";
  }

  showDropdown() {
    this.dropdown.classList.add("show");
  }

  hideDropdown() {
    this.dropdown.classList.remove("show");
  }

  addTag({ code, label, title, entityType }) {
    if (code === "EVERYWHERE") {
      this.selected = [
        { code, label: "Ovunque", title: "Ovunque", entityType: "SPECIAL" },
      ];
      this.renderTags();
      return;
    }

    if (this.selected.some((item) => item.code === code)) {
      return;
    }

    this.selected = this.selected.filter((item) => item.code !== "EVERYWHERE");
    this.selected.push({
      code,
      label: label || code,
      title: title || label || code,
      entityType: entityType || "",
    });
    this.renderTags();
  }

  removeTag(code) {
    this.selected = this.selected.filter((item) => item.code !== code);
    this.renderTags();
  }

  renderTags() {
    this.tagsEl.innerHTML = "";
    this.selected.forEach((item) => {
      const tag = createElement("span", "tag");
      tag.textContent = item.label;
      const button = createElement("button");
      button.type = "button";
      button.textContent = "×";
      button.addEventListener("click", () => this.removeTag(item.code));
      tag.appendChild(button);
      this.tagsEl.appendChild(tag);
    });
  }

  getCodes() {
    return this.selected.map((item) => item.code);
  }

  getItems() {
    return this.selected.map((item) => ({
      code: item.code,
      entityType: item.entityType || "",
      title: item.title || item.label || item.code,
    }));
  }

  hasEverywhere() {
    return this.selected.some((item) => item.code === "EVERYWHERE");
  }

  swapWith(other) {
    if (other.hasEverywhere()) {
      return;
    }
    const temp = [...this.selected];
    this.selected = [...other.selected];
    other.selected = temp;
    this.renderTags();
    other.renderTags();
  }
}

const formatStats = (stats) => {
  if (!stats) return "";
  const parts = [];
  if (stats.paesi !== undefined) {
    parts.push(`Paesi: ${stats.paesi}`);
  }
  if (stats.città !== undefined) {
    parts.push(`Città: ${stats.città}`);
  }
  if (stats.partenze) {
    parts.push(`Partenze: ${stats.partenze}`);
  }
  if (stats.destinazioni) {
    parts.push(`Destinazioni: ${stats.destinazioni}`);
  }
  return parts.join(" | ");
};

const getInitials = (name) => {
  const words = name.split(" ");
  if (words.length >= 2) {
    return (words[0][0] + words[1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
};

const airlineColors = [
  "#1a4fd6",
  "#e94560",
  "#10b981",
  "#f59e0b",
  "#8b5cf6",
  "#06b6d4",
];

const getAirlineColor = (name) => {
  const index = Math.abs(hashCode(name)) % airlineColors.length;
  return airlineColors[index];
};

const hashCode = (str) => {
  let hash = 0;
  for (let i = 0; i < str.length; i += 1) {
    hash = (hash << 5) - hash + str.charCodeAt(i);
    hash |= 0;
  }
  return hash;
};

const renderFlights = (flights, container) => {
  container.innerHTML = "";

  if (!flights.length) {
    const empty = createElement("div", "card");
    empty.textContent = "Nessun volo trovato con i criteri selezionati.";
    container.appendChild(empty);
    return;
  }

  flights.forEach((flight) => {
    const card = createElement("div", "flight-card");
    const top = createElement("div", "flight-top");

    const airline = createElement("div", "airline");
    const logo = createElement("div", "logo");
    logo.style.background = getAirlineColor(flight.compagnia || "");
    logo.textContent = getInitials(flight.compagnia || "NA");
    airline.appendChild(logo);
    const airlineName = createElement("span");
    airlineName.textContent = flight.compagnia || "N/A";
    airline.appendChild(airlineName);

    const times = createElement("div", "times");
    const dep = createElement("div", "time-block");
    dep.innerHTML = `<strong>${flight.partenza}</strong><span>${flight.codice_origine}</span>`;
    const duration = createElement("div", "time-block");
    duration.innerHTML = `<div class="stops">${flight.durata}</div><div class="line"></div><div class="stops">${flight.scali === 0 ? "Diretto" : `${flight.scali} scalo`}</div>`;
    const arr = createElement("div", "time-block");
    arr.innerHTML = `<strong>${flight.arrivo}</strong><span>${flight.codice_dest}</span>`;
    times.append(dep, duration, arr);

    const price = createElement("div", "price");
    price.innerHTML = `<strong>€ ${Math.round(flight.prezzo)}</strong><span>${flight.città} ${flight.paese}</span>`;

    top.append(airline, times, price);
    card.appendChild(top);

    if (flight.stopovers && flight.stopovers.length) {
      const stopovers = createElement("div", "stopovers");
      flight.stopovers.forEach((stop) => {
        const line = createElement("span");
        line.innerHTML = `<span class="icon">✈</span>Scalo a ${stop.città}${stop.codice ? ` (${stop.codice})` : ""}: arrivo ${stop.arrivo}${stop.partenza ? ` → ripartenza ${stop.partenza}` : ""}${stop.attesa ? ` (attesa ${stop.attesa})` : ""}`;
        stopovers.appendChild(line);
      });
      card.appendChild(stopovers);
    }

    container.appendChild(card);
  });
};

const describeSelection = (items, fallback) => {
  if (!items.length) return fallback;
  return items.map((item) => item.title || item.code).join(", ");
};

const buildSearchMessages = (origins, destinations) => {
  const hasEverywhere = destinations.some((item) => item.code === "EVERYWHERE");
  const countries = destinations.filter((item) => item.entityType === "COUNTRY");
  const airports = destinations.filter(
    (item) => item.entityType === "AIRPORT" || item.entityType === "CITY"
  );
  const originLabel = describeSelection(origins, "partenze selezionate");
  const destinationLabel = hasEverywhere
    ? "tutto il mondo"
    : describeSelection(destinations, "destinazioni selezionate");
  const countryLabel = countries.length
    ? describeSelection(countries, "paese selezionato")
    : "";
  const airportLabel = airports.length
    ? describeSelection(airports, "destinazioni selezionate")
    : "";

  const messages = [
    `Sto cercando voli da ${originLabel} verso ${destinationLabel}...`,
  ];

  if (countries.length) {
    messages.push(
      `Sto espandendo il paese ${countryLabel} in città e aeroporti...`
    );
  }

  if (airports.length && !hasEverywhere) {
    messages.push(`Sto interrogando ${airportLabel}...`);
  } else if (!hasEverywhere) {
    messages.push("Sto interrogando le destinazioni selezionate...");
  }

  messages.push("Quasi fatto, sto ordinando i risultati...");
  return messages;
};

const startStatusRotation = (statusTitle, statusSubtitle, messages) => {
  let index = 0;
  const startedAt = Date.now();

  statusTitle.textContent = messages[index] || "Ricerca in corso...";
  statusSubtitle.textContent = "In corso da 0s";

  const intervalId = setInterval(() => {
    index = (index + 1) % messages.length;
    const elapsedSeconds = Math.floor((Date.now() - startedAt) / 1000);
    statusTitle.textContent = messages[index];
    statusSubtitle.textContent = `In corso da ${elapsedSeconds}s`;
  }, 1800);

  return () => clearInterval(intervalId);
};

const init = () => {
  const originSelector = new AirportSelector(
    document.getElementById("origin-selector"),
    {
      allowEverywhere: false,
      defaults: [{ code: "VCE", label: "VCE", title: "Venezia" }],
    }
  );

  const destSelector = new AirportSelector(document.getElementById("dest-selector"), {
    allowEverywhere: true,
    defaults: [{ code: "EVERYWHERE", label: "Ovunque", title: "Ovunque" }],
  });

  const swapBtn = document.getElementById("swap-btn");
  swapBtn.addEventListener("click", () => {
    originSelector.swapWith(destSelector);
  });

  const form = document.getElementById("search-form");
  const departDateInput = document.getElementById("depart-date");
  const maxPriceInput = document.getElementById("max-price");
  const minHourInput = document.getElementById("min-hour");
  const directOnlyInput = document.getElementById("direct-only");
  const sameDayInput = document.getElementById("same-day");
  const statusTitle = document.getElementById("status-title");
  const statusSubtitle = document.getElementById("status-subtitle");
  const statsEl = document.getElementById("stats");
  const resultsEl = document.getElementById("results");
  const searchBtn = document.getElementById("search-btn");

  const setDefaultDate = () => {
    const date = new Date();
    date.setDate(date.getDate() + 30);
    const day = String(date.getDate()).padStart(2, "0");
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const year = date.getFullYear();
    departDateInput.value = `${year}-${month}-${day}`;
  };
  setDefaultDate();

  let lastFlights = [];
  let stopStatusRotation = null;

  const getSortValue = () => {
    const selected = document.querySelector("input[name='sort']:checked");
    return selected ? selected.value : "prezzo";
  };

  const sortFlights = (flights, sortValue) => {
    const copy = [...flights];
    if (sortValue === "orario") {
      return copy.sort((a, b) => a.partenza.localeCompare(b.partenza));
    }
    if (sortValue === "durata") {
      return copy.sort((a, b) => (a.durata_min || 0) - (b.durata_min || 0));
    }
    return copy.sort((a, b) => (a.prezzo || 0) - (b.prezzo || 0));
  };

  document.querySelectorAll("input[name='sort']").forEach((radio) => {
    radio.addEventListener("change", () => {
      const sorted = sortFlights(lastFlights, getSortValue());
      renderFlights(sorted, resultsEl);
    });
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    statusSubtitle.textContent = "";
    statsEl.textContent = "";
    resultsEl.innerHTML = "";

    const origins = originSelector.getItems();
    const destinations = destSelector.getItems();

    if (!origins.length) {
      statusTitle.textContent = "Seleziona almeno un aeroporto di partenza.";
      return;
    }

    searchBtn.disabled = true;
    if (stopStatusRotation) {
      stopStatusRotation();
    }
    const statusMessages = buildSearchMessages(origins, destinations);
    stopStatusRotation = startStatusRotation(
      statusTitle,
      statusSubtitle,
      statusMessages
    );

    const formattedDate = departDateInput.value
      ? departDateInput.value.split("-").reverse().join("/")
      : "";
    const payload = {
      origins,
      destinations,
      search_everywhere: destSelector.hasEverywhere() || destinations.length === 0,
      depart_date: formattedDate,
      max_price: maxPriceInput.value,
      min_hour: minHourInput.value,
      direct_only: directOnlyInput.checked,
      same_day: sameDayInput.checked,
      sort: getSortValue(),
    };

    try {
      const response = await fetch(API_SEARCH, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (!response.ok) {
        statusTitle.textContent = data.error || "Errore durante la ricerca.";
        statusSubtitle.textContent = "";
        searchBtn.disabled = false;
        return;
      }

      if (stopStatusRotation) {
        stopStatusRotation();
        stopStatusRotation = null;
      }
      statusTitle.textContent = `Trovati ${data.count} voli`;
      statusSubtitle.textContent = data.search_everywhere
        ? "Risultati ovunque"
        : "Risultati su destinazioni selezionate";
      statsEl.textContent = formatStats(data.stats);

      lastFlights = data.flights || [];
      const sorted = sortFlights(lastFlights, getSortValue());
      renderFlights(sorted, resultsEl);
    } catch (error) {
      statusTitle.textContent = "Errore durante la ricerca.";
      statusSubtitle.textContent = "";
    } finally {
      searchBtn.disabled = false;
      if (stopStatusRotation) {
        stopStatusRotation();
        stopStatusRotation = null;
      }
    }
  });
};

window.addEventListener("DOMContentLoaded", init);
