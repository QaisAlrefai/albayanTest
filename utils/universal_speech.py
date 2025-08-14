import  UniversalSpeech as u_speech
from utils.settings import Config
from utils.logger import LoggerManager
logger = LoggerManager.get_logger(__name__)

class UniversalSpeech:
    logger.debug("Initializing UniversalSpeech")
    universal_speech = u_speech.UniversalSpeech()
    logger.debug("UniversalSpeech initialized")
    universal_speech.enable_native_speech(False)
    reader = universal_speech.engine_used
    logger.debug(f"Using screen reader: {reader}")

    @classmethod
    def say(cls, msg: str, interrupt: bool = True, force: bool = False) -> None:
        if Config.audio.speak_actions_enabled or force:
            cls.universal_speech.say(msg, interrupt)
            logger.debug(f"Speaking: {msg} (Interrupt: {interrupt}, Force: {force})")
        else:
            logger.debug(f"Speech action skipped. Message: '{msg}' (Force: {force})")