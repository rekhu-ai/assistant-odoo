"""What the users read from the module itself, in their language: the locale the widget sends, else the Odoo user's
language. English, Arabic and Dutch; anything else is English."""

MESSAGES = {
    'en': {
        'working': 'Working on it…',
        'help': 'Looking in the help…',
        'searching': 'Looking it up…',
        'unavailable': 'The assistant is not available right now. Please try again in a moment.',
        'empty': 'Say something first.',
        'off': 'The assistant is switched off. An administrator turns it on under Settings → Rekhu Assistant.',
        'busy': 'That was a lot of messages at once. Wait a minute and try again.',
    },
    'ar': {
        'working': 'جارٍ العمل على ذلك…',
        'help': 'أبحث في المساعدة…',
        'searching': 'أبحث عن ذلك…',
        'unavailable': 'المساعد غير متاح الآن. حاول مرة أخرى بعد قليل.',
        'empty': 'اكتب شيئاً أولاً.',
        'off': 'المساعد متوقف. يقوم المسؤول بتشغيله من الإعدادات ← Rekhu Assistant.',
        'busy': 'رسائل كثيرة في وقت واحد. انتظر دقيقة ثم حاول مرة أخرى.',
    },
    'nl': {
        'working': 'Ik ben ermee bezig…',
        'help': 'Ik zoek in de hulp…',
        'searching': 'Ik zoek het op…',
        'unavailable': 'De assistent is nu niet beschikbaar. Probeer het zo opnieuw.',
        'empty': 'Typ eerst iets.',
        'off': 'De assistent staat uit. Een beheerder zet hem aan onder Instellingen → Rekhu Assistant.',
        'busy': 'Dat waren veel berichten tegelijk. Wacht even en probeer het opnieuw.',
    },
}


def language_of(tag):
    """'ar-SA,ar;q=0.9' or 'ar_SY' → 'ar'; a language without messages → None."""
    first = str(tag or '').split(',')[0].strip().lower().replace('_', '-').split('-')[0].split(';')[0]
    return first if first in MESSAGES else None


def message(key, *tags):
    lang = next((language_of(t) for t in tags if language_of(t)), 'en')
    return MESSAGES[lang].get(key) or MESSAGES['en'][key]
