# api_helpers.py

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import requests
import json

from auth.token_manager import TokenManager
from config.settings import API_VERSION, AD_ACCOUNT_ID


class APIHelper:
    """
    Fornisce metodi per effettuare chiamate POST e GET e gestire le risposte della Meta Marketing API.
    """
    def __init__(self):
        self.token_manager = TokenManager()
        self.base_url = f"https://graph.facebook.com/{API_VERSION}/"

    def make_post_request(self, endpoint: str, payload: dict) -> dict:
        """
        Esegue una chiamata POST all'endpoint specificato con il payload fornito.

        :param endpoint: stringa dell'endpoint, es. 'act_<AD_ACCOUNT_ID>/campaigns'
        :param payload: dizionario con i parametri da inviare in JSON
        :return: dizionario JSON della risposta se successo
        :raises Exception: in caso di errore HTTP o risposta non OK
        """
        url = self.base_url + endpoint
        headers = self.token_manager.get_headers()
        response = requests.post(url, json=payload, headers=headers)
        return self.handle_response(response)

    def make_get_request(self, endpoint: str, params: dict = None) -> dict:
        """
        Esegue una chiamata GET all'endpoint specificato.

        :param endpoint: stringa dell'endpoint, es. 'me/adaccounts'
        :param params: dizionario dei parametri querystring
        :return: dizionario JSON della risposta
        :raises Exception: in caso di errore HTTP
        """
        url = self.base_url + endpoint
        headers = self.token_manager.get_headers()
        response = requests.get(url, params=params or {}, headers=headers)
        return self.handle_response(response)

    def handle_response(self, response: requests.Response) -> dict:
        """
        Controlla lo status HTTP e ritorna il JSON se tutto OK, altrimenti solleva un'eccezione dettagliata.

        :param response: oggetto Response di requests
        :return: dizionario JSON della risposta
        :raises Exception: in caso di status code non 2xx
        """
        if 200 <= response.status_code < 300:
            try:
                return response.json()
            except json.JSONDecodeError:
                raise Exception(f"Risposta ricevuta non è JSON: {response.text}")
        else:
            try:
                error_info = response.json().get("error", response.text)
            except json.JSONDecodeError:
                error_info = response.text
            raise Exception(f"Errore API {response.status_code}: {error_info}")
