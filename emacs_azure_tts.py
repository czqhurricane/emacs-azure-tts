# 来源 https://github.com/OS984/DiscordBotBackend/blob/3b06b8be39e4dbc07722b0afefeee4c18c136102/NeuralTTS.py
# A completely innocent attempt to borrow proprietary Microsoft technology for a much better TTS experience
import requests
import websockets
import asyncio
from datetime import datetime
import time
import re
import uuid
import tempfile
import os
import string
import json

from PyDeepLX import PyDeepLX
from utils import (eval_in_emacs, message_emacs, get_emacs_var)

deeplx_api = "http://127.0.0.1:1188/translate"


# Fix the time to match Americanisms
def hr_cr(hr):
    corrected = (hr - 1) % 24
    return str(corrected)

# Add zeros in the right places i.e 22:1:5 -> 22:01:05
def fr(input_string):
    corr = ''
    i = 2 - len(input_string)
    while (i > 0):
        corr += '0'
        i -= 1
    return corr + input_string

# Generate X-Timestamp all correctly formatted
def getXTime():
    now = datetime.now()
    return fr(str(now.year)) + '-' + fr(str(now.month)) + '-' + fr(str(now.day)) + 'T' + fr(hr_cr(int(now.hour))) + ':' + fr(str(now.minute)) + ':' + fr(str(now.second)) + '.' + str(now.microsecond)[:3] + 'Z'

def get_SSML(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

# Async function for actually communicating with the websocket
async def transferMsTTSData(sentence, SSML_text, full_output_path, not_after_speak):
    req_id = uuid.uuid4().hex.upper()
    print(req_id)
    # TOKEN来源 https://github.com/rany2/edge-tts/blob/master/src/edge_tts/constants.py
    # 查看支持声音列表 https://speech.platform.bing.com/consumer/speech/synthesize/readaloud/voices/list?trustedclienttoken=6A5AA1D4EAFF4E9FB37E23D68491D6F4
    TRUSTED_CLIENT_TOKEN = "6A5AA1D4EAFF4E9FB37E23D68491D6F4"
    WSS_URL = (
        "wss://speech.platform.bing.com/consumer/speech/synthesize/"
        + "readaloud/edge/v1?TrustedClientToken="
        + TRUSTED_CLIENT_TOKEN
    )
    endpoint2 = f"{WSS_URL}&ConnectionId={req_id}"
    async with websockets.connect(endpoint2,extra_headers={
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
        "Origin": "chrome-extension://jdiccldimpdaibmpdkjnbmckianbfold",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/91.0.4472.77 Safari/537.36 Edg/91.0.864.41"}) as websocket:
        message_1 = (
                    f"X-Timestamp:{getXTime()}\r\n"
                    "Content-Type:application/json; charset=utf-8\r\n"
                    "Path:speech.config\r\n\r\n"
                    '{"context":{"synthesis":{"audio":{"metadataoptions":{'
                    '"sentenceBoundaryEnabled":false,"wordBoundaryEnabled":true},'
                    '"outputFormat":"audio-24khz-48kbitrate-mono-mp3"'
                    "}}}}\r\n"
                )
        await websocket.send(message_1)

        message_2 = (
        f"X-RequestId:{req_id}\r\n"
        "Content-Type:application/ssml+xml\r\n"
        f"X-Timestamp:{getXTime()}Z\r\n"  # This is not a mistake, Microsoft Edge bug.
        "Path:ssml\r\n\r\n"
        f"{SSML_text}")
        await websocket.send(message_2)

        # Checks for close connection message
        end_resp_pat = re.compile('Path:turn.end')
        audio_stream = b''
        while(True):
            response = await websocket.recv()
            print('receiving...')
            # print(response)
            # Make sure the message isn't telling us to stop
            if (re.search(end_resp_pat, str(response)) == None):
                # Check if our response is text data or the audio bytes
                if type(response) == type(bytes()):
                    # Extract binary data
                    try:
                        needle = b'Path:audio\r\n'
                        start_ind = response.find(needle) + len(needle)
                        audio_stream += response[start_ind:]
                    except:
                        pass
            else:
                break
        os.makedirs(os.path.dirname(full_output_path), exist_ok=True)
        with open(full_output_path, 'wb') as audio_out:
            audio_out.write(audio_stream)
        message_emacs('Audio already downloaded in: ' + full_output_path)
        if not not_after_speak:
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
            eval_in_emacs('emacs-azure-tts-after-speak', full_output_path, sentence, translation)
            eval_in_emacs('play-sound-file', full_output_path)
            eval_in_emacs("youdao-dictionary--posframe-tip", translation)

async def mainSeq(sentence, SSML_text, full_output_path, not_after_speak):
    await transferMsTTSData(sentence, SSML_text, full_output_path, not_after_speak)

def run(sentence, audio_file, not_after_speak):
    SSML_file = get_emacs_var('emacs-azure-tts-SSML-file')
    audio_directory = get_emacs_var('emacs-azure-tts-audio-dir')
    content = {'content': sentence}
    SSML_text = string.Template(get_SSML(SSML_file)).substitute(content)
    file_name = 'emacs_azure_tts_' + str(int(time.time()*1000))

    if audio_directory:
        full_output_path = audio_file or os.path.join(audio_directory, file_name + '.mp3')
    else:
        full_output_path = audio_file or os.path.join(tempfile.gettempdir(), file_name + '.mp3')

    asyncio.run(mainSeq(sentence, SSML_text, full_output_path, not_after_speak))

    print('completed')
