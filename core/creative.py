import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import requests
from typing import Optional
from auth.token_manager import TokenManager
from utils.api_helpers import APIHelper

api_helper = APIHelper()


def upload_image(ad_account_id: str, image_path: str) -> str:
    """
    Carica un’immagine su Meta e restituisce lo "image_hash".
    """
    token = TokenManager().access_token
    url = f"https://graph.facebook.com/v19.0/act_{ad_account_id}/adimages"
    headers = {"Authorization": f"Bearer {token}"}
    with open(image_path, "rb") as f:
        files = {"source": f}
        r = requests.post(url, headers=headers, files=files)
    data = r.json()
    if "images" not in data:
        raise Exception(f"Errore upload immagine: {data}")
    # Prende l'hash della prima immagine ritornata
    return next(iter(data["images"].values()))["hash"]


def upload_video(ad_account_id: str, video_path: str) -> str:
    """
    Carica un video su Meta e restituisce l'ID del video.
    """
    token = TokenManager().access_token
    url = f"https://graph.facebook.com/v19.0/act_{ad_account_id}/advideos"
    headers = {"Authorization": f"Bearer {token}"}
    with open(video_path, "rb") as f:
        files = {"source": f}
        r = requests.post(url, headers=headers, files=files)
    data = r.json()
    if "id" not in data:
        raise Exception(f"Errore upload video: {data}")
    return data["id"]


def create_ad_creative(
    ad_account_id: str,
    page_id: str,
    page_token: str,
    media_id: str,
    primary_text: str,
    headline: str,
    link_url: str,
    creative_name: str,
    call_to_action: str,
    description: Optional[str] = None,
    is_video: bool = False,
    thumbnail_hash: Optional[str] = None
) -> str:
    """
    Crea un AdCreative (immagine o video) e restituisce il suo ID.
    
    - page_token: Page Access Token, necessario per associare la creative alla Pagina.
    - media_id: hash per immagini, ID per video.
    - thumbnail_hash: obbligatorio per video_data (hash di un’immagine di anteprima).
    """
    url = f"https://graph.facebook.com/v19.0/act_{ad_account_id}/adcreatives"
    params = {"access_token": page_token}

    # Costruisci l’object_story_spec a seconda se è video o immagine
    if is_video:
        if not thumbnail_hash:
            raise Exception("Thumbnail image_hash richiesto per video_data")
        story_spec = {
            "page_id": page_id,
            "video_data": {
                "video_id": media_id,
                "image_hash": thumbnail_hash,
                "title": headline,
                "message": primary_text,
                "call_to_action": {
                    "type": call_to_action,
                    "value": {"link": link_url}
                }
            }
        }
    else:
        story_spec = {
            "page_id": page_id,
            "link_data": {
                "image_hash": media_id,
                "link": link_url,
                "message": primary_text,
                "name": headline,
                "description": description or "",
                "call_to_action": {"type": call_to_action}
            }
        }

    payload = {
        "name": creative_name,
        "object_story_spec": story_spec
    }

    # POST vero e proprio
    r = requests.post(url, params=params, json=payload)
    data = r.json()
    if "id" not in data:
        raise Exception(f"Errore AdCreative: {data}")
    return data["id"]


def create_ad(
    ad_account_id: str,
    adset_id: str,
    creative_id: str,
    name: Optional[str] = None
) -> str:
    """
    Crea l’Ad finale sotto l’AdSet specificato, usando la creative data.
    """
    endpoint = f"act_{ad_account_id}/ads"
    payload = {
        "adset_id": adset_id,
        "creative": {"creative_id": creative_id},
        "status": "ACTIVE"  # o "PAUSED" se preferisci
    }
    if name:
        payload["name"] = name

    response = api_helper.make_post_request(endpoint, payload)
    ad_id = response.get("id")
    if not ad_id:
        raise Exception(f"Nessun ID Ad restituito: {response}")
    return ad_id
