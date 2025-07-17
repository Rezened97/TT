import sys, os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from typing import Optional, List, Dict
from utils.api_helpers import APIHelper

from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.adset import AdSet
from facebook_business.api import FacebookAdsApi

api_helper = APIHelper()


def create_adset(
    ad_account_id: str,
    campaign_id: str,
    name: str,
    countries: List[str],
    pixel_id: str,
    event: str,
    optimization_goal: str,
    daily_budget: Optional[float] = None,
    billing_event: Optional[str] = None,
    bid_amount: Optional[int] = None,
    advantage_placement: bool = False,
    placements: Optional[List[str]] = None,
    attribution_spec: Optional[List[Dict[str, int]]] = None,
    excluded_custom_locations: Optional[List[Dict[str, float]]] = None
) -> str:
    """
    Crea un AdSet sotto un Ad Account e restituisce l'ID.

    Params:
    - ad_account_id: ID numerico dell'Ad Account (senza 'act_')
    - campaign_id: ID della campagna padre
    - name: nome dell'AdSet
    - countries: lista di codici paese ISO (es. ['IT','FR'])
    - pixel_id: ID del pixel
    - event: custom_event_type (es. 'PURCHASE')
    - optimization_goal: obiettivo di ottimizzazione valido
    - daily_budget: budget giornaliero in euro (opzionale)
    - billing_event: evento di fatturazione (opzionale), default 'IMPRESSIONS'
    - bid_amount: importo massimo offerta in centesimi (opzionale)
    - advantage_placement: se True usa Advantage+ placements
    - placements: lista di publisher_platforms (opzionale se advantage_placement False)
    - attribution_spec: lista di dict per finestra di attribuzione
    - excluded_custom_locations: lista di dict con chiavi 'lat','lon','radius'
    """
    # billing_event default
    if billing_event is None:
        billing_event = "IMPRESSIONS"

    endpoint = f"act_{ad_account_id}/adsets"

    # Costruzione del payload base
    payload = {
        "name": name,
        "campaign_id": campaign_id,
        "optimization_goal": optimization_goal,
        "billing_event": billing_event,
        "promoted_object": {
            "pixel_id": pixel_id,
            "custom_event_type": event
        },
        "targeting": {
            "geo_locations": {"countries": countries}
        },
        "special_ad_categories": []
    }

    # Esclusione di aree personalizzate tramite coordinate e raggio
    if excluded_custom_locations:
        payload["targeting"]["excluded_geo_locations"] = {
            "custom_locations": [
                {
                    "latitude": loc["lat"],
                    "longitude": loc["lon"],
                    "radius": loc["radius"],
                    "distance_unit": "kilometer"
                }
                for loc in excluded_custom_locations
            ]
        }

    # Posizionamenti
    if advantage_placement:
        payload["advantage_plus_placement"] = True
    elif placements:
        payload["publisher_platforms"] = placements

    # Finestra di attribuzione
    if attribution_spec:
        payload["attribution_spec"] = attribution_spec

    # Budget e offerta
    if daily_budget is not None:
        payload["daily_budget"] = int(daily_budget * 100)
    if bid_amount is not None:
        payload["bid_amount"] = bid_amount

    # Invio della richiesta
    response = api_helper.make_post_request(endpoint, payload)
    return response.get("id")