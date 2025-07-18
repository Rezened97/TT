from dotenv import load_dotenv
import os

# Carica il .env nella root del progetto
load_dotenv(dotenv_path=os.path.join(os.getcwd(), ".env"))

import os
os.environ["STREAMLIT_DEVELOPMENT_MODE"] = "false"

import sys
import tempfile
import cv2
import logging
import traceback

import streamlit as st
import streamlit_authenticator as stauth
from core.campaign import create_campaign
from core.adset import create_adset
from core.creative import upload_image, upload_video, create_ad_creative, create_ad
from core.meta_data import fetch_ad_accounts, fetch_pages
from utils.api_helpers import APIHelper

# Carica la mappa username→password da secrets.toml
# [credentials]
# mario = "pass123"
# luca  = "secret456"
CREDENTIALS = st.secrets["credentials"]

# 1) Inizializza lo stato di autenticazione
if "authed" not in st.session_state:
    st.session_state.authed = False
    st.session_state.username = None

# 2) Se non sei autenticato, mostra SOLO il login e poi blocca
if not st.session_state.authed:
    st.title("🔒 Login")
    username = st.text_input("Username", key="login_user")
    password = st.text_input("Password", type="password", key="login_pwd")
    if st.button("Accedi", key="login_btn"):
        if username in CREDENTIALS and CREDENTIALS[username] == password:
            st.session_state.authed = True
            st.session_state.username = username
        else:
            st.error("⚠️ Username o password errati")
    # Qui fermiamo tutto il resto finché non si fa login
    st.stop()

# 3) Da qui in poi sei autenticato: il form di login non viene più neanche disegnato
st.sidebar.success(f"Benvenuto, {st.session_state.username}")
if st.sidebar.button("Logout"):
    st.session_state.authed = False
    st.session_state.username = None
    # La prossima interazione ricadrà nel blocco di login

# ——— Configurazione Streamlit ———
st.set_page_config(page_title="AdLaunch", layout="wide")

# ——— Logging ———
LOG_FILE = os.path.join(os.path.dirname(__file__), "adlaunch_debug.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s"
)
logging.debug("App start")


def clean_id(raw: str) -> str:
    """
    Da "Name (act_123)" o "act_123" restituisce "123".
    """
    val = raw.split("(")[-1].rstrip(")")
    if hasattr(val, "removeprefix"):
        return val.removeprefix("act_")
    return val[4:] if val.startswith("act_") else val


# ——— Fetch risorse iniziali ———
api_dbg = APIHelper()
accounts = fetch_ad_accounts()
pages    = fetch_pages()

# ——— Sidebar: selezione Account, Pagina e Pixel ———
st.sidebar.header("⚙️ Configurazione")

# 1️⃣ Ad Account
acc_opts = [f"{a['name']} ({a['id']})" for a in accounts]
sel_acc  = st.sidebar.selectbox("1️⃣ Ad Account", acc_opts)
ad_account_id       = clean_id(sel_acc)
ad_account_endpoint = f"act_{ad_account_id}"

# 2️⃣ Pagina Facebook
page_opts = [f"{p['name']} ({p['id']})" for p in pages]
sel_page  = st.sidebar.selectbox("2️⃣ Pagina FB", page_opts)
page_idx  = page_opts.index(sel_page)
page_id   = pages[page_idx]["id"]
page_token= pages[page_idx]["access_token"]

# 3️⃣ Pixel: filtro solo quelli assegnati al system user
try:
    pix_resp   = api_dbg.make_get_request(
        f"{ad_account_endpoint}/adspixels",
        params={"fields": "id,name"}
    )
    all_pixels = pix_resp.get("data", [])
except Exception as e:
    st.sidebar.error(f"❌ Errore fetch pixels: {e}")
    all_pixels = []

# ID del system user
try:
    me_resp        = api_dbg.make_get_request("me", params={"fields": "id"})
    system_user_id = me_resp.get("id")
except Exception:
    system_user_id = None

assigned_pixels = []
for px in all_pixels:
    try:
        resp = api_dbg.make_get_request(
            f"{px['id']}/assigned_users",
            params={"fields": "id", "business": st.secrets["FB_BUSINESS_ID"]}
        )
        users = resp.get("data", [])
        if system_user_id and any(u["id"] == system_user_id for u in users):
            assigned_pixels.append(px)
    except Exception as e:
        logging.warning(f"Skip pixel {px['id']}: {e}")

if not assigned_pixels:
    st.sidebar.warning("⚠️ Nessun Pixel assegnato trovato per il tuo user.")

pix_opts  = [f"{px['name']} ({px['id']})" for px in assigned_pixels]
sel_pixel = st.sidebar.selectbox("3️⃣ Pixel", pix_opts)
pixel_id  = clean_id(sel_pixel)

# ——— Sidebar: scelta Campagna e AdSet ———
camp_mode  = st.sidebar.radio("❓ Gestione Campagna", ("Crea nuova campagna", "Usa campagna esistente"))
adset_mode = st.sidebar.radio("❓ Gestione AdSet",    ("Crea nuovi AdSet",     "Usa AdSet esistenti"))

# 4️⃣ Campagna esistente
if camp_mode == "Usa campagna esistente":
    try:
        resp      = api_dbg.make_get_request(
            f"{ad_account_endpoint}/campaigns",
            params={"fields": "id,name", "limit": 100}
        )
        campaigns = resp.get("data", [])
    except Exception as e:
        st.sidebar.error(f"❌ Impossibile recuperare campagne: {e}")
        campaigns = []
    camp_opts = [f"{c['name']} ({c['id']})" for c in campaigns]
    sel_camp  = st.sidebar.selectbox("4️⃣ Seleziona Campagna", camp_opts)
    if sel_camp:
        st.session_state.campaign_id = clean_id(sel_camp)

# 5️⃣ AdSet esistenti
if adset_mode == "Usa AdSet esistenti":
    if "campaign_id" in st.session_state:
        try:
            resp   = api_dbg.make_get_request(
                f"{st.session_state.campaign_id}/adsets",
                params={"fields": "id,name", "limit": 100}
            )
            adsets = resp.get("data", [])
        except Exception as e:
            st.sidebar.error(f"❌ Impossibile recuperare AdSet: {e}")
            adsets = []
        as_opts = [f"{a['name']} ({a['id']})" for a in adsets]
        sel_as  = st.sidebar.multiselect("5️⃣ Seleziona AdSet esistenti", as_opts)
        if sel_as:
            st.session_state.adset_ids_existing = [clean_id(x) for x in sel_as]
    else:
        st.sidebar.warning("🚨 Seleziona o crea prima una campagna.")

if st.sidebar.button("🔍 Mostra session_state"):
    st.sidebar.json(dict(st.session_state))


# ——— 1) Campagna ———

st.header("📣 1) Campagna")
if camp_mode == "Crea nuova campagna":
    camp_name    = st.text_input("Nome campagna")
    obj_map      = {
        "Conversions": "OUTCOME_SALES",
        "Traffic":     "OUTCOME_TRAFFIC",
        "Engagement":  "OUTCOME_ENGAGEMENT",
        "Leads":       "OUTCOME_LEADS"
    }
    objective    = obj_map[st.selectbox("Obiettivo campagna", list(obj_map.keys()))]
    daily_budget = st.number_input("Budget giornaliero (€)", min_value=1.0, value=10.0, step=1.0)
    strat_map    = {
        "Lowest cost (no cap)":       "LOWEST_COST_WITHOUT_CAP",
        "Lowest cost (with bid cap)": "LOWEST_COST_WITH_BID_CAP",
        "Cost cap":                   "COST_CAP",
        "Lowest cost (min ROAS)":     "LOWEST_COST_WITH_MIN_ROAS"
    }
    bid_strategy = strat_map[st.selectbox("Strategia di offerta", list(strat_map.keys()))]

    if st.button("🚀 Crea Campagna"):
        try:
            cid = create_campaign(
                name=camp_name,
                objective=objective,
                status="PAUSED",
                account_id=ad_account_id,
                daily_budget=daily_budget,
                bid_strategy=bid_strategy
            )
            st.success(f"✅ Campagna creata! ID: {cid}")
            st.session_state.campaign_id = cid
        except Exception as e:
            st.error(f"❌ Errore creazione campagna: {e}")
            st.text(traceback.format_exc())
elif "campaign_id" in st.session_state:
    st.success(f"✅ Campagna selezionata: ID {st.session_state.campaign_id}")
else:
    st.warning("🚨 Seleziona o crea prima una campagna.")



# ——— 1) Adset ———
st.markdown("---")
st.header("🎯 2) AdSet")

if "campaign_id" not in st.session_state:
    st.warning("🚨 Prima scegli o crea una campagna.")
else:
    if adset_mode == "Crea nuovi AdSet":
        # — Nome e targeting geografico —
        as_name = st.text_input("Nome AdSet", key="as_name")
        EUROPE = {
            'Austria':'AT','Belgium':'BE','Bulgaria':'BG','Croatia':'HR','Cyprus':'CY',
            'Czech Republic':'CZ','Denmark':'DK','Estonia':'EE','Finland':'FI','France':'FR',
            'Germany':'DE','Greece':'GR','Hungary':'HU','Ireland':'IE','Italy':'IT',
            'Latvia':'LV','Lithuania':'LT','Luxembourg':'LU','Malta':'MT','Netherlands':'NL',
            'Poland':'PL','Portugal':'PT','Romania':'RO','Slovakia':'SK','Slovenia':'SI',
            'Spain':'ES','Sweden':'SE'
        }
        sel_countries = st.multiselect(
            "Seleziona paesi",
            options=list(EUROPE.keys()),
            key="sel_countries"
        )
        countries = [EUROPE[c] for c in sel_countries]

        # — Esclusione isole Portogallo mediante coordinate e raggio —
        if "Portugal" in sel_countries:
            exclude_islands = st.checkbox(
                "Escludi isole (Azores, Madeira, Porto Santo)",
                value=True,
                help="Esclude cerchi di 80 km intorno ai principali centri delle isole"
            )
            if exclude_islands:
                excluded_custom_locations = [
                    {"lat": 32.6669, "lon": -16.9241, "radius": 80},  # Funchal
                    {"lat": 32.99,   "lon": -16.39,   "radius": 80},  # Porto Santo
                    {"lat": 38.60,   "lon": -28.02,   "radius": 80},  # Calheta
                    {"lat": 37.7412, "lon": -25.6756, "radius": 80},  # Ponta Delgada
                    {"lat": 38.76,   "lon": -27.26,   "radius": 80},  # Praia da Vitória
                    {"lat": 39.45,   "lon": -31.17,   "radius": 80},  # Santa Cruz das Flores
                    {"lat": 36.99,   "lon": -25.09,   "radius": 80}   # Vila do Porto
                ]
            else:
                excluded_custom_locations = []
        else:
            excluded_custom_locations = []

        # — Esclusione isole Spagna mediante coordinate e raggio —
        if "Spain" in sel_countries:
            exclude_islands = st.checkbox(
                "Escludi isole spagnole",
                value=True,
                help="Esclude cerchi di 80 km intorno ai principali centri delle isole"
            )
            if exclude_islands:
                excluded_custom_locations = [
                    {"lat": 39.94,   "lon": 4.11,   "radius": 80},  # Alayor, Balearic Islands
                    {"lat": 38.90,   "lon": 1.40,   "radius": 80},  # Ibiza
                    {"lat": 39.56,   "lon": 3.08,   "radius": 80},  # Villafranca De Bonany
                    {"lat": 35.8880, "lon": -5.3146, "radius": 21},  # Ceuta
                    {"lat": 35.1751, "lon": -2.9313, "radius": 80},  # Melilla
                    {"lat": 28.69,   "lon": -17.86,  "radius": 80},  # El Paso, Canary Islands
                    {"lat": 27.75,   "lon": -18.02,  "radius": 80},  # Frontera, Canary Islands
                    {"lat": 28.23,   "lon": -16.67,  "radius": 80},  # La Orotava
                    {"lat": 28.48,   "lon": -13.99,  "radius": 80},  # Puerto Del Rosario
                    {"lat": 29.07,   "lon": -13.55,  "radius": 80},  # Teguise
                    {"lat": 27.76,   "lon": -15.58,  "radius": 80},  # Puerto Rico
                ]
            else:
                excluded_custom_locations = []
        else:
            excluded_custom_locations = []



        # — Conversion event & optimization goal —
        evt_map = {"Purchase":"PURCHASE", "Lead":"LEAD", "Complete Registration":"COMPLETE_REGISTRATION"}
        event = evt_map[st.selectbox("Evento di conversione", list(evt_map.keys()), key="evt")]

        opt_map = {
            "Offsite Conversions":"OFFSITE_CONVERSIONS","Link Clicks":"LINK_CLICKS",
            "Landing Page Views":"LANDING_PAGE_VIEWS","Page Likes":"PAGE_LIKES",
            "Post Engagement":"POST_ENGAGEMENT","Video Views":"VIDEO_VIEWS",
            "Impressions":"IMPRESSIONS","Reach":"REACH","Lead Generation":"LEAD_GENERATION",
            "Value":"VALUE"
        }
        optimization_goal = opt_map[st.selectbox("Obiettivo ottimizzazione",
                                                 list(opt_map.keys()), key="opt")]

        # — Placements, attribution, bid —
        placement_mode = st.radio("Posizionamenti", ("Advantage+","Manual"), key="placement_mode")
        manual = []
        if placement_mode == "Manual":
            PLACEMENTS = ['facebook_feed','instagram_feed','instagram_story','facebook_story',
                          'audience_network','messenger','facebook_reels','instagram_reels']
            manual = st.multiselect("Manual placements", options=PLACEMENTS, key="man")
        advantage = (placement_mode == "Advantage+")

        use_attr = st.checkbox("Usa attribuzione standard (7d click + 1d view)", value=True)
        attribution_spec = (
            [{"event_type":"CLICK_THROUGH","window_days":7},
             {"event_type":"VIEW_THROUGH","window_days":1}]
            if use_attr else []
        )

        bid_amount_eur = st.number_input("Limite offerta (€)", min_value=0.0, step=0.1, value=0.0)
        bid_amount = int(bid_amount_eur*100) if bid_amount_eur>0 else None

        # — Creazione AdSet —
        if st.button("🚀 Crea AdSet"):
            try:
                aid = create_adset(
                    ad_account_id=ad_account_id,
                    campaign_id=st.session_state.campaign_id,
                    name=as_name,
                    countries=countries or None,
                    pixel_id=pixel_id,
                    event=event,
                    optimization_goal=optimization_goal,
                    bid_amount=bid_amount,
                    advantage_placement=advantage,
                    placements=manual,
                    attribution_spec=attribution_spec,
                    excluded_custom_locations=excluded_custom_locations
                )
                st.success(f"✅ AdSet creato! ID: {aid}")
                st.session_state.adset_id = aid
                st.session_state.adset_config = {
                    "name": as_name, "countries": countries, "pixel_id": pixel_id,
                    "event": event, "optimization_goal": optimization_goal,
                    "bid_amount": bid_amount, "advantage_placement": advantage,
                    "placements": manual, "attribution_spec": attribution_spec,
                    "excluded_custom_locations": excluded_custom_locations
                }
            except Exception as e:
                st.error(f"❌ Errore creazione AdSet: {e}")
                st.text(traceback.format_exc())
    else:
        if st.session_state.get("adset_ids_existing"):
            st.success(f"✅ AdSet selezionati: {st.session_state.adset_ids_existing}")
        else:
            st.info("Seleziona almeno un AdSet esistente nella sidebar.")

# Utility per montare gli UTM
import urllib.parse

def build_utm_url(base_url, utm_params):
    parsed = urllib.parse.urlparse(base_url)
    qs = dict(urllib.parse.parse_qsl(parsed.query))
    qs.update({k: v for k, v in utm_params.items() if v})
    new_query = urllib.parse.urlencode(qs)
    return urllib.parse.urlunparse(parsed._replace(query=new_query))

# ——— 3) Bulk Creatività ———
st.markdown("---")
st.header("🎨 3) Crea creatività e distribuisci")

# Input UTM fissi
utm_source   = st.text.input("utm_source",   value="newsletter")
utm_medium   = st.text.input("utm_medium",   value="email")
utm_campaign = st.text.input("utm_campaign", value="summer_sale")
utm_base = {
    "utm_source":   utm_source,
    "utm_medium":   utm_medium,
    "utm_campaign": utm_campaign
}

if adset_mode == "Usa AdSet esistenti":
    files        = st.file_uploader("Carica file (jpg/png/mp4)", type=["jpg","jpeg","png","mp4"], accept_multiple_files=True)
    primary_text = st.text_area("Testo principale comune")
    headline     = st.text_input("Titolo comune")
    description  = st.text_input("Descrizione comune (solo immagini)")
    common_url   = st.text_input("URL comune")
    cta          = "LEARN_MORE"

    if st.button("🚀 Aggiungi creatività"):
        if not files:
            st.error("🚨 Nessun file caricato.")
        else:
            adset_ids = st.session_state.adset_ids_existing
            total     = len(files)
            m         = len(adset_ids)
            base      = total // m
            rem       = total % m
            sizes     = [base + (1 if i < rem else 0) for i in range(m)]
            idx       = 0

            for i, adset_id in enumerate(adset_ids):
                chunk      = files[idx: idx + sizes[i]]
                idx       += sizes[i]
                adset_name = str(adset_id)  # oppure recupera il nome via API

                for f in chunk:
                    try:
                        name = os.path.splitext(f.name)[0]
                        ext  = os.path.splitext(f.name)[1].lower()
                        tmp  = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
                        tmp.write(f.getbuffer()); tmp.close()

                        # upload e thumbnail/video
                        if ext == ".mp4":
                            media_id = upload_video(ad_account_id, tmp.name)
                            cap      = cv2.VideoCapture(tmp.name)
                            ok, frame = cap.read(); cap.release()
                            if not ok:
                                raise Exception("Impossibile estrarre frame")
                            tmp_th     = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                            cv2.imwrite(tmp_th.name, frame)
                            thumb_hash = upload_image(ad_account_id, tmp_th.name)
                            is_video   = True
                        else:
                            thumb_hash = None
                            media_id   = upload_image(ad_account_id, tmp.name)
                            is_video   = False

                        # UTM dinamici
                        utm = utm_base.copy()
                        utm["utm_content"] = adset_name
                        utm["utm_term"]    = name
                        link_with_utm      = build_utm_url(common_url, utm)

                        # crea la creatività
                        creative_id = create_ad_creative(
                            ad_account_id=ad_account_id,
                            page_id=page_id,
                            page_token=page_token,
                            media_id=media_id,
                            primary_text=primary_text,
                            headline=headline,
                            link_url=link_with_utm,
                            creative_name=name,
                            call_to_action=cta,
                            description=None if is_video else description,
                            is_video=is_video,
                            thumbnail_hash=thumb_hash
                        )

                        # crea l'ad
                        ad_id = create_ad(
                            ad_account_id=ad_account_id,
                            adset_id=adset_id,
                            creative_id=creative_id,
                            name=name
                        )
                        st.write(f"✅ '{name}' → AdSet {adset_id}, Ad {ad_id}")
                    except Exception as e:
                        st.error(f"{f.name}: {e}")

            st.success(f"Tutte le {total} creatività aggiunte su {m} AdSet")

else:
    files        = st.file_uploader("Carica file (jpg/png/mp4)", type=["jpg","jpeg","png","mp4"], accept_multiple_files=True)
    primary_text = st.text_area("Testo principale comune")
    headline     = st.text_input("Titolo comune")
    description  = st.text_input("Descrizione comune (solo immagini)")
    common_url   = st.text_input("URL comune")
    cta          = "LEARN_MORE"
    per_adset    = st.number_input("Quante creatività per ogni AdSet?", min_value=1, value=3, step=1)

    if st.button("🚀 Invia e distribuisci"):
        if not files:
            st.error("🚨 Nessun file caricato.")
        else:
            chunks        = [files[i:i+per_adset] for i in range(0, len(files), per_adset)]
            all_adset_ids = []
            cfg           = st.session_state.adset_config

            for idx, chunk in enumerate(chunks):
                if idx == 0:
                    adset_id   = st.session_state.adset_id
                    adset_name = cfg["name"]
                else:
                    new_name = f"{cfg['name']}_{idx+1}"
                    adset_id = create_adset(
                        ad_account_id=ad_account_id,
                        campaign_id=st.session_state.campaign_id,
                        name=new_name,
                        countries=cfg["countries"],
                        pixel_id=cfg["pixel_id"],
                        event=cfg["event"],
                        optimization_goal=cfg["optimization_goal"],
                        bid_amount=cfg["bid_amount"],
                        advantage_placement=cfg["advantage_placement"],
                        placements=cfg["placements"],
                        attribution_spec=cfg["attribution_spec"]
                    )
                    adset_name = new_name

                all_adset_ids.append(adset_id)

                for f in chunk:
                    try:
                        name = os.path.splitext(f.name)[0]
                        ext  = os.path.splitext(f.name)[1].lower()
                        tmp  = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
                        tmp.write(f.getbuffer()); tmp.close()

                        # upload e thumbnail/video
                        if ext == ".mp4":
                            media_id = upload_video(ad_account_id, tmp.name)
                            cap      = cv2.VideoCapture(tmp.name)
                            ok, frame = cap.read(); cap.release()
                            if not ok:
                                raise Exception("Impossibile estrarre frame")
                            tmp_th     = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                            cv2.imwrite(tmp_th.name, frame)
                            thumb_hash = upload_image(ad_account_id, tmp_th.name)
                            is_video   = True
                        else:
                            thumb_hash = None
                            media_id   = upload_image(ad_account_id, tmp.name)
                            is_video   = False

                        # UTM dinamici
                        utm = utm_base.copy()
                        utm["utm_content"] = adset_name
                        utm["utm_term"]    = name
                        link_with_utm      = build_utm_url(common_url, utm)

                        creative_id = create_ad_creative(
                            ad_account_id=ad_account_id,
                            page_id=page_id,
                            page_token=page_token,
                            media_id=media_id,
                            primary_text=primary_text,
                            headline=headline,
                            link_url=link_with_utm,
                            creative_name=name,
                            call_to_action=cta,
                            description=None if is_video else description,
                            is_video=is_video,
                            thumbnail_hash=thumb_hash
                        )
                        ad_id = create_ad(
                            ad_account_id=ad_account_id,
                            adset_id=adset_id,
                            creative_id=creative_id,
                            name=name
                        )
                        st.write(f"✅ '{name}' → AdSet {adset_id}, Ad {ad_id}")
                    except Exception as e:
                        st.error(f"{f.name}: {e}")

            st.success(f"Tutti i file distribuiti in {len(all_adset_ids)} AdSet")


logging.debug("App end")
