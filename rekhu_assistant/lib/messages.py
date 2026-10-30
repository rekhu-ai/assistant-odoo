"""What the users read from the module itself, in their language: the locale the widget sends, else the Odoo user's
language. English, Arabic and Dutch; anything else is English."""

MESSAGES = {
    'en': {
        'working': 'Working on it…',
        'help': 'Looking in the help…',
        'searching': 'Looking it up…',
        'unavailable': 'The assistant cannot be reached right now. Please try again in a moment.',
        'overloaded': 'The assistant is very busy right now. Please try again in a minute.',
        'paused': 'The assistant is paused or has reached its limit for this month. Please let the administrator of this app know.',
        'credit': 'The assistant is switched off for now because its plan needs attention. Please let the administrator of this app know.',
        'conversation': 'Something went wrong in this conversation. Please start a new chat.',
        'too_big': 'This request needs more steps than one answer allows, so I stopped here. Say "continue" to go on, or split it into smaller parts, for example a few at a time.',
        'empty': 'Say something first.',
        'off': 'The assistant is switched off. An administrator turns it on under Settings → Rekhu Assistant.',
        'busy': 'That was a lot of messages at once. Wait a minute and try again.',
    },
    'ar': {
        'working': 'جارٍ العمل على ذلك…',
        'help': 'أبحث في المساعدة…',
        'searching': 'أبحث عن ذلك…',
        'unavailable': 'تعذّر الوصول إلى المساعد الآن. حاول مرة أخرى بعد قليل.',
        'overloaded': 'المساعد مشغول جدًا الآن. حاول مرة أخرى بعد دقيقة.',
        'paused': 'المساعد متوقف مؤقتًا أو وصل إلى حدّه لهذا الشهر. يُرجى إبلاغ مسؤول هذا التطبيق.',
        'credit': 'المساعد متوقف حاليًا لأن اشتراكه يحتاج إلى مراجعة. يُرجى إبلاغ مسؤول هذا التطبيق.',
        'conversation': 'حدث خطأ في هذه المحادثة. يُرجى بدء محادثة جديدة.',
        'too_big': 'هذا الطلب يحتاج إلى خطوات أكثر مما تسمح به إجابة واحدة، لذلك توقفت هنا. اكتب «تابِع» للمتابعة، أو قسّم الطلب إلى أجزاء أصغر، مثلًا بضعة عناصر في كل مرة.',
        'empty': 'اكتب شيئاً أولاً.',
        'off': 'المساعد متوقف. يقوم المسؤول بتشغيله من الإعدادات ← Rekhu Assistant.',
        'busy': 'رسائل كثيرة في وقت واحد. انتظر دقيقة ثم حاول مرة أخرى.',
    },
    'nl': {
        'working': 'Ik ben ermee bezig…',
        'help': 'Ik zoek in de hulp…',
        'searching': 'Ik zoek het op…',
        'unavailable': 'De assistent is nu niet bereikbaar. Probeer het zo opnieuw.',
        'overloaded': 'De assistent is nu erg druk. Probeer het over een minuut opnieuw.',
        'paused': 'De assistent staat op pauze of heeft zijn limiet voor deze maand bereikt. Laat het de beheerder van deze app weten.',
        'credit': 'De assistent staat voorlopig uit, omdat het abonnement aandacht nodig heeft. Laat het de beheerder van deze app weten.',
        'conversation': 'Er ging iets mis in dit gesprek. Begin een nieuwe chat.',
        'too_big': 'Dit verzoek vraagt meer stappen dan één antwoord toestaat, dus ik ben hier gestopt. Zeg "ga door" om verder te gaan, of splits het op in kleinere delen, bijvoorbeeld een paar tegelijk.',
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
