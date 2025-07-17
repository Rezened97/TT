import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from facebook_business.adobjects.business import Business
from facebook_business.adobjects.adspixel import AdsPixel
from facebook_business.exceptions import FacebookRequestError
from utils.api_helpers import APIHelper
from config.settings import AD_ACCOUNT_ID

api_helper = APIHelper()


def fetch_ad_accounts():
    """
    Ritorna la lista di ad accounts legati all'utente di sistema:
    [{ 'id': 'act_...', 'name': 'Nome Account' }, ...]
    """
    data = api_helper.make_get_request(
        "me/adaccounts",
        params={"fields": "id,name"}
    )
    return data.get("data", [])



def fetch_pages():
    """
    Ritorna la lista di Pagine collegate all'utente di sistema,
    incluse le page access token:
    [{ 'id': '12345', 'name': 'Pagina FB', 'access_token': '...' }, ...]
    """
    data = api_helper.make_get_request(
        "me/accounts",
        params={"fields": "id,name,access_token"}
    )
    return data.get("data", [])


def fetch_pixels(business_id=None):
    """
    Recupera tutti i Facebook Pixels associati al Business, 
    gestendo eventuale paginazione.

    Se business_id è None, usa AD_ACCOUNT_ID come fallback (ma è consigliato passare l'id del business).
    Restituisce una lista di dict: [{ 'id': '123456789', 'name': 'MyPixel' }, …]
    """
    # Inizializza API se necessario (assumi già init in app.py)
    # FacebookAdsApi.init(app_id, app_secret, access_token)

    # Determina business_id
    biz_id = business_id or AD_ACCOUNT_ID
    biz = Business(biz_id)
    all_pixels = []
    try:
        # prima pagina owned pixels
        pixels = biz.get_owned_pixels(fields=[
            AdsPixel.Field.id,
            AdsPixel.Field.name,
        ])
        all_pixels.extend(pixels)

        # paginazione
        while pixels.load_next_page():
            pixels = pixels.load_next_page()
            all_pixels.extend(pixels)

    except FacebookRequestError as e:
        # log error o mostra a console
        print(f"Errore fetching pixels: {e.body}")
        return []

    # mappa in lista di dict puliti
    return [
        { 'id': p[AdsPixel.Field.id], 'name': p[AdsPixel.Field.name] }
        for p in all_pixels
    ]
