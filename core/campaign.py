# core/campaign.py

from utils.api_helpers import APIHelper

api_helper = APIHelper()

def create_campaign(name: str,
                    objective: str,
                    status: str,
                    account_id: str,
                    daily_budget: float,
                    bid_strategy: str) -> str:
    """
    Crea una campagna su Meta e restituisce l'ID della campagna.

    Params:
    - name: Nome della campagna
    - objective: Obiettivo di business (es. CONVERSIONS, LINK_CLICKS...)
    - status: 'PAUSED' o 'ACTIVE'
    - account_id: ID numerico dell'Ad Account (senza 'act_')
    - daily_budget: budget giornaliero in euro
    - bid_strategy: strategia di offerta (es. 'LOWEST_COST_WITHOUT_CAP')
    """

    # Endpoint su cui fare POST
    endpoint = f"act_{account_id}/campaigns"

    # Meta API vuole il budget in centesimi
    budget_in_cents = int(daily_budget * 100)

    # Costruiamo il payload, includendo special_ad_categories=[] per default
    payload = {
        "name": name,
        "objective": objective,
        "status": status,
        "daily_budget": budget_in_cents,
        "bid_strategy": bid_strategy,
        "special_ad_categories": []  # obbligatorio anche se non rientri in categorie speciali
    }

    response = api_helper.make_post_request(endpoint, payload)
    return response.get("id")
