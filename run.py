import logging
from TwitchChannelPointsMiner import TwitchChannelPointsMiner
from TwitchChannelPointsMiner.logger import LoggerSettings, ColorPalette
from TwitchChannelPointsMiner.classes.entities.Bet import Strategy, BetSettings, Condition, OutcomeKeys, FilterCondition, DelayMode
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer, StreamerSettings

twitch_miner = TwitchChannelPointsMiner(
    username="barflyy_",
    password="tyqqyuvcmm7r670i5bnil3rw580n8d",  # Le token copié
    claim_drops_startup=False,
    priority=[
        # Liste des streamers à miner
        Streamer("streamer1"),
        Streamer("streamer2"),
    ],
    logger_settings=LoggerSettings(
        save=True,
        console_level=logging.INFO,
        file_level=logging.DEBUG,
        emoji=True,
        colored=True,
        color_palette=ColorPalette(
            STREAMER_online="green",
            streamer_offline="red"
        )
    )
)

twitch_miner.mine()
