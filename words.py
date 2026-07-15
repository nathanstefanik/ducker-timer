import secrets

WORDS = [
    "mallard", "teal", "wigeon", "pintail", "eider", "scaup",
    "smew", "goldeneye", "merganser", "shoveler", "gadwall", "pochard",
    "ruddy", "wood", "muscovy", "pekin", "cayuga", "drake",
    "duckling", "feather", "preen", "waddle", "paddle", "splash",
    "ripple", "pond", "puddle", "creek", "marsh", "reed",
    "rush", "sedge", "lily", "lotus", "algae", "minnow",
    "tadpole", "dragonfly", "mayfly", "cattail", "willow", "pebble",
    "mossy", "misty", "foggy", "dewy", "muddy", "sunny",
    "breezy", "drizzly", "quack", "honk", "whistle", "dabble",
    "dive", "float", "glide", "skim", "nibble", "wade",
]


def new_code():
    return f"{secrets.choice(WORDS)}-{secrets.choice(WORDS)}-{secrets.choice(WORDS)}"
