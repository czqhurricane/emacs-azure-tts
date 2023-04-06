import asyncio
import time
import os
import tempfile

import edge_tts
from utils import (eval_in_emacs, message_emacs, get_emacs_var)

VOICE = 'en-US-GuyNeural'


async def _main(sentence, file_name) -> None:
    communicate = edge_tts.Communicate(sentence, VOICE)
    audio_directory = get_emacs_var('emacs-azure-tts-audio-dir')
    if audio_directory:
        full_output_path = os.path.join(audio_directory, file_name + '.mp3')
    else:
        full_output_path = os.path.join(tempfile.gettempdir(), file_name + '.mp3')
    await communicate.save(full_output_path)
    eval_in_emacs('play-sound-file', full_output_path)
    message_emacs('Audio already downloaded in: ' + full_output_path)
    eval_in_emacs('emacs-azure-tts-after-speak', full_output_path, sentence)


def run(sentence):
    file_name = 'emacs_azure_tts' + str(int(time.time()*1000))
    asyncio.run(_main(sentence, file_name))
