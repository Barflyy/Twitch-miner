# event_logger.py
import logging
from TwitchChannelPointsMiner.classes.entities.Streamer import Streamer as OriginalStreamer

class StreamerWrapper:
    """Wrapper pour intercepter les changements d'état des streamers"""
    
    def __init__(self, original_streamer, discord_webhook):
        self.streamer = original_streamer
        self.discord = discord_webhook
        self._online = False
    
    def __getattr__(self, name):
        return getattr(self.streamer, name)
    
    def set_online(self, online, game=None):
        """Intercepte le changement d'état online/offline"""
        was_online = self._online
        self._online = online
        
        # Appeler la méthode originale
        if hasattr(self.streamer, 'set_online'):
            self.streamer.set_online(online, game)
        
        # Notifier Discord
        if online and not was_online:
            self.discord.on_event("streamer_online", {
                "streamer": {"username": self.streamer.username},
                "game": {"name": game or "Unknown"},
                "title": getattr(self.streamer, 'title', '')
            })
        elif not online and was_online:
            self.discord.on_event("streamer_offline", {
                "streamer": {"username": self.streamer.username}
            })

def patch_streamer_for_discord(streamer_objects, discord_webhook):
    """Patch les streamers pour capturer les events"""
    wrapped = []
    for streamer in streamer_objects:
        wrapped.append(StreamerWrapper(streamer, discord_webhook))
    return wrapped