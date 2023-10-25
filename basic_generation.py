import asyncio
import time
import os
import tempfile
import requests
import json

import edge_tts
from utils import (eval_in_emacs, message_emacs, get_emacs_var)
from PyDeepLX import PyDeepLX

VOICE = 'en-US-GuyNeural'
deeplx_api = "http://127.0.0.1:1188/translate"


async def _main(sentence, file_name) -> None:
    communicate = edge_tts.Communicate(sentence, VOICE)
    audio_directory = get_emacs_var('emacs-azure-tts-audio-dir')
    data = {
        "text": sentence,
        "source_lang": "EN",
        "target_lang": "ZH"
    }
    post_data = json.dumps(data)
    try:
        translation = PyDeepLX.translate(text=sentence, sourceLang="EN", targetLang="ZH", numberAlternative=0, printResult=False, proxies="Http://0.0.0.0:8118")
    except:
        translation = json.loads(requests.post(url = deeplx_api, data=post_data).text)["data"]
    if audio_directory:
        full_output_path = os.path.join(audio_directory, file_name + '.mp3')
    else:
        full_output_path = os.path.join(tempfile.gettempdir(), file_name + '.mp3')
    await communicate.save(full_output_path)
    eval_in_emacs('emacs-azure-tts-after-speak', full_output_path, sentence, translation)
    eval_in_emacs('play-sound-file', full_output_path)
    eval_in_emacs("youdao-dictionary--posframe-tip", translation)
    message_emacs('Audio already downloaded in: ' + full_output_path)


def run(sentence):
    file_name = 'emacs_azure_tts' + str(int(time.time()*1000))
    asyncio.run(_main(sentence, file_name))
