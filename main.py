import os, json, requests
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.utils import get_color_from_hex
from kivy.graphics import Color, RoundedRectangle
from datetime import datetime
import json

# ============================================================
# CONFIG FILE
# ============================================================
CONFIG_FILE = os.path.expanduser("~/.uber_profit_config.json")

DEFAULT_CONFIG = {
    "combustibil_lei_per_litru": 7.20,
    "consum_litri_per_100km": 7.5,
    "comision_uber_procent": 25.0,
    "comision_bolt_procent": 20.0,
    "taxe_anuale_lei": 0,
    "asigurare_lunara_lei": 0,
    "alte_costuri_lunare_lei": 0,
    "google_maps_api_key": ""
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            cfg = json.load(f)
            # merge cu default pentru chei noi
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = v
            return cfg
    return DEFAULT_CONFIG.copy()

def save_config(cfg):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)

# ============================================================
# CALCUL RUTA REALA WAZE/GOOGLE MAPS
# ============================================================
def get_real_distance_google(origin, destination, api_key):
    """Returneaza (distanta_km, timp_min) via Google Maps API"""
    url = "https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": origin,
        "destinations": destination,
        "mode": "driving",
        "key": api_key,
        "departure_time": "now",
        "traffic_model": "best_guess"
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        el = data["rows"][0]["elements"][0]
        if el["status"] == "OK":
            dist_km = el["distance"]["value"] / 1000
            time_min = el["duration_in_traffic"]["value"] / 60
            return round(dist_km, 2), round(time_min, 1)
    except Exception as e:
        return None, None
    return None, None

# ============================================================
# CALCULATOR PROFIT
# ============================================================
def calculeaza_profit(
    tarif_per_km, tarif_per_min, tarif_ora,
    distanta_cursa_km, timp_cursa_min,
    distanta_pana_la_client_km, timp_pana_la_client_min,
    platforma,  # "uber" sau "bolt"
    config
):
    # Venit brut
    venit_brut = (tarif_per_km * distanta_cursa_km) + (tarif_per_min * timp_cursa_min)
    
    # Comision platformă
    if platforma.lower() == "uber":
        comision_pct = config["comision_uber_procent"]
    else:
        comision_pct = config["comision_bolt_procent"]
    
    comision_lei = venit_brut * (comision_pct / 100)
    venit_net = venit_brut - comision_lei
    
    # Cost combustibil (cursa + drum pana la client)
    distanta_totala = distanta_cursa_km + distanta_pana_la_client_km
    cost_combustibil = (distanta_totala / 100) * config["consum_litri_per_100km"] * config["combustibil_lei_per_litru"]
    
    # Profit real
    profit = venit_net - cost_combustibil
    profit_per_km = profit / distanta_cursa_km if distanta_cursa_km > 0 else 0
    
    # Timp total (inclusiv drum la client)
    timp_total = timp_cursa_min + timp_pana_la_client_min
    profit_per_ora = (profit / timp_total) * 60 if timp_total > 0 else 0
    
    # Rating cursa (BUNA / OK / SLABA)
    if profit_per_km >= 3.5:
        rating = "✅ BUNĂ"
        rating_color = "#00C853"
    elif profit_per_km >= 2.5:
        rating = "🟡 OK"
        rating_color = "#FFD600"
    else:
        rating = "❌ SLABĂ"
        rating_color = "#FF1744"
    
    return {
        "venit_brut": round(venit_brut, 2),
        "comision_lei": round(comision_lei, 2),
        "venit_net": round(venit_net, 2),
        "cost_combustibil": round(cost_combustibil, 2),
        "profit": round(profit, 2),
        "profit_per_km": round(profit_per_km, 2),
        "profit_per_ora": round(profit_per_ora, 2),
        "distanta_totala": round(distanta_totala, 2),
        "timp_total": round(timp_total, 1),
        "rating": rating,
        "rating_color": rating_color
    }

# ============================================================
# UI - CARD WIDGET
# ============================================================
class CardBox(BoxLayout):
    def __init__(self, bg_color="#1E1E2E", **kwargs):
        super().__init__(**kwargs)
        self.bg_color = bg_color
        self.bind(pos=self._update_bg, size=self._update_bg)

    def _update_bg(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*get_color_from_hex(self.bg_color))
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12)])

class LabelBold(Label):
    pass

# ============================================================
# ECRAN PRINCIPAL - CALCULATOR
# ============================================================
class CalculatorScreen(BoxLayout):
    def __init__(self, config_ref, **kwargs):
        super().__init__(orientation='vertical', padding=dp(10), spacing=dp(8), **kwargs)
        self.config = config_ref
        self.last_result = None
        self._build_ui()

    def _build_ui(self):
        # Header
        header = BoxLayout(size_hint_y=None, height=dp(50), padding=[dp(5), 0])
        header.add_widget(Label(
            text="🏎️ PROFIT CALCULATOR",
            font_size=dp(18),
            bold=True,
            color=get_color_from_hex("#BB86FC")
        ))
        self.add_widget(header)

        # Scroll pentru inputs
        scroll = ScrollView()
        main_layout = BoxLayout(orientation='vertical', spacing=dp(8),
                                size_hint_y=None, padding=[dp(5), 0])
        main_layout.bind(minimum_height=main_layout.setter('height'))

        # --- PLATFORMA ---
        plat_box = CardBox(bg_color="#252535", orientation='horizontal',
                           size_hint_y=None, height=dp(45), padding=[dp(8), 0])
        plat_box.add_widget(Label(text="Platforma:", size_hint_x=0.4,
                                  color=get_color_from_hex("#BBBBCC"), font_size=dp(13)))
        self.btn_uber = Button(text="UBER", size_hint_x=0.3,
                               background_color=get_color_from_hex("#1565C0"),
                               font_size=dp(12))
        self.btn_bolt = Button(text="BOLT", size_hint_x=0.3,
                               background_color=get_color_from_hex("#333344"),
                               font_size=dp(12))
        self.btn_uber.bind(on_press=lambda x: self._set_platforma("uber"))
        self.btn_bolt.bind(on_press=lambda x: self._set_platforma("bolt"))
        plat_box.add_widget(self.btn_uber)
        plat_box.add_widget(self.btn_bolt)
        self.platforma = "uber"
        main_layout.add_widget(plat_box)

        # --- TARIFE ---
        self.tarif_km = self._input_row(main_layout, "Tarif /km (RON):", "4.45")
        self.tarif_min = self._input_row(main_layout, "Tarif /min (RON):", "1.07")

        # --- CURSA ---
        self._section_label(main_layout, "📍 DATE CURSĂ")
        self.dist_cursa = self._input_row(main_layout, "Distanță cursă (km):", "7.4")
        self.timp_cursa = self._input_row(main_layout, "Timp cursă (min):", "34")

        # --- DRUM LA CLIENT ---
        self._section_label(main_layout, "🚗 DRUM PÂNĂ LA CLIENT")
        self.dist_client = self._input_row(main_layout, "Distanță la client (km):", "1.7")
        self.timp_client = self._input_row(main_layout, "Timp la client (min):", "5")

        # --- RUTA REALA WAZE ---
        self._section_label(main_layout, "🗺️ DISTANȚĂ REALĂ (opțional)")
        waze_box = CardBox(bg_color="#1A2A1A", orientation='vertical',
                           size_hint_y=None, height=dp(120), padding=[dp(8), dp(5)], spacing=dp(5))

        addr_row1 = BoxLayout(size_hint_y=None, height=dp(35), spacing=dp(5))
        addr_row1.add_widget(Label(text="De la:", size_hint_x=0.25,
                                   color=get_color_from_hex("#88FF88"), font_size=dp(11)))
        self.addr_from = TextInput(hint_text="Adresa preluare", size_hint_x=0.75,
                                    background_color=get_color_from_hex("#252535"),
                                    foreground_color=[1,1,1,1], font_size=dp(11),
                                    multiline=False)
        addr_row1.add_widget(self.addr_from)
        waze_box.add_widget(addr_row1)

        addr_row2 = BoxLayout(size_hint_y=None, height=dp(35), spacing=dp(5))
        addr_row2.add_widget(Label(text="Până la:", size_hint_x=0.25,
                                   color=get_color_from_hex("#88FF88"), font_size=dp(11)))
        self.addr_to = TextInput(hint_text="Adresa destinație", size_hint_x=0.75,
                                  background_color=get_color_from_hex("#252535"),
                                  foreground_color=[1,1,1,1], font_size=dp(11),
                                  multiline=False)
        addr_row2.add_widget(self.addr_to)
        waze_box.add_widget(addr_row2)

        btn_waze = Button(text="🔍 Calculează distanță reală cu traffic",
                          size_hint_y=None, height=dp(32),
                          background_color=get_color_from_hex("#004D40"),
                          font_size=dp(11))
        btn_waze.bind(on_press=self._get_real_distance)
        waze_box.add_widget(btn_waze)
        main_layout.add_widget(waze_box)

        # --- BUTON CALCUL ---
        btn_calc = Button(
            text="⚡ CALCULEAZĂ PROFIT",
            size_hint_y=None, height=dp(50),
            background_color=get_color_from_hex("#6200EE"),
            font_size=dp(15), bold=True
        )
        btn_calc.bind(on_press=self._calculeaza)
        main_layout.add_widget(btn_calc)

        # --- REZULTAT ---
        self.result_card = CardBox(bg_color="#0D1F0D", orientation='vertical',
                                   size_hint_y=None, height=dp(280),
                                   padding=[dp(10), dp(8)], spacing=dp(4))
        self.result_label = Label(
            text="Completează datele și apasă CALCULEAZĂ",
            color=get_color_from_hex("#888899"),
            font_size=dp(13), halign='left', valign='top',
            text_size=(Window.width - dp(50), None)
        )
        self.result_card.add_widget(self.result_label)
        main_layout.add_widget(self.result_card)

        # Spacer
        main_layout.add_widget(BoxLayout(size_hint_y=None, height=dp(20)))

        scroll.add_widget(main_layout)
        self.add_widget(scroll)

    def _section_label(self, parent, text):
        lbl = Label(text=text, size_hint_y=None, height=dp(25),
                    color=get_color_from_hex("#03DAC6"), font_size=dp(11),
                    halign='left', bold=True)
        lbl.bind(size=lbl.setter('text_size'))
        parent.add_widget(lbl)

    def _input_row(self, parent, label, default=""):
        row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(40), spacing=dp(5))
        lbl = Label(text=label, size_hint_x=0.55,
                    color=get_color_from_hex("#CCCCDD"), font_size=dp(12))
        inp = TextInput(text=default, size_hint_x=0.45,
                        background_color=get_color_from_hex("#252535"),
                        foreground_color=[1,1,1,1], font_size=dp(13),
                        multiline=False, input_filter='float',
                        halign='center')
        row.add_widget(lbl)
        row.add_widget(inp)
        parent.add_widget(row)
        return inp

    def _set_platforma(self, p):
        self.platforma = p
        if p == "uber":
            self.btn_uber.background_color = get_color_from_hex("#1565C0")
            self.btn_bolt.background_color = get_color_from_hex("#333344")
        else:
            self.btn_uber.background_color = get_color_from_hex("#333344")
            self.btn_bolt.background_color = get_color_from_hex("#1A7F2E")

    def _get_real_distance(self, *args):
        api_key = self.config.get("google_maps_api_key", "")
        if not api_key:
            self._show_popup("⚠️ API Key lipsă",
                "Mergi la Setări și adaugă Google Maps API Key\npentru distanță reală cu traffic.")
            return
        origin = self.addr_from.text.strip()
        dest = self.addr_to.text.strip()
        if not origin or not dest:
            self._show_popup("⚠️ Adrese incomplete", "Completează ambele adrese.")
            return
        dist, timp = get_real_distance_google(origin, dest, api_key)
        if dist and timp:
            self.dist_cursa.text = str(dist)
            self.timp_cursa.text = str(timp)
            self._show_popup("✅ Distanță actualizată",
                f"Distanță reală: {dist} km\nTimp estimat cu traffic: {timp} min")
        else:
            self._show_popup("❌ Eroare", "Nu s-a putut obține distanța.\nVerifică API key-ul și adresele.")

    def _calculeaza(self, *args):
        try:
            tkm = float(self.tarif_km.text or 0)
            tmin = float(self.tarif_min.text or 0)
            dkm = float(self.dist_cursa.text or 0)
            tmin_cursa = float(self.timp_cursa.text or 0)
            dkm_client = float(self.dist_client.text or 0)
            tmin_client = float(self.timp_client.text or 0)
        except ValueError:
            self._show_popup("❌ Eroare", "Verifică că toate câmpurile conțin numere valide.")
            return

        r = calculeaza_profit(
            tkm, tmin, 0,
            dkm, tmin_cursa,
            dkm_client, tmin_client,
            self.platforma,
            self.config
        )
        self.last_result = r

        txt = f"""[b][color={r['rating_color'].replace('#','')}]{r['rating']}[/color][/b]

[color=03DAC6]PROFIT NET:[/color]  [b][color=00E676]{r['profit']} RON[/color][/b]
[color=AAAAAA]Profit/km:[/color]   {r['profit_per_km']} RON/km
[color=AAAAAA]Profit/oră:[/color]  {r['profit_per_ora']:.1f} RON/h

─────────────────────
[color=FFCC02]Venit brut:[/color]      {r['venit_brut']} RON
[color=FF6B6B]Comision {self.platforma.upper()}:[/color] -{r['comision_lei']} RON
[color=FFCC02]Venit net:[/color]       {r['venit_net']} RON
[color=FF6B6B]Combustibil:[/color]     -{r['cost_combustibil']} RON
─────────────────────
[color=AAAAAA]Dist totală:[/color]  {r['distanta_totala']} km
[color=AAAAAA]Timp total:[/color]   {r['timp_total']} min"""

        self.result_label.text = txt
        self.result_label.markup = True
        self.result_label.color = [1, 1, 1, 1]

    def _show_popup(self, title, msg):
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        content.add_widget(Label(text=msg, font_size=dp(13)))
        btn = Button(text="OK", size_hint_y=None, height=dp(40),
                     background_color=get_color_from_hex("#6200EE"))
        popup = Popup(title=title, content=content,
                      size_hint=(0.85, 0.4), auto_dismiss=True)
        btn.bind(on_press=popup.dismiss)
        content.add_widget(btn)
        popup.open()

# ============================================================
# ECRAN SETARI
# ============================================================
class SettingsScreen(BoxLayout):
    def __init__(self, config_ref, on_save_callback, **kwargs):
        super().__init__(orientation='vertical', padding=dp(10), spacing=dp(8), **kwargs)
        self.config = config_ref
        self.on_save_callback = on_save_callback
        self.inputs = {}
        self._build_ui()

    def _build_ui(self):
        self.add_widget(Label(
            text="⚙️ SETĂRI",
            size_hint_y=None, height=dp(45),
            font_size=dp(18), bold=True,
            color=get_color_from_hex("#BB86FC")
        ))

        scroll = ScrollView()
        layout = BoxLayout(orientation='vertical', spacing=dp(6),
                           size_hint_y=None, padding=[dp(5), 0])
        layout.bind(minimum_height=layout.setter('height'))

        fields = [
            ("combustibil_lei_per_litru",   "⛽ Preț combustibil (lei/L):",   "7.20"),
            ("consum_litri_per_100km",       "🚗 Consum (litri/100km):",       "7.5"),
            ("comision_uber_procent",        "Uber comision (%):",             "25"),
            ("comision_bolt_procent",        "Bolt comision (%):",             "20"),
            ("taxe_anuale_lei",              "📋 Taxe anuale (lei):",          "0"),
            ("asigurare_lunara_lei",         "🛡️ Asigurare lunară (lei):",     "0"),
            ("alte_costuri_lunare_lei",      "💼 Alte costuri/lună (lei):",    "0"),
            ("google_maps_api_key",          "🗺️ Google Maps API Key:",        ""),
        ]

        for key, label, default in fields:
            row = BoxLayout(orientation='horizontal', size_hint_y=None, height=dp(42), spacing=dp(5))
            lbl = Label(text=label, size_hint_x=0.6,
                        color=get_color_from_hex("#CCCCDD"), font_size=dp(11),
                        halign='left')
            lbl.bind(size=lbl.setter('text_size'))
            val = str(self.config.get(key, default))
            inp = TextInput(text=val, size_hint_x=0.4,
                            background_color=get_color_from_hex("#252535"),
                            foreground_color=[1,1,1,1], font_size=dp(12),
                            multiline=False)
            self.inputs[key] = inp
            row.add_widget(lbl)
            row.add_widget(inp)
            layout.add_widget(row)

        # Info Google Maps API
        info = Label(
            text="[color=888899]🔑 Obține gratuit API key:\nconsole.cloud.google.com\n→ Maps → Distance Matrix API[/color]",
            size_hint_y=None, height=dp(60),
            font_size=dp(10), markup=True
        )
        layout.add_widget(info)

        btn_save = Button(
            text="💾 SALVEAZĂ SETĂRILE",
            size_hint_y=None, height=dp(50),
            background_color=get_color_from_hex("#00897B"),
            font_size=dp(14), bold=True
        )
        btn_save.bind(on_press=self._save)
        layout.add_widget(btn_save)
        layout.add_widget(BoxLayout(size_hint_y=None, height=dp(20)))

        scroll.add_widget(layout)
        self.add_widget(scroll)

    def _save(self, *args):
        for key, inp in self.inputs.items():
            val = inp.text.strip()
            try:
                if key == "google_maps_api_key":
                    self.config[key] = val
                else:
                    self.config[key] = float(val)
            except ValueError:
                pass
        save_config(self.config)
        if self.on_save_callback:
            self.on_save_callback()
        content = BoxLayout(orientation='vertical', padding=dp(10))
        content.add_widget(Label(text="✅ Setările au fost salvate!"))
        btn = Button(text="OK", size_hint_y=None, height=dp(40),
                     background_color=get_color_from_hex("#00897B"))
        popup = Popup(title="Salvat", content=content,
                      size_hint=(0.6, 0.3), auto_dismiss=True)
        btn.bind(on_press=popup.dismiss)
        content.add_widget(btn)
        popup.open()

# ============================================================
# ECRAN ISTORIC
# ============================================================
HISTORY_FILE = os.path.expanduser("~/.uber_profit_history.json")

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    return []

def save_history_entry(entry):
    h = load_history()
    h.insert(0, entry)
    h = h[:50]  # max 50 intrări
    with open(HISTORY_FILE, 'w') as f:
        json.dump(h, f, indent=2)

# ============================================================
# APLICATIA PRINCIPALA
# ============================================================
class UberProfitApp(App):
    def build(self):
        Window.clearcolor = get_color_from_hex("#121220")

        self.config_data = load_config()

        root = BoxLayout(orientation='vertical')

        # Tab panel
        tp = TabbedPanel(do_default_tab=False)
        tp.tab_width = Window.width / 3

        # Tab Calculator
        tab_calc = TabbedPanelItem(text="🧮 Calculator")
        self.calc_screen = CalculatorScreen(config_ref=self.config_data)
        tab_calc.add_widget(self.calc_screen)
        tp.add_widget(tab_calc)

        # Tab Setări
        tab_set = TabbedPanelItem(text="⚙️ Setări")
        self.set_screen = SettingsScreen(
            config_ref=self.config_data,
            on_save_callback=self._on_config_saved
        )
        tab_set.add_widget(self.set_screen)
        tp.add_widget(tab_set)

        # Tab Info
        tab_info = TabbedPanelItem(text="ℹ️ Info")
        info_layout = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(10))
        info_text = """[b][color=BB86FC]🏎️ Uber/Bolt Profit Calculator[/color][/b]

[color=03DAC6]Cum se calculează profitul:[/color]

1. Introdu tarifele din pop-up-ul cursei
2. Introdu distanța și timpul cursei
3. Introdu distanța până la client
4. Apasă CALCULEAZĂ

[color=FFCC02]Formula profit:[/color]
Venit = tarif/km × km + tarif/min × min
Net = Venit - Comision platformă
Profit = Net - Combustibil (cursa + client)

[color=FF6B6B]Rating cursă:[/color]
✅ BUNĂ   = > 3.5 RON/km
🟡 OK      = 2.5 - 3.5 RON/km  
❌ SLABĂ  = < 2.5 RON/km

[color=888899]Setează prețul combustibilului
și consumul mașinii în tab-ul Setări.[/color]"""

        lbl = Label(text=info_text, markup=True, font_size=dp(13),
                    halign='left', valign='top')
        lbl.bind(size=lbl.setter('text_size'))
        info_layout.add_widget(lbl)
        tab_info.add_widget(info_layout)
        tp.add_widget(tab_info)

        tp.default_tab = tab_calc
        root.add_widget(tp)
        return root

    def _on_config_saved(self):
        # Reîncarcă config în calculator
        self.calc_screen.config = self.config_data

if __name__ == '__main__':
    UberProfitApp().run()
