import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "games.json"


def load_games():

    with open(
        CONFIG_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


def get_game(name):

    return load_games().get(name)


def get_games():

    return load_games()


def find_game_folder(source_root, game_name):

    root = Path(source_root)

    if not root.exists():
        return None

    aliases = {
        "Fortnite": [
            "فورتنايت (Fortnite)",
            "Fortnite"
        ],

        "Genshin Impact": [
            "جينشن امباكت (Genshin Impact)",
            "Genshin Impact"
        ],

        "eFootball": [
            "بيس (eFootball™)",
            "eFootball",
            "eFootball™"
        ],

        "Free Fire": [
            "فري فاير (free fire)",
            "free fire",
            "Free Fire"
        ],

        "PUBG Mobile": [
            "ببجي (PUBG)",
            "PUBG",
            "PUBG Mobile"
        ],

        "Call of Duty Mobile": [
            "كول اوف ديوتي (call of duty)",
            "call of duty",
            "Call of Duty"
        ],

        "Grand Theft Auto": [
            "جراند ثفت اوتو (Grand Theft Auto)",
            "Grand Theft Auto",
            "GTA"
        ]
    }

    names = aliases.get(
        game_name,
        [game_name]
    )

    folders = {
        item.name: item
        for item in root.iterdir()
        if item.is_dir()
    }

    for name in names:

        if name in folders:
            return folders[name]

    lowered = {
        item.name.lower(): item
        for item in folders.values()
    }

    for name in names:

        result = lowered.get(name.lower())

        if result:
            return result

    return None
