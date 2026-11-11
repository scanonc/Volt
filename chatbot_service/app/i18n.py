from gettext import translation
from pathlib import Path


english = translation('messages', Path(__file__).parent / 'locale', languages=['en'])


def translate(message, language):
    return english.gettext(message) if language == 'en' else message
