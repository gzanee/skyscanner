const API_SEARCH_STREAM = "/api/search/stream";
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

// Time Range Slider Class
class TimeRangeSlider {
  constructor(container, options = {}) {
    this.container = container;
    this.minValue = options.min || 0;
    this.maxValue = options.max || 24;
    this.step = options.step || 0.5; // 30 minute increments
    this.currentMin = options.initialMin ?? this.minValue;
    this.currentMax = options.initialMax ?? this.maxValue;

    this.track = container.querySelector(".time-range-track");
    this.selected = container.querySelector(".time-range-selected");
    this.thumbMin = container.querySelector(".thumb-min");
    this.thumbMax = container.querySelector(".thumb-max");

    this.labelMin = container.parentElement.querySelector(".time-label-min");
    this.labelMax = container.parentElement.querySelector(".time-label-max");

    this.minInput = options.minInput;
    this.maxInput = options.maxInput;

    this.dragging = null;

    this.init();
  }

  init() {
    this.thumbMin.addEventListener("mousedown", (e) => this.startDrag(e, "min"));
    this.thumbMax.addEventListener("mousedown", (e) => this.startDrag(e, "max"));
    this.thumbMin.addEventListener("touchstart", (e) => this.startDrag(e, "min"), { passive: false });
    this.thumbMax.addEventListener("touchstart", (e) => this.startDrag(e, "max"), { passive: false });

    document.addEventListener("mousemove", (e) => this.onDrag(e));
    document.addEventListener("mouseup", () => this.endDrag());
    document.addEventListener("touchmove", (e) => this.onDrag(e), { passive: false });
    document.addEventListener("touchend", () => this.endDrag());

    // Click on track to move nearest thumb
    this.container.addEventListener("click", (e) => this.onTrackClick(e));

    this.update();
  }

  startDrag(e, type) {
    e.preventDefault();
    this.dragging = type;
    const thumb = type === "min" ? this.thumbMin : this.thumbMax;
    thumb.classList.add("dragging");
  }

  endDrag() {
    if (this.dragging) {
      const thumb = this.dragging === "min" ? this.thumbMin : this.thumbMax;
      thumb.classList.remove("dragging");
      this.dragging = null;
    }
  }

  onDrag(e) {
    if (!this.dragging) return;
    e.preventDefault();

    const clientX = e.touches ? e.touches[0].clientX : e.clientX;
    const rect = this.container.getBoundingClientRect();
    const percent = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    const rawValue = this.minValue + percent * (this.maxValue - this.minValue);
    const value = Math.round(rawValue / this.step) * this.step;

    if (this.dragging === "min") {
      this.currentMin = Math.min(value, this.currentMax - this.step);
      this.currentMin = Math.max(this.minValue, this.currentMin);
    } else {
      this.currentMax = Math.max(value, this.currentMin + this.step);
      this.currentMax = Math.min(this.maxValue, this.currentMax);
    }

    this.update();
  }

  onTrackClick(e) {
    if (this.dragging) return;
    if (e.target.classList.contains("time-range-thumb")) return;

    const rect = this.container.getBoundingClientRect();
    const percent = (e.clientX - rect.left) / rect.width;
    const rawValue = this.minValue + percent * (this.maxValue - this.minValue);
    const value = Math.round(rawValue / this.step) * this.step;

    const distToMin = Math.abs(value - this.currentMin);
    const distToMax = Math.abs(value - this.currentMax);

    if (distToMin <= distToMax && value < this.currentMax) {
      this.currentMin = Math.max(this.minValue, value);
    } else if (value > this.currentMin) {
      this.currentMax = Math.min(this.maxValue, value);
    }

    this.update();
  }

  update() {
    const range = this.maxValue - this.minValue;
    const minPercent = ((this.currentMin - this.minValue) / range) * 100;
    const maxPercent = ((this.currentMax - this.minValue) / range) * 100;

    this.thumbMin.style.left = `${minPercent}%`;
    this.thumbMax.style.left = `${maxPercent}%`;

    this.selected.style.left = `${minPercent}%`;
    this.selected.style.width = `${maxPercent - minPercent}%`;

    const minTime = this.formatTime(this.currentMin);
    const maxTime = this.formatTime(this.currentMax);

    this.labelMin.textContent = minTime;
    this.labelMax.textContent = maxTime;

    this.thumbMin.setAttribute("data-tooltip", minTime);
    this.thumbMax.setAttribute("data-tooltip", maxTime);

    if (this.minInput) {
      this.minInput.value = Math.floor(this.currentMin);
    }
    if (this.maxInput) {
      this.maxInput.value = Math.ceil(this.currentMax);
    }
  }

  formatTime(value) {
    const hours = Math.floor(value);
    const minutes = Math.round((value - hours) * 60);
    return `${hours.toString().padStart(2, "0")}:${minutes.toString().padStart(2, "0")}`;
  }

  getValues() {
    return {
      min: this.currentMin,
      max: this.currentMax,
      minHour: Math.floor(this.currentMin),
      maxHour: Math.ceil(this.currentMax),
    };
  }
}

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

  const buildStopovers = (stopovers, className = "") => {
    if (!stopovers || !stopovers.length) return null;
    const stopoversEl = createElement("div", `stopovers ${className}`.trim());
    stopovers.forEach((stop) => {
      const line = createElement("span");
      line.innerHTML = `<span class="icon">✈</span>Scalo a ${stop.città}${stop.codice ? ` (${stop.codice})` : ""}: arrivo ${stop.arrivo}${stop.partenza ? ` → ripartenza ${stop.partenza}` : ""}${stop.attesa ? ` (attesa ${stop.attesa})` : ""}`;
      stopoversEl.appendChild(line);
    });
    return stopoversEl;
  };

  const buildLeg = ({
    compagnia,
    logo_url,
    partenza,
    arrivo,
    codice_origine,
    codice_dest,
    durata,
    scali,
  }, labelText, priceEl = null) => {
    const leg = createElement("div", "flight-leg");
    const label = createElement("span", "leg-label");
    label.textContent = labelText;
    leg.appendChild(label);

    const top = createElement("div", "flight-top");

    const airline = createElement("div", "airline");
    const logo = createElement("div", "logo");
    if (logo_url) {
      const img = createElement("img");
      img.src = logo_url;
      img.alt = compagnia || "Logo compagnia";
      img.loading = "lazy";
      logo.appendChild(img);
    } else {
      logo.style.background = getAirlineColor(compagnia || "");
      logo.textContent = getInitials(compagnia || "NA");
    }
    airline.appendChild(logo);
    const airlineName = createElement("span");
    airlineName.textContent = compagnia || "N/A";
    airline.appendChild(airlineName);

    const times = createElement("div", "times");
    const dep = createElement("div", "time-block");
    dep.innerHTML = `<strong>${partenza}</strong><span>${codice_origine}</span>`;
    const duration = createElement("div", "time-block");
    const stopCount = Number(scali || 0);
    const stopLabel = stopCount === 0 ? "Diretto" : `${stopCount} scalo`;
    let stopDots = "";
    if (stopCount > 0) {
      const dots = Array.from({ length: stopCount }, (_, index) => {
        const position = ((index + 1) / (stopCount + 1)) * 100;
        return `<span class="stop-dot" style="left: ${position}%"></span>`;
      });
      stopDots = dots.join("");
    }
    duration.innerHTML = `<div class="stops">${durata}</div><div class="line">${stopDots}</div><div class="stops">${stopLabel}</div>`;
    const arr = createElement("div", "time-block");
    arr.innerHTML = `<strong>${arrivo}</strong><span>${codice_dest}</span>`;
    times.append(dep, duration, arr);

    if (priceEl) {
      top.append(airline, times, priceEl);
    } else {
      top.classList.add("no-price");
      top.append(airline, times);
    }
    leg.appendChild(top);
    return leg;
  };

  const buildFlightCard = (flight) => {
    const card = createElement("div", "flight-card");
    const price = createElement("div", "price");
    const hasReturn = flight.prezzo_ritorno !== undefined && flight.prezzo_totale !== undefined;

    if (hasReturn) {
      price.innerHTML = `<strong>€ ${Math.round(flight.prezzo_totale)}</strong><span>Andata € ${Math.round(flight.prezzo)} • Ritorno € ${Math.round(flight.prezzo_ritorno)}</span>`;
    } else {
      price.innerHTML = `<strong>€ ${Math.round(flight.prezzo)}</strong>`;
    }

    const outboundLeg = buildLeg(
      {
        compagnia: flight.compagnia,
        logo_url: flight.logo_url,
        partenza: flight.partenza,
        arrivo: flight.arrivo,
        codice_origine: flight.codice_origine,
        codice_dest: flight.codice_dest,
        durata: flight.durata,
        scali: flight.scali,
      },
      "Andata",
      price
    );
    card.appendChild(outboundLeg);

    const outboundStopovers = buildStopovers(flight.stopovers);
    if (outboundStopovers) {
      card.appendChild(outboundStopovers);
    }

    if (hasReturn) {
      const returnLeg = buildLeg(
        {
          compagnia: flight.ritorno_compagnia,
          logo_url: flight.ritorno_logo_url,
          partenza: flight.ritorno_partenza,
          arrivo: flight.ritorno_arrivo,
          codice_origine: flight.ritorno_codice_origine,
          codice_dest: flight.ritorno_codice_dest,
          durata: flight.ritorno_durata,
          scali: flight.ritorno_scali,
        },
        "Ritorno"
      );
      returnLeg.classList.add("return-leg");
      card.appendChild(returnLeg);
      const returnStopovers = buildStopovers(flight.ritorno_stopovers, "return-stopovers");
      if (returnStopovers) {
        card.appendChild(returnStopovers);
      }
    }

    return card;
  };

  // Raggruppa voli per città
  const groupedByCity = {};
  flights.forEach((flight) => {
    const cityKey = `${flight.città || "Sconosciuta"}|${flight.paese || ""}`;
    if (!groupedByCity[cityKey]) {
      groupedByCity[cityKey] = {
        città: flight.città || "Sconosciuta",
        paese: flight.paese || "",
        flights: [],
        minPrice: Infinity,
      };
    }
    groupedByCity[cityKey].flights.push(flight);
    const flightPrice = flight.prezzo_totale ?? flight.prezzo ?? Infinity;
    if (flightPrice < groupedByCity[cityKey].minPrice) {
      groupedByCity[cityKey].minPrice = flightPrice;
    }
  });

  // Converti in array e ordina per prezzo minimo
  const cityGroups = Object.values(groupedByCity).sort((a, b) => a.minPrice - b.minPrice);

  // Se c'è una sola città, non usare accordion
  if (cityGroups.length === 1) {
    cityGroups[0].flights.forEach((flight) => {
      container.appendChild(buildFlightCard(flight));
    });
    return;
  }

  // Crea accordion per ogni città
  cityGroups.forEach((group, index) => {
    const accordion = createElement("div", "city-accordion");

    const header = createElement("div", "city-accordion-header");
    const isOpen = index === 0; // Prima città aperta di default

    const headerLeft = createElement("div", "city-accordion-left");
    const chevron = createElement("span", "city-accordion-chevron");
    chevron.innerHTML = "&#9662;"; // ▾
    const cityName = createElement("span", "city-accordion-name");
    cityName.textContent = group.paese ? `${group.città}, ${group.paese}` : group.città;
    headerLeft.append(chevron, cityName);

    const headerRight = createElement("div", "city-accordion-right");
    const flightCount = createElement("span", "city-accordion-count");
    flightCount.textContent = `${group.flights.length} ${group.flights.length === 1 ? "volo" : "voli"}`;
    const minPrice = createElement("span", "city-accordion-price");
    minPrice.textContent = `da € ${Math.round(group.minPrice)}`;
    headerRight.append(flightCount, minPrice);

    header.append(headerLeft, headerRight);

    const content = createElement("div", "city-accordion-content");
    if (isOpen) {
      accordion.classList.add("open");
    }

    group.flights.forEach((flight) => {
      content.appendChild(buildFlightCard(flight));
    });

    header.addEventListener("click", () => {
      accordion.classList.toggle("open");
    });

    accordion.append(header, content);
    container.appendChild(accordion);
  });
};

const formatProgressMessage = (payload) => {
  const base = payload.message || "Ricerca in corso...";
  if (payload.current && payload.total) {
    return `${base} (${payload.current}/${payload.total})`;
  }
  return base;
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

  // Initialize Time Range Sliders
  const departureSlider = new TimeRangeSlider(
    document.getElementById("time-range-slider-departure"),
    {
      min: 0,
      max: 24,
      step: 0.25,  // 15 minuti
      initialMin: 0,
      initialMax: 24,
      minInput: document.getElementById("min-hour"),
      maxInput: document.getElementById("max-hour"),
    }
  );

  const arrivalSlider = new TimeRangeSlider(
    document.getElementById("time-range-slider-arrival"),
    {
      min: 0,
      max: 24,
      step: 0.25,  // 15 minuti
      initialMin: 0,
      initialMax: 24,
      minInput: document.getElementById("min-arrival-hour"),
      maxInput: document.getElementById("max-arrival-hour"),
    }
  );

  const returnDepartureSlider = new TimeRangeSlider(
    document.getElementById("time-range-slider-return-departure"),
    {
      min: 0,
      max: 24,
      step: 0.25,
      initialMin: 0,
      initialMax: 24,
      minInput: document.getElementById("return-min-hour"),
      maxInput: document.getElementById("return-max-hour"),
    }
  );

  const returnArrivalSlider = new TimeRangeSlider(
    document.getElementById("time-range-slider-return-arrival"),
    {
      min: 0,
      max: 24,
      step: 0.25,
      initialMin: 0,
      initialMax: 24,
      minInput: document.getElementById("return-min-arrival-hour"),
      maxInput: document.getElementById("return-max-arrival-hour"),
    }
  );

  const form = document.getElementById("search-form");
  const departDateInput = document.getElementById("depart-date");
  const returnDateInput = document.getElementById("return-date");
  const returnDateField = document.getElementById("return-date-field");
  const returnTimeGroup = document.getElementById("return-time-group");
  const returnPriceField = document.getElementById("return-price-field");
  const totalPriceField = document.getElementById("total-price-field");
  const tripTypeInputs = document.querySelectorAll("input[name='trip-type']");
  const maxPriceInput = document.getElementById("max-price");
  const maxPriceReturnInput = document.getElementById("max-price-return");
  const maxPriceTotalInput = document.getElementById("max-price-total");
  const minHourInput = document.getElementById("min-hour");
  const maxHourInput = document.getElementById("max-hour");
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
    const returnDate = new Date(date);
    returnDate.setDate(returnDate.getDate() + 7);
    const returnDay = String(returnDate.getDate()).padStart(2, "0");
    const returnMonth = String(returnDate.getMonth() + 1).padStart(2, "0");
    const returnYear = returnDate.getFullYear();
    returnDateInput.value = `${returnYear}-${returnMonth}-${returnDay}`;
  };
  setDefaultDate();

  let lastFlights = [];
  let stopTimer = null;
  let lastFound = null;
  let startedAt = null;

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
    return copy.sort((a, b) => {
      const priceA = a.prezzo_totale ?? a.prezzo ?? 0;
      const priceB = b.prezzo_totale ?? b.prezzo ?? 0;
      return priceA - priceB;
    });
  };

  const updateTripVisibility = () => {
    const selected = document.querySelector("input[name='trip-type']:checked");
    const isRoundTrip = selected?.value === "round-trip";
    [returnDateField, returnTimeGroup, returnPriceField, totalPriceField].forEach((el) => {
      if (!el) return;
      el.classList.toggle("is-hidden", !isRoundTrip);
    });
    returnDateInput.disabled = !isRoundTrip;
    maxPriceReturnInput.disabled = !isRoundTrip;
    maxPriceTotalInput.disabled = !isRoundTrip;
  };

  tripTypeInputs.forEach((input) => {
    input.addEventListener("change", updateTripVisibility);
  });
  updateTripVisibility();

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
    if (stopTimer) {
      stopTimer();
    }
    startedAt = Date.now();
    lastFound = null;
    const updateSubtitle = () => {
      const elapsedSeconds = Math.floor((Date.now() - startedAt) / 1000);
      const foundText = lastFound !== null ? ` • ${lastFound} trovati` : "";
      statusSubtitle.textContent = `In corso da ${elapsedSeconds}s${foundText}`;
    };
    updateSubtitle();
    const intervalId = setInterval(updateSubtitle, 1000);
    stopTimer = () => clearInterval(intervalId);

    const formattedDate = departDateInput.value
      ? departDateInput.value.split("-").reverse().join("/")
      : "";
    const formattedReturnDate = returnDateInput.value
      ? returnDateInput.value.split("-").reverse().join("/")
      : "";
    
    const departureValues = departureSlider.getValues();
    const arrivalValues = arrivalSlider.getValues();
    const returnDepartureValues = returnDepartureSlider.getValues();
    const returnArrivalValues = returnArrivalSlider.getValues();
    const tripType = document.querySelector("input[name='trip-type']:checked")?.value || "one-way";
    
    const payload = {
      origins,
      destinations,
      search_everywhere: destSelector.hasEverywhere() || destinations.length === 0,
      depart_date: formattedDate,
      max_price: maxPriceInput.value,
      min_hour: departureValues.minHour,
      max_hour: departureValues.maxHour,
      min_arrival_hour: arrivalValues.minHour,
      max_arrival_hour: arrivalValues.maxHour,
      direct_only: directOnlyInput.checked,
      same_day: sameDayInput.checked,
      sort: getSortValue(),
      trip_type: tripType,
    };

    if (tripType === "round-trip") {
      payload.return_date = formattedReturnDate;
      payload.return_max_price = maxPriceReturnInput.value;
      payload.total_max_price = maxPriceTotalInput.value;
      payload.return_min_hour = returnDepartureValues.minHour;
      payload.return_max_hour = returnDepartureValues.maxHour;
      payload.return_min_arrival_hour = returnArrivalValues.minHour;
      payload.return_max_arrival_hour = returnArrivalValues.maxHour;
    }

    try {
      const response = await fetch(API_SEARCH_STREAM, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const data = await response.json();
        statusTitle.textContent = data.error || "Errore durante la ricerca.";
        statusSubtitle.textContent = "";
        return;
      }

      if (!response.body) {
        statusTitle.textContent = "Impossibile leggere lo stream della ricerca.";
        statusSubtitle.textContent = "";
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let completed = false;

      const handleEvent = (payload) => {
        if (payload.type === "progress") {
          statusTitle.textContent = formatProgressMessage(payload);
          if (payload.found !== undefined) {
            lastFound = payload.found;
          }
          updateSubtitle();
          return;
        }

        if (payload.type === "results") {
          const newFlights = payload.flights || [];
          if (newFlights.length) {
            lastFlights = lastFlights.concat(newFlights);
            const sorted = sortFlights(lastFlights, getSortValue());
            renderFlights(sorted, resultsEl);
          }
          if (payload.count !== undefined) {
            lastFound = payload.count;
            updateSubtitle();
          }
          return;
        }

        if (payload.type === "error") {
          statusTitle.textContent = payload.error || "Errore durante la ricerca.";
          statusSubtitle.textContent = "";
          completed = true;
          return;
        }

        if (payload.type === "complete") {
          completed = true;
          statusTitle.textContent = `Trovati ${payload.count} voli`;
          statusSubtitle.textContent = payload.search_everywhere
            ? "Risultati ovunque"
            : "Risultati su destinazioni selezionate";
          statsEl.textContent = formatStats(payload.stats);
          lastFlights = payload.flights || [];
          const sorted = sortFlights(lastFlights, getSortValue());
          renderFlights(sorted, resultsEl);
        }
      };

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        parts.forEach((part) => {
          const line = part
            .split("\n")
            .find((entry) => entry.startsWith("data:"));
          if (!line) return;
          const jsonStr = line.replace(/^data:\s*/, "");
          try {
            const payload = JSON.parse(jsonStr);
            handleEvent(payload);
          } catch (error) {
            // ignore malformed chunks
          }
        });
      }

      if (!completed && buffer.trim()) {
        const line = buffer
          .split("\n")
          .find((entry) => entry.startsWith("data:"));
        if (line) {
          const jsonStr = line.replace(/^data:\s*/, "");
          try {
            handleEvent(JSON.parse(jsonStr));
          } catch (error) {
            // ignore
          }
        }
      }
    } catch (error) {
      statusTitle.textContent = "Errore durante la ricerca.";
      statusSubtitle.textContent = "";
    } finally {
      searchBtn.disabled = false;
      if (stopTimer) {
        stopTimer();
        stopTimer = null;
      }
    }
  });
};

window.addEventListener("DOMContentLoaded", init);