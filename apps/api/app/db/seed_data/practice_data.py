"""Curated practice data: verb conjugations and example sentences.

Hand-checked rather than derived from the CSV, because the source CSV leaves
part-of-speech blank on nearly every row (so "ayer"/yesterday would be mistaken
for an -er verb by any naive ending heuristic).

Conjugations cover present, preterite, and future for the persons Polyglot
quizzes. Regular verbs are generated from their stem; irregulars are written out.
"""
from __future__ import annotations

PERSONS = ("yo", "tú", "él/ella", "nosotros", "vosotros", "ellos/ellas")

# Regular endings by conjugation class and tense.
REGULAR_ENDINGS = {
    "ar": {
        "present":   ("o", "as", "a", "amos", "áis", "an"),
        "preterite": ("é", "aste", "ó", "amos", "asteis", "aron"),
        "future":    ("é", "ás", "á", "emos", "éis", "án"),      # added to infinitive
    },
    "er": {
        "present":   ("o", "es", "e", "emos", "éis", "en"),
        "preterite": ("í", "iste", "ió", "imos", "isteis", "ieron"),
        "future":    ("é", "ás", "á", "emos", "éis", "án"),
    },
    "ir": {
        "present":   ("o", "es", "e", "imos", "ís", "en"),
        "preterite": ("í", "iste", "ió", "imos", "isteis", "ieron"),
        "future":    ("é", "ás", "á", "emos", "éis", "án"),
    },
}

# Regular verbs present in the curriculum, by class.
REGULAR_VERBS: dict[str, str] = {
    # -ar
    "caminar": "ar", "trabajar": "ar", "estudiar": "ar", "usar": "ar",
    "ayudar": "ar", "comprar": "ar", "entrar": "ar", "llamar": "ar",
    "tomar": "ar", "cocinar": "ar", "hablar": "ar", "bailar": "ar",
    "cantar": "ar", "escuchar": "ar", "mirar": "ar", "necesitar": "ar",
    # -er
    "comer": "er", "beber": "er", "aprender": "er", "vender": "er",
    "comprender": "er", "correr": "er", "leer": "er", "creer": "er",
    # -ir
    "vivir": "ir", "escribir": "ir", "abrir": "ir", "recibir": "ir",
    "subir": "ir", "decidir": "ir",
}

# Irregular verbs — written out because their forms don't follow the pattern.
IRREGULAR_VERBS: dict[str, dict[str, dict[str, str]]] = {
    "ser": {
        "present": {"yo": "soy", "tú": "eres", "él/ella": "es",
                    "nosotros": "somos", "vosotros": "sois", "ellos/ellas": "son"},
        "preterite": {"yo": "fui", "tú": "fuiste", "él/ella": "fue",
                      "nosotros": "fuimos", "vosotros": "fuisteis", "ellos/ellas": "fueron"},
        "future": {"yo": "seré", "tú": "serás", "él/ella": "será",
                   "nosotros": "seremos", "vosotros": "seréis", "ellos/ellas": "serán"},
    },
    "estar": {
        "present": {"yo": "estoy", "tú": "estás", "él/ella": "está",
                    "nosotros": "estamos", "vosotros": "estáis", "ellos/ellas": "están"},
        "preterite": {"yo": "estuve", "tú": "estuviste", "él/ella": "estuvo",
                      "nosotros": "estuvimos", "vosotros": "estuvisteis",
                      "ellos/ellas": "estuvieron"},
        "future": {"yo": "estaré", "tú": "estarás", "él/ella": "estará",
                   "nosotros": "estaremos", "vosotros": "estaréis", "ellos/ellas": "estarán"},
    },
    "tener": {
        "present": {"yo": "tengo", "tú": "tienes", "él/ella": "tiene",
                    "nosotros": "tenemos", "vosotros": "tenéis", "ellos/ellas": "tienen"},
        "preterite": {"yo": "tuve", "tú": "tuviste", "él/ella": "tuvo",
                      "nosotros": "tuvimos", "vosotros": "tuvisteis", "ellos/ellas": "tuvieron"},
        "future": {"yo": "tendré", "tú": "tendrás", "él/ella": "tendrá",
                   "nosotros": "tendremos", "vosotros": "tendréis", "ellos/ellas": "tendrán"},
    },
    "hacer": {
        "present": {"yo": "hago", "tú": "haces", "él/ella": "hace",
                    "nosotros": "hacemos", "vosotros": "hacéis", "ellos/ellas": "hacen"},
        "preterite": {"yo": "hice", "tú": "hiciste", "él/ella": "hizo",
                      "nosotros": "hicimos", "vosotros": "hicisteis", "ellos/ellas": "hicieron"},
        "future": {"yo": "haré", "tú": "harás", "él/ella": "hará",
                   "nosotros": "haremos", "vosotros": "haréis", "ellos/ellas": "harán"},
    },
    "ir": {
        "present": {"yo": "voy", "tú": "vas", "él/ella": "va",
                    "nosotros": "vamos", "vosotros": "vais", "ellos/ellas": "van"},
        "preterite": {"yo": "fui", "tú": "fuiste", "él/ella": "fue",
                      "nosotros": "fuimos", "vosotros": "fuisteis", "ellos/ellas": "fueron"},
        "future": {"yo": "iré", "tú": "irás", "él/ella": "irá",
                   "nosotros": "iremos", "vosotros": "iréis", "ellos/ellas": "irán"},
    },
    "querer": {
        "present": {"yo": "quiero", "tú": "quieres", "él/ella": "quiere",
                    "nosotros": "queremos", "vosotros": "queréis", "ellos/ellas": "quieren"},
        "preterite": {"yo": "quise", "tú": "quisiste", "él/ella": "quiso",
                      "nosotros": "quisimos", "vosotros": "quisisteis", "ellos/ellas": "quisieron"},
        "future": {"yo": "querré", "tú": "querrás", "él/ella": "querrá",
                   "nosotros": "querremos", "vosotros": "querréis", "ellos/ellas": "querrán"},
    },
    "poder": {
        "present": {"yo": "puedo", "tú": "puedes", "él/ella": "puede",
                    "nosotros": "podemos", "vosotros": "podéis", "ellos/ellas": "pueden"},
        "preterite": {"yo": "pude", "tú": "pudiste", "él/ella": "pudo",
                      "nosotros": "pudimos", "vosotros": "pudisteis", "ellos/ellas": "pudieron"},
        "future": {"yo": "podré", "tú": "podrás", "él/ella": "podrá",
                   "nosotros": "podremos", "vosotros": "podréis", "ellos/ellas": "podrán"},
    },
    "pagar": {
        "present": {"yo": "pago", "tú": "pagas", "él/ella": "paga",
                    "nosotros": "pagamos", "vosotros": "pagáis", "ellos/ellas": "pagan"},
        "preterite": {"yo": "pagué", "tú": "pagaste", "él/ella": "pagó",
                      "nosotros": "pagamos", "vosotros": "pagasteis", "ellos/ellas": "pagaron"},
        "future": {"yo": "pagaré", "tú": "pagarás", "él/ella": "pagará",
                   "nosotros": "pagaremos", "vosotros": "pagaréis", "ellos/ellas": "pagarán"},
    },
    "llegar": {
        "present": {"yo": "llego", "tú": "llegas", "él/ella": "llega",
                    "nosotros": "llegamos", "vosotros": "llegáis", "ellos/ellas": "llegan"},
        "preterite": {"yo": "llegué", "tú": "llegaste", "él/ella": "llegó",
                      "nosotros": "llegamos", "vosotros": "llegasteis", "ellos/ellas": "llegaron"},
        "future": {"yo": "llegaré", "tú": "llegarás", "él/ella": "llegará",
                   "nosotros": "llegaremos", "vosotros": "llegaréis", "ellos/ellas": "llegarán"},
    },
    "contar": {
        "present": {"yo": "cuento", "tú": "cuentas", "él/ella": "cuenta",
                    "nosotros": "contamos", "vosotros": "contáis", "ellos/ellas": "cuentan"},
        "preterite": {"yo": "conté", "tú": "contaste", "él/ella": "contó",
                      "nosotros": "contamos", "vosotros": "contasteis", "ellos/ellas": "contaron"},
        "future": {"yo": "contaré", "tú": "contarás", "él/ella": "contará",
                   "nosotros": "contaremos", "vosotros": "contaréis", "ellos/ellas": "contarán"},
    },
}


def conjugate_regular(infinitive: str, klass: str) -> dict[str, dict[str, str]]:
    """Build the conjugation table for a regular verb from its stem."""
    stem = infinitive[:-2]
    endings = REGULAR_ENDINGS[klass]
    out: dict[str, dict[str, str]] = {}
    for tense, forms in endings.items():
        # Future tense attaches to the FULL infinitive, not the stem.
        base = infinitive if tense == "future" else stem
        out[tense] = {p: base + e for p, e in zip(PERSONS, forms, strict=True)}
    return out


def all_conjugations() -> dict[str, dict]:
    """{infinitive: {"class": .., "regular": bool, "conjugations": {...}}}"""
    out: dict[str, dict] = {}
    for inf, klass in REGULAR_VERBS.items():
        out[inf] = {"class": klass, "regular": True,
                    "conjugations": conjugate_regular(inf, klass)}
    for inf, table in IRREGULAR_VERBS.items():
        klass = inf[-2:] if inf[-2:] in ("ar", "er", "ir") else "irregular"
        out[inf] = {"class": klass, "regular": False, "conjugations": table}
    return out


# Example sentences for fill-in-the-blank practice.
# (spanish, english, target_word) — the target is blanked out in the prompt.
# Targets are chosen from words that ACTUALLY appear in this curriculum (mostly
# colours, adjectives, verbs, and time words); the seeder skips any whose target
# isn't in the database, so unmatched entries are harmless.
EXAMPLE_SENTENCES: list[tuple[str, str, str]] = [
    # colours
    ("El carro es rojo.", "The car is red.", "rojo"),
    ("El cielo es azul.", "The sky is blue.", "azul"),
    ("La planta es verde.", "The plant is green.", "verde"),
    ("El gato es negro.", "The cat is black.", "negro"),
    ("La pared es blanco.", "The wall is white.", "blanco"),
    # size / quality adjectives
    ("Mi cuarto es grande.", "My room is big.", "grande"),
    ("El café está bueno.", "The coffee is good.", "bueno"),
    ("El día está malo.", "The day is bad.", "malo"),
    ("Tengo un carro nuevo.", "I have a new car.", "nuevo"),
    ("Mi abuelo es viejo.", "My grandfather is old.", "viejo"),
    ("Es muy facil para mi.", "It is very easy for me.", "facil"),
    ("El examen es dificil.", "The exam is difficult.", "dificil"),
    ("Es barato en el mercado.", "It is cheap at the market.", "barato"),
    ("Ese reloj es caro.", "That watch is expensive.", "caro"),
    # feelings
    ("Hoy estoy feliz.", "Today I am happy.", "feliz"),
    ("Ella está triste.", "She is sad.", "triste"),
    ("Estoy muy cansado.", "I am very tired.", "cansado"),
    ("Mi hermano es alto.", "My brother is tall.", "alto"),
    ("Ella es joven.", "She is young.", "joven"),
    # quantity
    ("Tengo mucho trabajo.", "I have a lot of work.", "mucho"),
    ("Queda poco tiempo.", "There is little time left.", "poco"),
    # time and place
    ("Hoy vamos al parque.", "Today we go to the park.", "hoy"),
    ("Ayer comí en casa.", "Yesterday I ate at home.", "ayer"),
    ("Ahora quiero descansar.", "Now I want to rest.", "ahora"),
    ("La tienda está cerca.", "The store is nearby.", "cerca"),
    ("Mi casa está lejos.", "My house is far.", "lejos"),
    # verbs in context
    ("Me gusta comer temprano.", "I like to eat early.", "comer"),
    ("Quiero beber agua fría.", "I want to drink cold water.", "beber"),
    ("Me gusta leer por la noche.", "I like to read at night.", "leer"),
    ("Vamos a caminar juntos.", "We are going to walk together.", "caminar"),
    ("Tengo que trabajar mañana.", "I have to work tomorrow.", "trabajar"),
    ("Necesito estudiar para el examen.", "I need to study for the exam.", "estudiar"),
    ("Quiero comprar un regalo.", "I want to buy a gift.", "comprar"),
    ("Ella sabe cocinar muy bien.", "She knows how to cook very well.", "cocinar"),
    ("Quiero vivir en México.", "I want to live in Mexico.", "vivir"),
    ("Voy a escribir una carta.", "I am going to write a letter.", "escribir"),
    ("Puedes abrir la puerta.", "You can open the door.", "abrir"),
    ("Me gusta correr en la mañana.", "I like to run in the morning.", "correr"),
    # greetings / courtesy
    ("Muchas gracias por todo.", "Thank you very much for everything.", "gracias"),
    ("Hola, ¿cómo estás?", "Hello, how are you?", "hola"),
    # months
    ("Mi cumpleaños es en enero.", "My birthday is in January.", "enero"),
    ("Vamos de viaje en julio.", "We travel in July.", "julio"),
]
