import tkinter as tk
from tkinter import ttk, messagebox
import threading
import datetime
from skyscanner import SkyScanner
from skyscanner.types import SpecialTypes


class ModernLightStyle:
    """Modern light color scheme"""
    # Colors
    BG_MAIN = "#f0f4f8"
    BG_WHITE = "#ffffff"
    BG_CARD = "#ffffff"
    BORDER = "#e1e5eb"
    PRIMARY = "#1a4fd6"
    PRIMARY_HOVER = "#1542b0"
    TEXT_DARK = "#1a1a2e"
    TEXT_SECONDARY = "#6b7280"
    TEXT_LIGHT = "#9ca3af"
    SUCCESS = "#10b981"
    WARNING = "#f59e0b"
    ACCENT_LIGHT = "#e8f0fe"

    @classmethod
    def configure_styles(cls):
        style = ttk.Style()
        style.theme_use('clam')

        # Frames
        style.configure("Main.TFrame", background=cls.BG_MAIN)
        style.configure("Card.TFrame", background=cls.BG_WHITE)
        style.configure("White.TFrame", background=cls.BG_WHITE)

        # Labels
        style.configure("Title.TLabel",
                       background=cls.BG_WHITE,
                       foreground=cls.TEXT_DARK,
                       font=("Segoe UI", 20, "bold"))
        style.configure("Subtitle.TLabel",
                       background=cls.BG_WHITE,
                       foreground=cls.TEXT_SECONDARY,
                       font=("Segoe UI", 10))
        style.configure("Card.TLabel",
                       background=cls.BG_WHITE,
                       foreground=cls.TEXT_DARK,
                       font=("Segoe UI", 10))
        style.configure("CardSmall.TLabel",
                       background=cls.BG_WHITE,
                       foreground=cls.TEXT_SECONDARY,
                       font=("Segoe UI", 9))
        style.configure("Status.TLabel",
                       background=cls.BG_MAIN,
                       foreground=cls.PRIMARY,
                       font=("Segoe UI", 10, "bold"))
        style.configure("Step.TLabel",
                       background=cls.BG_MAIN,
                       foreground=cls.TEXT_SECONDARY,
                       font=("Segoe UI", 9))
        style.configure("Price.TLabel",
                       background=cls.BG_WHITE,
                       foreground=cls.PRIMARY,
                       font=("Segoe UI", 16, "bold"))
        style.configure("Airline.TLabel",
                       background=cls.BG_WHITE,
                       foreground=cls.TEXT_DARK,
                       font=("Segoe UI", 11, "bold"))
        style.configure("Time.TLabel",
                       background=cls.BG_WHITE,
                       foreground=cls.TEXT_DARK,
                       font=("Segoe UI", 14, "bold"))
        style.configure("Duration.TLabel",
                       background=cls.BG_WHITE,
                       foreground=cls.TEXT_SECONDARY,
                       font=("Segoe UI", 9))
        style.configure("FilterLabel.TLabel",
                       background=cls.BG_WHITE,
                       foreground=cls.TEXT_SECONDARY,
                       font=("Segoe UI", 9))

        # Progress bar
        style.configure("Primary.Horizontal.TProgressbar",
                       background=cls.PRIMARY,
                       troughcolor=cls.BORDER,
                       borderwidth=0)

        # Combobox
        style.configure("TCombobox",
                       fieldbackground=cls.BG_WHITE,
                       background=cls.BG_WHITE,
                       foreground=cls.TEXT_DARK,
                       arrowcolor=cls.PRIMARY,
                       borderwidth=1,
                       relief="solid")
        style.map("TCombobox",
                 fieldbackground=[('readonly', cls.BG_WHITE)],
                 selectbackground=[('readonly', cls.ACCENT_LIGHT)],
                 selectforeground=[('readonly', cls.TEXT_DARK)])

        # Checkbutton
        style.configure("Filter.TCheckbutton",
                       background=cls.BG_WHITE,
                       foreground=cls.TEXT_DARK,
                       font=("Segoe UI", 9))


class FlightCard(ttk.Frame):
    """A single flight result card"""
    def __init__(self, parent, flight_data, **kwargs):
        super().__init__(parent, style="Card.TFrame", **kwargs)

        self.configure(padding=15)
        self.flight_data = flight_data

        # Main container (vertical)
        main_container = ttk.Frame(self, style="White.TFrame")
        main_container.pack(fill="x", expand=True)

        # Top row: main flight info
        top_row = ttk.Frame(main_container, style="White.TFrame")
        top_row.pack(fill="x")

        # Left: Airline
        airline_frame = ttk.Frame(top_row, style="White.TFrame", width=100)
        airline_frame.pack(side="left", padx=(0, 20))
        airline_frame.pack_propagate(False)

        # Airline logo placeholder (colored box with initials)
        logo_frame = tk.Frame(airline_frame, bg=self._get_airline_color(flight_data["compagnia"]),
                             width=50, height=50)
        logo_frame.pack(pady=(0, 5))
        logo_frame.pack_propagate(False)

        initials = self._get_initials(flight_data["compagnia"])
        tk.Label(logo_frame, text=initials, bg=self._get_airline_color(flight_data["compagnia"]),
                fg="white", font=("Segoe UI", 12, "bold")).place(relx=0.5, rely=0.5, anchor="center")

        ttk.Label(airline_frame, text=flight_data["compagnia"][:15],
                 style="CardSmall.TLabel").pack()

        # Center: Times and duration
        times_frame = ttk.Frame(top_row, style="White.TFrame")
        times_frame.pack(side="left", expand=True, fill="x", padx=20)

        # Departure
        dep_frame = ttk.Frame(times_frame, style="White.TFrame")
        dep_frame.pack(side="left")
        ttk.Label(dep_frame, text=flight_data["partenza"], style="Time.TLabel").pack()
        ttk.Label(dep_frame, text="VCE", style="CardSmall.TLabel").pack()

        # Duration line
        duration_frame = ttk.Frame(times_frame, style="White.TFrame")
        duration_frame.pack(side="left", expand=True, fill="x", padx=20)

        ttk.Label(duration_frame, text=flight_data["durata"], style="Duration.TLabel").pack()

        # Draw line with dots
        line_canvas = tk.Canvas(duration_frame, height=20, bg="white", highlightthickness=0)
        line_canvas.pack(fill="x", pady=2)
        line_canvas.bind("<Configure>", lambda e: self._draw_flight_line(line_canvas, flight_data["scali"]))

        stops_text = "Diretto" if flight_data["scali"] == 0 else f"{flight_data['scali']} scalo"
        ttk.Label(duration_frame, text=stops_text, style="Duration.TLabel").pack()

        # Arrival
        arr_frame = ttk.Frame(times_frame, style="White.TFrame")
        arr_frame.pack(side="left")
        ttk.Label(arr_frame, text=flight_data["arrivo"], style="Time.TLabel").pack()
        ttk.Label(arr_frame, text=flight_data["codice_dest"], style="CardSmall.TLabel").pack()

        # Right: Price and destination
        price_frame = ttk.Frame(top_row, style="White.TFrame", width=150)
        price_frame.pack(side="right", padx=(20, 0))
        price_frame.pack_propagate(False)

        ttk.Label(price_frame, text=f"€ {flight_data['prezzo']:.0f}",
                 style="Price.TLabel").pack(anchor="e")
        ttk.Label(price_frame, text=flight_data["città"],
                 style="Card.TLabel").pack(anchor="e")
        ttk.Label(price_frame, text=flight_data["paese"],
                 style="CardSmall.TLabel").pack(anchor="e")

        # Bottom row: Stopover details (if any)
        stopovers = flight_data.get("stopovers", [])
        if stopovers:
            # Separator line
            separator = ttk.Frame(main_container, style="White.TFrame", height=1)
            separator.pack(fill="x", pady=(10, 5))
            tk.Frame(separator, bg="#e1e5eb", height=1).pack(fill="x")

            # Stopover info
            stopover_frame = ttk.Frame(main_container, style="White.TFrame")
            stopover_frame.pack(fill="x", padx=(100, 0))  # Align with times

            for i, stop in enumerate(stopovers):
                stop_row = ttk.Frame(stopover_frame, style="White.TFrame")
                stop_row.pack(fill="x", pady=2)

                # Stop icon
                tk.Label(stop_row, text="✈", font=("Segoe UI", 9),
                        bg="white", fg="#f59e0b").pack(side="left", padx=(0, 5))

                # Stop info text
                stop_text = f"Scalo a {stop['città']}"
                if stop['codice']:
                    stop_text += f" ({stop['codice']})"
                stop_text += f": arrivo {stop['arrivo']}"
                if stop['partenza']:
                    stop_text += f" → ripartenza {stop['partenza']}"
                if stop['attesa']:
                    stop_text += f" (attesa {stop['attesa']})"

                tk.Label(stop_row, text=stop_text, font=("Segoe UI", 9),
                        bg="white", fg="#6b7280").pack(side="left")

    def _get_initials(self, name):
        words = name.split()
        if len(words) >= 2:
            return (words[0][0] + words[1][0]).upper()
        return name[:2].upper()

    def _get_airline_color(self, name):
        colors = ["#1a4fd6", "#e94560", "#10b981", "#f59e0b", "#8b5cf6", "#06b6d4"]
        return colors[hash(name) % len(colors)]

    def _draw_flight_line(self, canvas, stops):
        canvas.delete("all")
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        y = h // 2

        # Draw line
        canvas.create_line(10, y, w-10, y, fill="#e1e5eb", width=2)

        # Draw dots for stops
        if stops > 0:
            for i in range(stops):
                x = 10 + (i + 1) * (w - 20) / (stops + 1)
                canvas.create_oval(x-4, y-4, x+4, y+4, fill="#f59e0b", outline="")

        # Endpoints
        canvas.create_oval(6, y-4, 14, y+4, fill="#1a4fd6", outline="")
        canvas.create_oval(w-14, y-4, w-6, y+4, fill="#1a4fd6", outline="")


class FlightSearchApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Flight Booking - Cerca Voli")
        self.root.geometry("1100x800")
        self.root.minsize(1000, 700)
        self.root.configure(bg=ModernLightStyle.BG_MAIN)

        ModernLightStyle.configure_styles()

        self.scanner = None
        self.searching = False
        self.flight_count = 0
        self.airports_cache = {}
        self.flight_cards = []

        self.create_widgets()
        self.load_airports()

    def create_widgets(self):
        # Main container with padding
        main_frame = ttk.Frame(self.root, style="Main.TFrame")
        main_frame.pack(fill="both", expand=True, padx=30, pady=20)

        # Header
        header = ttk.Frame(main_frame, style="Main.TFrame")
        header.pack(fill="x", pady=(0, 20))

        title_label = tk.Label(header, text="✈  Flight Booking",
                              font=("Segoe UI", 18, "bold"),
                              bg=ModernLightStyle.BG_MAIN,
                              fg=ModernLightStyle.TEXT_DARK)
        title_label.pack(side="left")

        # Search Card
        search_card = ttk.Frame(main_frame, style="Card.TFrame")
        search_card.pack(fill="x", pady=(0, 15), ipady=20, ipadx=20)

        # Add shadow effect (border)
        search_card.configure(borderwidth=1, relief="solid")

        # Search form row
        form_frame = ttk.Frame(search_card, style="White.TFrame")
        form_frame.pack(fill="x", padx=20, pady=15)

        # From
        from_frame = ttk.Frame(form_frame, style="White.TFrame")
        from_frame.pack(side="left", padx=(0, 15))
        ttk.Label(from_frame, text="Da", style="FilterLabel.TLabel").pack(anchor="w")
        self.origin_var = tk.StringVar(value="Venezia (VCE)")
        self.origin_combo = ttk.Combobox(from_frame, textvariable=self.origin_var,
                                         width=25, font=("Segoe UI", 11), state="readonly")
        self.origin_combo.pack(pady=(5, 0), ipady=5)

        # Swap button
        swap_btn = tk.Button(form_frame, text="⇄", font=("Segoe UI", 14),
                            bg=ModernLightStyle.BG_WHITE, fg=ModernLightStyle.PRIMARY,
                            relief="flat", cursor="hand2", width=3)
        swap_btn.pack(side="left", padx=5, pady=(15, 0))

        # To
        to_frame = ttk.Frame(form_frame, style="White.TFrame")
        to_frame.pack(side="left", padx=(0, 15))
        ttk.Label(to_frame, text="A", style="FilterLabel.TLabel").pack(anchor="w")
        self.dest_var = tk.StringVar(value="🌍 Ovunque")
        self.dest_combo = ttk.Combobox(to_frame, textvariable=self.dest_var,
                                       width=25, font=("Segoe UI", 11), state="readonly")
        self.dest_combo["values"] = ["🌍 Ovunque"]
        self.dest_combo.pack(pady=(5, 0), ipady=5)

        # Date
        date_frame = ttk.Frame(form_frame, style="White.TFrame")
        date_frame.pack(side="left", padx=(0, 15))
        ttk.Label(date_frame, text="Data Partenza", style="FilterLabel.TLabel").pack(anchor="w")
        self.date_entry = tk.Entry(date_frame, width=12, font=("Segoe UI", 11),
                                   bg=ModernLightStyle.BG_WHITE,
                                   fg=ModernLightStyle.TEXT_DARK,
                                   relief="solid", bd=1,
                                   highlightthickness=2,
                                   highlightbackground=ModernLightStyle.BORDER,
                                   highlightcolor=ModernLightStyle.PRIMARY)
        self.date_entry.insert(0, (datetime.date.today() + datetime.timedelta(days=30)).strftime("%d/%m/%Y"))
        self.date_entry.pack(pady=(5, 0), ipady=6)

        # Search button
        self.search_btn = tk.Button(form_frame, text="🔍  Cerca Voli",
                                    font=("Segoe UI", 11, "bold"),
                                    bg=ModernLightStyle.PRIMARY,
                                    fg="white",
                                    activebackground=ModernLightStyle.PRIMARY_HOVER,
                                    activeforeground="white",
                                    relief="flat", cursor="hand2",
                                    command=self.start_search)
        self.search_btn.pack(side="right", padx=10, ipady=10, ipadx=20)

        # Filters row
        filter_frame = ttk.Frame(search_card, style="White.TFrame")
        filter_frame.pack(fill="x", padx=20, pady=(0, 10))

        # Price filter
        price_filter = ttk.Frame(filter_frame, style="White.TFrame")
        price_filter.pack(side="left", padx=(0, 30))
        ttk.Label(price_filter, text="Prezzo max €", style="FilterLabel.TLabel").pack(side="left")
        self.price_entry = tk.Entry(price_filter, width=6, font=("Segoe UI", 10),
                                    bg=ModernLightStyle.BG_WHITE,
                                    fg=ModernLightStyle.TEXT_DARK,
                                    relief="solid", bd=1)
        self.price_entry.insert(0, "100")
        self.price_entry.pack(side="left", padx=(5, 0), ipady=3)

        # Hour filter
        hour_filter = ttk.Frame(filter_frame, style="White.TFrame")
        hour_filter.pack(side="left", padx=(0, 30))
        ttk.Label(hour_filter, text="Partenza dalle ore", style="FilterLabel.TLabel").pack(side="left")
        self.hour_entry = tk.Entry(hour_filter, width=4, font=("Segoe UI", 10),
                                   bg=ModernLightStyle.BG_WHITE,
                                   fg=ModernLightStyle.TEXT_DARK,
                                   relief="solid", bd=1)
        self.hour_entry.insert(0, "18")
        self.hour_entry.pack(side="left", padx=(5, 0), ipady=3)

        # Direct only checkbox
        self.direct_var = tk.BooleanVar(value=False)
        direct_check = ttk.Checkbutton(filter_frame, text="Solo voli diretti",
                                       variable=self.direct_var,
                                       style="Filter.TCheckbutton")
        direct_check.pack(side="left", padx=(0, 20))

        # Same day arrival checkbox
        self.same_day_var = tk.BooleanVar(value=True)
        same_day_check = ttk.Checkbutton(filter_frame, text="Arrivo stesso giorno",
                                         variable=self.same_day_var,
                                         style="Filter.TCheckbutton")
        same_day_check.pack(side="left")

        # Progress section
        progress_frame = ttk.Frame(main_frame, style="Main.TFrame")
        progress_frame.pack(fill="x", pady=(0, 10))

        self.action_var = tk.StringVar(value="")
        self.action_label = ttk.Label(progress_frame, textvariable=self.action_var,
                                      style="Status.TLabel")
        self.action_label.pack(anchor="w")

        self.step_var = tk.StringVar(value="")
        self.step_label = ttk.Label(progress_frame, textvariable=self.step_var,
                                    style="Step.TLabel")
        self.step_label.pack(anchor="w", pady=(2, 5))

        self.progress_bar = ttk.Progressbar(progress_frame, mode="determinate",
                                            style="Primary.Horizontal.TProgressbar",
                                            length=400)
        self.progress_bar.pack(fill="x", pady=(0, 5))

        # Stats row
        stats_frame = ttk.Frame(progress_frame, style="Main.TFrame")
        stats_frame.pack(fill="x")

        self.stats_var = tk.StringVar(value="")
        tk.Label(stats_frame, textvariable=self.stats_var,
                bg=ModernLightStyle.BG_MAIN,
                fg=ModernLightStyle.TEXT_SECONDARY,
                font=("Segoe UI", 9)).pack(side="left")

        self.count_var = tk.StringVar(value="")
        tk.Label(stats_frame, textvariable=self.count_var,
                bg=ModernLightStyle.BG_MAIN,
                fg=ModernLightStyle.SUCCESS,
                font=("Segoe UI", 10, "bold")).pack(side="right")

        # Results section header
        results_header = ttk.Frame(main_frame, style="Main.TFrame")
        results_header.pack(fill="x", pady=(10, 5))

        self.results_title = tk.Label(results_header, text="Seleziona il tuo volo",
                                     font=("Segoe UI", 14, "bold"),
                                     bg=ModernLightStyle.BG_MAIN,
                                     fg=ModernLightStyle.TEXT_DARK)
        self.results_title.pack(side="left")

        # Sort options
        sort_frame = ttk.Frame(results_header, style="Main.TFrame")
        sort_frame.pack(side="right")

        self.sort_var = tk.StringVar(value="prezzo")
        tk.Label(sort_frame, text="Ordina per:",
                bg=ModernLightStyle.BG_MAIN,
                fg=ModernLightStyle.TEXT_SECONDARY,
                font=("Segoe UI", 9)).pack(side="left", padx=(0, 5))

        sort_price = tk.Radiobutton(sort_frame, text="Prezzo", variable=self.sort_var,
                                   value="prezzo", bg=ModernLightStyle.BG_MAIN,
                                   fg=ModernLightStyle.TEXT_DARK, font=("Segoe UI", 9),
                                   activebackground=ModernLightStyle.BG_MAIN,
                                   selectcolor=ModernLightStyle.BG_MAIN)
        sort_price.pack(side="left")

        sort_time = tk.Radiobutton(sort_frame, text="Orario", variable=self.sort_var,
                                  value="orario", bg=ModernLightStyle.BG_MAIN,
                                  fg=ModernLightStyle.TEXT_DARK, font=("Segoe UI", 9),
                                  activebackground=ModernLightStyle.BG_MAIN,
                                  selectcolor=ModernLightStyle.BG_MAIN)
        sort_time.pack(side="left")

        sort_duration = tk.Radiobutton(sort_frame, text="Durata", variable=self.sort_var,
                                       value="durata", bg=ModernLightStyle.BG_MAIN,
                                       fg=ModernLightStyle.TEXT_DARK, font=("Segoe UI", 9),
                                       activebackground=ModernLightStyle.BG_MAIN,
                                       selectcolor=ModernLightStyle.BG_MAIN)
        sort_duration.pack(side="left")

        # Results scrollable area
        results_container = ttk.Frame(main_frame, style="Main.TFrame")
        results_container.pack(fill="both", expand=True)

        # Canvas for scrolling
        self.canvas = tk.Canvas(results_container, bg=ModernLightStyle.BG_MAIN,
                               highlightthickness=0)
        scrollbar = ttk.Scrollbar(results_container, orient="vertical",
                                 command=self.canvas.yview)

        self.results_frame = ttk.Frame(self.canvas, style="Main.TFrame")

        self.canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.canvas_window = self.canvas.create_window((0, 0), window=self.results_frame,
                                                       anchor="nw")

        self.results_frame.bind("<Configure>",
                               lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>",
                        lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))

        # Mouse wheel scrolling
        self.canvas.bind_all("<MouseWheel>",
                            lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    def load_airports(self):
        """Load common airports for dropdown"""
        airports = [
            "Venezia (VCE)",
            "Milano Malpensa (MXP)",
            "Milano Linate (LIN)",
            "Roma Fiumicino (FCO)",
            "Bologna (BLQ)",
            "Napoli (NAP)",
            "Torino (TRN)",
            "Firenze (FLR)",
            "Verona (VRN)",
            "Bergamo (BGY)",
            "Treviso (TSF)",
            "Bari (BRI)",
            "Catania (CTA)",
            "Palermo (PMO)"
        ]
        self.origin_combo["values"] = airports
        self.dest_combo["values"] = ["🌍 Ovunque"] + airports

    def start_search(self):
        if self.searching:
            return

        # Validate input
        try:
            date_str = self.date_entry.get()
            depart_date = datetime.datetime.strptime(date_str, "%d/%m/%Y")
            max_price = float(self.price_entry.get())
            min_hour = int(self.hour_entry.get())
        except ValueError:
            messagebox.showerror("Errore", "Controlla i valori inseriti.\n\nFormato data: GG/MM/AAAA")
            return

        self.searching = True
        self.flight_count = 0
        self.search_btn.config(state="disabled", bg="#9ca3af")

        # Clear previous results
        for card in self.flight_cards:
            card.destroy()
        self.flight_cards = []

        self.count_var.set("")
        self.stats_var.set("")
        self.results_title.config(text="Ricerca in corso...")

        # Get origin airport code
        origin_text = self.origin_var.get()
        origin_code = origin_text.split("(")[-1].replace(")", "").strip() if "(" in origin_text else "VCE"

        # Check if destination is "Everywhere"
        dest_text = self.dest_var.get()
        search_everywhere = "Ovunque" in dest_text

        thread = threading.Thread(
            target=self.search_flights,
            args=(depart_date, max_price, min_hour, origin_code, search_everywhere)
        )
        thread.daemon = True
        thread.start()

    def update_action(self, text):
        self.action_var.set(text)
        self.root.update_idletasks()

    def update_step(self, text):
        self.step_var.set(text)
        self.root.update_idletasks()

    def update_progress(self, value, maximum=None):
        if maximum is not None:
            self.progress_bar["maximum"] = maximum
        self.progress_bar["value"] = value
        self.root.update_idletasks()

    def update_stats(self, text):
        self.stats_var.set(text)
        self.root.update_idletasks()

    def update_count(self):
        self.count_var.set(f"✓ {self.flight_count} voli trovati")
        self.root.update_idletasks()

    def add_flight_card(self, flight):
        """Add a flight card to results"""
        card = FlightCard(self.results_frame, flight)
        card.pack(fill="x", pady=5, padx=5)
        self.flight_cards.append(card)
        self.flight_count += 1
        self.root.after(0, self.update_count)
        self.root.update_idletasks()

    def search_flights(self, depart_date, max_price, min_hour, origin_code, search_everywhere):
        try:
            # Step 1: Initialize
            self.update_action("⏳ Inizializzazione...")
            self.update_step("Connessione a Skyscanner")
            self.update_progress(0, 100)

            self.scanner = SkyScanner(locale="it-IT", currency="EUR", market="IT")

            # Step 2: Get origin airport
            self.update_action("🔍 Ricerca aeroporto...")
            self.update_step(f"Cerco aeroporto: {origin_code}")
            self.update_progress(5)

            origin = self.scanner.get_airport_by_code(origin_code)

            if search_everywhere:
                self._search_everywhere(origin, depart_date, max_price, min_hour)
            else:
                self.update_action("✅ Completato")
                self.update_step("Ricerca specifica destinazione non ancora implementata")

        except Exception as e:
            self.update_action("❌ Errore")
            self.update_step(str(e))
            messagebox.showerror("Errore", str(e))

        finally:
            self.searching = False
            self.root.after(0, lambda: self.search_btn.config(state="normal",
                                                              bg=ModernLightStyle.PRIMARY))
            self.root.after(0, lambda: self.results_title.config(
                text=f"Trovati {self.flight_count} voli"))

    def _search_everywhere(self, origin, depart_date, max_price, min_hour):
        """Search flights to everywhere"""

        # Step 3: Search countries
        self.update_action("🌍 Ricerca paesi economici...")
        self.update_step("Interrogo Skyscanner per destinazioni sotto budget")
        self.update_progress(10)

        response = self.scanner.get_flight_prices(
            origin=origin,
            destination=SpecialTypes.EVERYWHERE,
            depart_date=depart_date
        )

        countries = []
        for r in response.json.get("everywhereDestination", {}).get("results", []):
            content = r.get("content", {})
            location = content.get("location", {})
            price = content.get("flightQuotes", {}).get("cheapest", {}).get("rawPrice", 999999)
            if location.get("name") and location.get("skyCode") and price and price <= max_price:
                countries.append({"name": location["name"], "skyCode": location["skyCode"]})

        self.update_action(f"✓ Trovati {len(countries)} paesi")
        self.update_step("Cerco città in ogni paese...")
        self.update_progress(15)
        self.update_stats(f"Paesi sotto €{max_price:.0f}: {len(countries)}")

        # Step 4: Get cities
        all_cities = []
        for i, country in enumerate(countries):
            self.update_action(f"📍 Analisi paesi... ({i+1}/{len(countries)})")
            self.update_step(f"Cerco città in: {country['name']}")
            progress = 15 + (i / len(countries)) * 25
            self.update_progress(progress)

            try:
                country_airports = self.scanner.search_airports(country["skyCode"])
                if not country_airports:
                    continue
                country_entity = next((a for a in country_airports if a.skyId == country["skyCode"]),
                                      country_airports[0])

                country_response = self.scanner.get_flight_prices(
                    origin=origin, destination=country_entity, depart_date=depart_date
                )

                for r in country_response.json.get("countryDestination", {}).get("results", []):
                    content = r.get("content", {})
                    location = content.get("location", {})
                    city_price = content.get("flightQuotes", {}).get("cheapest", {}).get("rawPrice", 999999)
                    if location.get("name") and location.get("skyCode") and city_price and city_price <= max_price:
                        all_cities.append({
                            "name": location["name"],
                            "skyCode": location["skyCode"],
                            "country": country["name"]
                        })
            except:
                continue

        # Remove duplicates
        seen = set()
        cities = []
        for c in all_cities:
            if c["skyCode"] not in seen:
                seen.add(c["skyCode"])
                cities.append(c)

        self.update_action(f"✓ Trovate {len(cities)} città")
        self.update_step("Inizio ricerca voli specifici...")
        self.update_progress(40)
        self.update_stats(f"Paesi: {len(countries)} | Città: {len(cities)}")

        # Step 5: Search flights
        voli_trovati = []
        direct_only = self.direct_var.get()
        same_day = self.same_day_var.get()

        for i, city in enumerate(cities):
            self.update_action(f"✈ Ricerca voli... ({i+1}/{len(cities)})")
            self.update_step(f"Cerco voli per: {city['name']} ({city['country']})")
            progress = 40 + (i / len(cities)) * 55
            self.update_progress(progress)

            try:
                city_airports = self.scanner.search_airports(city["skyCode"])
                if not city_airports:
                    continue

                flight_response = self.scanner.get_flight_prices(
                    origin=origin, destination=city_airports[0], depart_date=depart_date
                )

                voli_visti = set()
                for bucket in flight_response.json.get("itineraries", {}).get("buckets", []):
                    for item in bucket.get("items", []):
                        if item["id"] in voli_visti:
                            continue
                        voli_visti.add(item["id"])

                        price = item.get("price", {}).get("raw", 999999)
                        if price > max_price:
                            continue

                        leg = item.get("legs", [{}])[0]
                        dep_str = leg.get("departure", "")
                        arr_str = leg.get("arrival", "")
                        if not dep_str or not arr_str:
                            continue

                        dep = datetime.datetime.fromisoformat(dep_str)
                        arr = datetime.datetime.fromisoformat(arr_str)

                        if dep.hour < min_hour:
                            continue

                        if same_day and arr.date() != dep.date():
                            continue

                        stops = leg.get("stopCount", 0)
                        if direct_only and stops > 0:
                            continue

                        duration = leg.get("durationInMinutes", 0)
                        carriers = leg.get("carriers", {}).get("marketing", [])
                        dest_info = leg.get("destination", {})

                        # Extract stopover details from segments
                        segments = leg.get("segments", [])
                        stopovers = []
                        if stops > 0 and len(segments) > 1:
                            for seg_idx in range(len(segments) - 1):
                                seg = segments[seg_idx]
                                next_seg = segments[seg_idx + 1]

                                # Stopover location (destination of current segment)
                                stop_dest = seg.get("destination", {})
                                stop_city = stop_dest.get("city", stop_dest.get("name", ""))
                                stop_code = stop_dest.get("displayCode", "")

                                # Times
                                seg_arr = seg.get("arrival", "")
                                next_dep = next_seg.get("departure", "")

                                # Calculate layover duration
                                layover_min = 0
                                if seg_arr and next_dep:
                                    try:
                                        arr_time = datetime.datetime.fromisoformat(seg_arr)
                                        dep_time = datetime.datetime.fromisoformat(next_dep)
                                        layover_min = int((dep_time - arr_time).total_seconds() / 60)
                                    except:
                                        pass

                                stopovers.append({
                                    "città": stop_city,
                                    "codice": stop_code,
                                    "arrivo": datetime.datetime.fromisoformat(seg_arr).strftime("%H:%M") if seg_arr else "",
                                    "partenza": datetime.datetime.fromisoformat(next_dep).strftime("%H:%M") if next_dep else "",
                                    "attesa": f"{layover_min // 60}h {layover_min % 60:02d}min" if layover_min > 0 else ""
                                })

                        flight = {
                            "città": dest_info.get("city", city["name"]),
                            "paese": dest_info.get("country", city["country"]),
                            "codice_dest": dest_info.get("displayCode", city["skyCode"]),
                            "prezzo": price,
                            "partenza": dep.strftime("%H:%M"),
                            "arrivo": arr.strftime("%H:%M"),
                            "durata": f"{duration // 60}h {duration % 60:02d}min",
                            "durata_min": duration,
                            "scali": stops,
                            "stopovers": stopovers,
                            "compagnia": carriers[0].get("name", "N/A") if carriers else "N/A"
                        }

                        key = f"{flight['città']}-{flight['partenza']}-{flight['prezzo']}"
                        if key not in [f"{v['città']}-{v['partenza']}-{v['prezzo']}" for v in voli_trovati]:
                            voli_trovati.append(flight)
                            self.root.after(0, lambda f=flight: self.add_flight_card(f))
            except:
                continue

        # Done
        self.update_action(f"✅ Ricerca completata!")
        self.update_step(f"Trovati {len(voli_trovati)} voli che rispettano i tuoi criteri")
        self.update_progress(100)
        self.update_stats(f"Paesi: {len(countries)} | Città: {len(cities)} | Voli analizzati: {len(cities) * 10}+")


if __name__ == "__main__":
    root = tk.Tk()

    # Center window
    root.update_idletasks()
    width = 1100
    height = 800
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f"{width}x{height}+{x}+{y}")

    app = FlightSearchApp(root)
    root.mainloop()