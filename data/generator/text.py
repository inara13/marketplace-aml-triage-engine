"""Listing titles and descriptions, including the suspicious wording used by
some typologies. All wording is generic and invented, with no real brands."""

ADJ = ["vintage", "y2k", "retro", "oversized", "cropped", "classic", "rare", "90s",
       "handmade", "minimal", "distressed", "like new", "gently used", "bnwt"]
NOUN = {
    "tops": ["graphic tee", "band tee", "knit sweater", "baby tee", "hoodie", "flannel shirt"],
    "jeans": ["straight leg jeans", "flared jeans", "mom jeans", "cargo denim", "baggy jeans"],
    "dresses": ["slip dress", "floral midi dress", "mini dress", "knit dress", "wrap dress"],
    "vintage_jackets": ["denim jacket", "leather jacket", "bomber jacket", "suede jacket"],
    "sneakers": ["high top sneakers", "running shoes", "court sneakers", "retro trainers"],
    "accessories": ["beaded necklace", "bucket hat", "silk scarf", "leather belt", "tote bag"],
    "luxury_bags": ["designer shoulder bag", "leather handbag", "quilted crossbody", "top handle bag"],
    "electronics": ["wireless headphones", "film camera", "handheld console", "smartwatch", "tablet"],
    "collectibles": ["trading card lot", "vinyl record", "vintage figurine", "comic issue", "enamel pin set"],
}
CONDITION = ["Good condition, small mark on the back.", "Worn twice, no flaws.",
             "Brand new with tags, never worn.", "Some fading, adds character.",
             "Great condition, from a smoke free home.", "Minor pilling, priced to sell.",
             "Tested and working perfectly.", "Light wear on the corners."]
SIZE = ["XS", "S", "M", "L", "XL", "UK 8", "US 10", "one size"]
SLANG = ["fire fit", "grail piece", "so cute", "must go", "no lowballs pls",
         "bundle to save", "open to offers", "ships fast"]

# Trade based laundering: no detail, just a price
VAGUE = ["Item as shown. Price is firm.", "As pictured. No questions please.",
         "Price firm, buyer knows the deal.", "Selling as is. Final price."]

# Coded or off platform listings, by difficulty
CODED = {
    "easy": ["Placeholder listing. Message me on telegram before buying, real item sent separately.",
             "Do not buy unless instructed. Contact on whatsapp for details.",
             "This is not the actual item. Pay here, details off app.",
             "Listing for payment only, no item will be shipped."],
    "medium": ["Reserved listing, price reflects prior arrangement. Please do not buy unless we spoke.",
               "Custom order for a returning client. Terms agreed privately.",
               "Special listing for J. Price includes extras discussed."],
    "hard": ["Digital download, no shipping needed.", "Instant delivery by message after purchase.",
             "Service listing, delivered digitally."],
}

# Genuine collector wording, used by the luxury collector decoy
DETAILED = ["Authenticated piece with original receipt and dust bag. Serial number documented, "
            "price reflects rarity and condition.",
            "From a private collection, stored carefully for years. Full provenance available, "
            "happy to share more photos.",
            "Rare early edition in excellent condition. Graded and sleeved, see photos for details."]


def title(rng, category):
    return f"{rng.choice(ADJ)} {rng.choice(NOUN[category])}"


def description(rng):
    parts = [str(rng.choice(CONDITION)), f"Size {rng.choice(SIZE)}."]
    if rng.random() < 0.5:
        parts.append(f"{rng.choice(SLANG)}.")
    return " ".join(parts)


def vague(rng):
    return str(rng.choice(VAGUE))


def coded(rng, difficulty):
    return str(rng.choice(CODED[difficulty]))


def detailed(rng):
    return str(rng.choice(DETAILED))


def add_typo(rng, s):
    """Swap two neighbouring letters in one word, like a quick phone typo."""
    words = s.split(" ")
    idx = [i for i, w in enumerate(words) if len(w) > 3]
    if not idx:
        return s
    i = int(rng.choice(idx))
    w = words[i]
    j = int(rng.integers(0, len(w) - 1))
    words[i] = w[:j] + w[j + 1] + w[j] + w[j + 2:]
    return " ".join(words)
