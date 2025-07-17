import os
import sys

venv_py = os.path.join(os.path.dirname(__file__), "venv", "Scripts", "python.exe")
if os.path.isfile(venv_py):
    # normalizzo i path a confronto
    current = os.path.normcase(sys.executable)
    target  = os.path.normcase(venv_py)
    if current != target:
        os.execv(venv_py, [venv_py] + sys.argv)

os.environ['STREAMLIT_SERVER_HEADLESS']   = "true"
os.environ['STREAMLIT_SERVER_ADDRESS']    = "127.0.0.1"
os.environ['STREAMLIT_SERVER_PORT']       = "8501"
os.environ['STREAMLIT_SERVER_ENABLECORS'] = "false"

import tempfile
import cv2

import streamlit as st
from facebook_business.api import FacebookAdsApi

# Aggiungi il path al modulo ui se serve
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "ui")))

import logging
import traceback

from core.campaign import create_campaign
from core.adset import create_adset
from core.creative import upload_image, upload_video, create_ad_creative, create_ad
from core.meta_data import fetch_ad_accounts, fetch_pages
from utils.api_helpers import APIHelper
from config.settings import AD_ACCOUNT_ID

# ——— Configurazione Streamlit ———
st.set_page_config(page_title="AdLaunch", layout="wide")

# ——— Inizializza FacebookAdsApi ———
app_id         = st.secrets.get("APP_ID")
app_secret     = st.secrets.get("APP_SECRET")
access_token   = st.secrets.get("META_ACCESS_TOKEN")
fb_business_id = st.secrets.get("fb_business_id")
api_version    = st.secrets.get("fb_api_version", "v15.0")

if not all([app_id, app_secret, access_token, fb_business_id]):
    st.error(
        "❌ Mancano chiavi in secrets.toml: "
        "APP_ID, APP_SECRET, META_ACCESS_TOKEN o fb_business_id"
    )
    st.stop()

FacebookAdsApi.init(app_id, app_secret, access_token, api_version=api_version)

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
    Rimuove eventuali prefissi 'act_' o parentesi da stringhe tipo
    'Name (act_12345)' o semplici 'act_12345', restituendo solo la parte numerica.
    """
    val = raw.split("(")[-1].rstrip(")")
    if hasattr(val, "removeprefix"):
        val = val.removeprefix("act_")
    else:
        if val.startswith("act_"):
            val = val[4:]
    return val


# ——— Fetch risorse iniziali ———
accounts = fetch_ad_accounts()
pages    = fetch_pages()
api_dbg  = APIHelper()

# ——— Sidebar: selezione Account, Pagina e Pixel ———
st.sidebar.header("⚙️ Configurazione")

# 1) Ad Account (mostro solo il nome per evitare tooltip ingombranti)
sel_acc = st.sidebar.selectbox(
    "1️⃣ Ad Account",
    accounts,
    format_func=lambda x: x["name"]
)
ad_account_endpoint = sel_acc["id"]          # es. "act_123456789"
ad_account_id       = clean_id(ad_account_endpoint)

# 2) Pagina Facebook
sel_page = st.sidebar.selectbox(
    "2️⃣ Pagina FB",
    pages,
    format_func=lambda x: x["name"]
)
page_id    = sel_page["id"]
page_token = sel_page["access_token"]

# 3) Pixel: recupera e filtra solo quelli assegnati al System User
pix_resp      = api_dbg.make_get_request(
    f"{ad_account_endpoint}/adspixels",
    params={"fields": "id,name"}
)
all_pixels    = pix_resp.get("data", [])
me_resp       = api_dbg.make_get_request("me", params={"fields": "id"})
system_user_id = me_resp.get("id")

pixels = []
for px in all_pixels:
    assigned = api_dbg.make_get_request(
        f"{px['id']}/assigned_users",
        params={"fields": "id", "business": fb_business_id}
    ).get("data", [])
    if any(u["id"] == system_user_id for u in assigned):
        pixels.append(px)

sel_pixel = st.sidebar.selectbox(
    "3️⃣ Pixel",
    pixels,
    format_func=lambda x: x["name"]
)
pixel_id = sel_pixel["id"]

# ——— Sidebar: scelta Campagna e AdSet ———
camp_mode  = st.sidebar.radio(
    "❓ Gestione Campagna",
    ("Crea nuova campagna", "Usa campagna esistente")
)
adset_mode = st.sidebar.radio(
    "❓ Gestione AdSet",
    ("Crea nuovi AdSet", "Usa AdSet esistenti")
)

# 4) Campagne esistenti
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
    sel_camp = st.sidebar.selectbox(
        "4️⃣ Seleziona Campagna",
        campaigns,
        format_func=lambda x: x["name"]
    )
    if sel_camp:
        st.session_state.campaign_id = sel_camp["id"]

# 5) AdSet esistenti
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
        sel_as = st.sidebar.multiselect(
            "5️⃣ Seleziona AdSet esistenti",
            adsets,
            format_func=lambda x: x["name"]
        )
        if sel_as:
            st.session_state.adset_ids_existing = [a["id"] for a in sel_as]
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


# ——— 2) AdSet ———
st.markdown("---")
st.header("🎯 2) AdSet")
if "campaign_id" not in st.session_state:
    st.warning("🚨 Prima scegli o crea una campagna.")
else:
    if adset_mode == "Crea nuovi AdSet":
        as_name = st.text_input("Nome AdSet", key="as_name")
        EUROPE = {
            'Austria':'AT','Belgium':'BE','Bulgaria':'BG','Croatia':'HR','Cyprus':'CY',
            'Czech Republic':'CZ','Denmark':'DK','Estonia':'EE','Finland':'FI','France':'FR',
            'Germany':'DE','Greece':'GR','Hungary':'HU','Ireland':'IE','Italy':'IT',
            'Latvia':'LV','Lithuania':'LT','Luxembourg':'LU','Malta':'MT','Netherlands':'NL',
            'Poland':'PL','Portugal':'PT','Romania':'RO','Slovakia':'SK','Slovenia':'SI',
            'Spain':'ES','Sweden':'SE'
        }
        countries = [EUROPE[c] for c in st.multiselect("Seleziona paesi", list(EUROPE.keys()))]
        evt_map   = {"Purchase":"PURCHASE","Lead":"LEAD","Complete Registration":"COMPLETE_REGISTRATION"}
        event     = evt_map[st.selectbox("Evento di conversione", list(evt_map.keys()), key="evt")]
        opt_map   = {
            "Offsite Conversions":"OFFSITE_CONVERSIONS","Link Clicks":"LINK_CLICKS",
            "Landing Page Views":"LANDING_PAGE_VIEWS","Page Likes":"PAGE_LIKES",
            "Post Engagement":"POST_ENGAGEMENT","Video Views":"VIDEO_VIEWS",
            "Impressions":"IMPRESSIONS","Reach":"REACH","Lead Generation":"LEAD_GENERATION",
            "Value":"VALUE"
        }
        optimization_goal = opt_map[st.selectbox("Obiettivo ottimizzazione", list(opt_map.keys()), key="opt")]
        mode      = st.radio("Posizionamenti", ("Advantage+","Manual"), key="placement_mode")
        manual    = []
        if mode == "Manual":
            PLACEMENTS = [  
                'facebook_feed','instagram_feed','instagram_story','facebook_story',
                'audience_network','messenger','facebook_reels','instagram_reels'
            ]
            manual = st.multiselect("Manual placements", PLACEMENTS, key="man")
        advantage = (mode == "Advantage+")
        use_attr  = st.checkbox("Usa attribuzione standard (7d click + 1d view)", value=True)
        attribution_spec = (
            [{"event_type":"CLICK_THROUGH","window_days":7},
             {"event_type":"VIEW_THROUGH","window_days":1}]
            if use_attr else []
        )
        bid_amount_eur = st.number_input("Limite offerta (€)", min_value=0.0, step=0.1, value=0.0)
        bid_amount     = int(bid_amount_eur * 100) if bid_amount_eur > 0 else None

        if st.button("🚀 Crea AdSet"):
            try:
                aid = create_adset(
                    ad_account_id=ad_account_id,
                    campaign_id=st.session_state.campaign_id,
                    name=as_name,
                    countries=countries,
                    pixel_id=pixel_id,
                    event=event,
                    optimization_goal=optimization_goal,
                    bid_amount=bid_amount,
                    advantage_placement=advantage,
                    placements=manual,
                    attribution_spec=attribution_spec
                )
                st.success(f"✅ AdSet creato! ID: {aid}")
                st.session_state.adset_id     = aid
                st.session_state.adset_config = {
                    "name": as_name, "countries": countries,
                    "pixel_id": pixel_id, "event": event,
                    "optimization_goal": optimization_goal,
                    "bid_amount": bid_amount,
                    "advantage_placement": advantage,
                    "placements": manual,
                    "attribution_spec": attribution_spec
                }
            except Exception as e:
                st.error(f"❌ Errore creazione AdSet: {e}")
                st.text(traceback.format_exc())
    else:
        if "adset_ids_existing" in st.session_state and st.session_state.adset_ids_existing:
            st.success(f"✅ AdSet selezionati: {st.session_state.adset_ids_existing}")
        else:
            st.info("Seleziona almeno un AdSet esistente nella sidebar.")


# ——— 3) Bulk Creatività ———
st.markdown("---")
st.header("🎨 3) Crea creatività e distribuisci")

if adset_mode == "Usa AdSet esistenti":
    if "adset_ids_existing" not in st.session_state or not st.session_state.adset_ids_existing:
        st.warning("🚨 Seleziona almeno un AdSet esistente.")
    else:
        primary_text = st.text_area("Testo principale comune")
        headline     = st.text_input("Titolo comune")
        description  = st.text_input("Descrizione comune (solo immagini)")
        common_url   = st.text_input("URL comune")
        cta          = "LEARN_MORE"
        files        = st.file_uploader(
            "Carica file (jpg/png/mp4)",
            type=["jpg","jpeg","png","mp4"],
            accept_multiple_files=True
        )

        if st.button("🚀 Aggiungi creatività"):
            if not files:
                st.error("🚨 Nessun file caricato.")
            else:
                total     = len(files)
                adset_ids = st.session_state.adset_ids_existing
                m         = len(adset_ids)
                base      = total // m
                rem       = total % m
                sizes     = [base + (1 if i < rem else 0) for i in range(m)]
                idx       = 0

                for i, adset_id in enumerate(adset_ids):
                    chunk = files[idx : idx + sizes[i]]
                    idx  += sizes[i]
                    for f in chunk:
                        try:
                            name = os.path.splitext(f.name)[0]
                            ext  = os.path.splitext(f.name)[1].lower()
                            tmp  = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
                            tmp.write(f.getbuffer()); tmp.close()
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

                            creative_id = create_ad_creative(
                                ad_account_id=ad_account_id,
                                page_id=page_id,
                                page_token=page_token,
                                media_id=media_id,
                                primary_text=primary_text,
                                headline=headline,
                                link_url=common_url,
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
                st.success(f"Tutte le {total} creatività aggiunte su {m} AdSet")
else:
    primary_text = st.text_area("Testo principale comune")
    headline     = st.text_input("Titolo comune")
    description  = st.text_input("Descrizione comune (solo immagini)")
    common_url   = st.text_input("URL comune")
    cta          = "LEARN_MORE"
    files        = st.file_uploader(
        "Carica file (jpg/png/mp4)",
        type=["jpg","jpeg","png","mp4"],
        accept_multiple_files=True
    )
    per_adset    = st.number_input("Quante creatività per AdSet?", min_value=1, value=3, step=1)

    if st.button("🚀 Invia e distribuisci"):
        if not files:
            st.error("🚨 Nessun file caricato.")
        else:
            chunks        = [files[i : i + per_adset] for i in range(0, len(files), per_adset)]
            all_adset_ids = []
            for idx, chunk in enumerate(chunks):
                if idx == 0:
                    adset_id = st.session_state.adset_id
                else:
                    cfg      = st.session_state.adset_config
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
                all_adset_ids.append(adset_id)
                for f in chunk:
                    try:
                        name = os.path.splitext(f.name)[0]
                        ext  = os.path.splitext(f.name)[1].lower()
                        tmp  = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
                        tmp.write(f.getbuffer()); tmp.close()
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

                        creative_id = create_ad_creative(
                            ad_account_id=ad_accountiolet,
                            page_id=page_id,
                            page_token=page_token,
                            media_id=media_id,
                            primary_text=primary_text,
                            headline=headline,
                            link_url=common_url,
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
