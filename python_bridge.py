#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2022 Andy Stewart
#
# Author:     Andy Stewart <lazycat.manatee@gmail.com>
# Maintainer: Andy Stewart <lazycat.manatee@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import queue
import threading
import traceback
import sys
from pathlib import Path
from epc.server import ThreadingEPCServer
from utils import (init_epc_client, eval_in_emacs, logger, close_epc_client, message_emacs)
from python_mpv_jsonipc import MPV
import fitz


class MindWave:
    def __init__(self, args):
        # Init EPC client port.
        init_epc_client(int(args[0]))

        # Build EPC server.
        self.server = ThreadingEPCServer(('localhost', 0), log_traceback=True)
        # self.server.logger.setLevel(logging.DEBUG)
        self.server.allow_reuse_address = True

        # ch = logging.FileHandler(filename=os.path.join(python-bridge_config_dir, 'epc_log.txt'), mode='w')
        # formatter = logging.Formatter('%(asctime)s | %(levelname)-8s | %(lineno)04d | %(message)s')
        # ch.setFormatter(formatter)
        # ch.setLevel(logging.DEBUG)
        # self.server.logger.addHandler(ch)
        # self.server.logger = logger

        self.server.register_instance(self)  # register instance functions let elisp side call

        # Start EPC server with sub-thread, avoid block Qt main loop.
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.start()

        # All Emacs request running in event_loop.
        self.event_queue = queue.Queue()
        self.event_loop = threading.Thread(target=self.event_dispatcher)
        self.event_loop.start()

        # All LSP server response running in message_thread.
        self.message_queue = queue.Queue()
        self.message_thread = threading.Thread(target=self.message_dispatcher)
        self.message_thread.start()

        # Pass epc port and webengine codec information to Emacs when first start python-bridge.
        eval_in_emacs('python-bridge--first-start', self.server.server_address[1])

        # event_loop never exit, simulation event loop.
        self.event_loop.join()

    def event_dispatcher(self):
        try:
            while True:
                message = self.event_queue.get(True)

                if message["name"] == "open_file":
                    self._open_file(message["content"])
                elif message["name"] == "close_file":
                    self._close_file(message["content"])
                elif message["name"] == "action_func":
                    (func_name, func_args) = message["content"]
                    getattr(self, func_name)(*func_args)

                self.event_queue.task_done()
        except:
            logger.error(traceback.format_exc())

    def message_dispatcher(self):
        try:
            while True:
                message = self.message_queue.get(True)
                if message["name"] == "server_process_exit":
                    self.handle_server_process_exit(message["content"])
                else:
                    logger.error("Unhandled python-bridge message: %s" % message)

                self.message_queue.task_done()
        except:
            logger.error(traceback.format_exc())

    def cleanup(self):
        """Do some cleanup before exit python process."""
        close_epc_client()

    def tts(self, args):
        from emacs_azure_tts import run
        # from basic_generation import run
        sentence = args[0]
        audio_file = args[1]
        not_after_speak = args[2]
        run(sentence, audio_file, not_after_speak)

    def deeplx_translate(self, sentence):
        import json
        import requests
        from PyDeepLX import PyDeepLX

        deeplx_api = "http://127.0.0.1:1188/translate"
        data = {
            "text": sentence,
            "source_lang": "EN",
            "target_lang": "ZH"
        }
        post_data = json.dumps(data)

        try:
            translation = PyDeepLX.translate(text=sentence, sourceLang="EN", targetLang="ZH", numberAlternative=0, printResult=False)
        except:
            translation = json.loads(requests.post(url = deeplx_api, data=post_data).text)["data"]
        return translation

    # python3 -m pip install python_mpv_jsonipc
    def mpv_send_sentence_to_anki(self, args):
        import os
        import re

        mpv = MPV(start_mpv=False, ipc_socket=args[0])
        mp3_full_file_path = args[1]
        start_timestamp = args[2]
        stop_timestamp = args[3]
        duration = int(args[4])/1000.0
        screenshot_full_file_path = args[5]
        subtitle = args[6]
        path = mpv.command(*args[7:])
        translation = self.deeplx_translate(subtitle)
        if path.startswith("http"):
            raw_source_url = os.popen("yt-dlp '{}' --print urls".format(path)).readlines()
            if "bili" in path:
                rep = {"?": r"\?", "&": r"\&", ",": r"\,"}

                # @See: https://stackoverflow.com/questions/6116978/how-to-replace-multiple-substrings-of-a-string
                rep = dict((re.escape(k), v) for k, v in rep.items())
                pattern = re.compile("|".join(rep.keys()))
                source_url = list(map(lambda text: pattern.sub(lambda m: rep[re.escape(m.group(0))], text.strip()), raw_source_url))
            elif "youtube" in path:
                source_url = list(map(lambda text: text.strip(), raw_source_url))
                final_cmd = f'ffmpeg -ss {start_timestamp} -to {stop_timestamp} -i "{source_url[1]}" -map_metadata -1 -ac 1 -codec:a libmp3lame -vbr on -compression_level 10 -application voip -b:a 24k "{mp3_full_file_path}" && ffmpeg -ss {stop_timestamp} -i "{source_url[0]}" -map_metadata -1 -vcodec mjpeg -lossless 0 -compression_level 6 -qscale:v 15 -vf scale=-2:200 -vframes 1 "{screenshot_full_file_path}"'
                eval_in_emacs("hurricane/subed--send-sentence-to-Anki", final_cmd, mp3_full_file_path, subtitle, translation, screenshot_full_file_path)
        else:
            file_name, file_extension = os.path.splitext(path)
            if file_extension == "mp3":
                final_cmd = f'ffmpeg -i "{path}" -ss {start_timestamp} -to {stop_timestamp} -c:a copy {full_file_path}'
                eval_in_emacs("hurricane/subed--send-sentence-to-Anki", final_cmd, mp3_full_file_path, subtitle, translation, screenshot_full_file_path)
            else:
                final_cmd = f'ffmpeg -ss {start_timestamp} -to {stop_timestamp} -i "{path}" -map_metadata -1 -map 0:1 -ac 1 -codec:a libmp3lame -vbr on -compression_level 10 -application voip -b:a 24k "{mp3_full_file_path}" && ffmpeg -ss {stop_timestamp} -i "{path}" -map_metadata -1 -vcodec mjpeg -lossless 0 -compression_level 6 -qscale:v 15 -vf scale=-2:200 -vframes 1 "{screenshot_full_file_path}"'
                eval_in_emacs("hurricane/subed--send-sentence-to-Anki", final_cmd, mp3_full_file_path, subtitle, translation, screenshot_full_file_path)

    def mpv_ontop(self, args):
        mpv = MPV(start_mpv=False, ipc_socket=args[0])
        mpv.command(*args[1:])

    def mpv_cut_video(self, args):
        import os
        import re

        mpv = MPV(start_mpv=False, ipc_socket=args[0])
        full_file_path = args[1]
        start_timestamp = args[2] if args[2] else mpv.command("get_property", "time-pos")
        duration = int(args[4])/1000.0
        stop_timestamp = args[3] if args[3] else start_timestamp + duration
        path = mpv.command(*args[5:])
        if path.startswith("http"):
            raw_source_url = os.popen("yt-dlp '{}' --print urls".format(path)).readlines()
            if "bili" in path:
                rep = {"?": r"\?", "&": r"\&", ",": r"\,"}

                # @See: https://stackoverflow.com/questions/6116978/how-to-replace-multiple-substrings-of-a-string
                rep = dict((re.escape(k), v) for k, v in rep.items())
                pattern = re.compile("|".join(rep.keys()))
                source_url = list(map(lambda text: pattern.sub(lambda m: rep[re.escape(m.group(0))], text.strip()), raw_source_url))
                bili_final_cmd = f'ffmpeg -user_agent "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.114 Safari/537.36 Edg/89.0.774.76 " -i {source_url[0]} -i {source_url[1]} -ss {start_timestamp} -t {duration} -y "{full_file_path}"'
                eval_in_emacs("hurricane/reveal--cut-media", bili_final_cmd, full_file_path)
            elif "youtube" in path:
                source_url = list(map(lambda text: text.strip(), raw_source_url))
                youtube_final_cmd = f'ffmpeg -ss {start_timestamp} -i "{source_url[0]}" -ss {start_timestamp} -i "{source_url[1]}" -ss 5 -map 0:v -map 1:a -c:v libx264 -c:a aac -t {duration} -y "{full_file_path}"'
                eval_in_emacs("hurricane/reveal--cut-media", youtube_final_cmd, full_file_path)
        else:
            file_final_cmd = f'ffmpeg -ss {start_timestamp} -t {duration} -i "{path}" -filter:v scale=1280:720 -c:v h264 -b:v 6m -c:a copy -strict -2 -y "{full_file_path}"'
            eval_in_emacs("hurricane/reveal--cut-media", file_final_cmd, full_file_path)

    def deeplx(self, sentence):
        translation = self.deeplx_translate(sentence)
        eval_in_emacs("hurricane//popweb-translation-show", sentence, translation)

    def reveal_comment_block_translate(self, args):
        translation = self.deeplx_translate(args[0])
        eval_in_emacs("hurricane//reveal--comment-block-translate", translation, args[1])

    def mpv_get_time_position(self, args):
        mpv = MPV(start_mpv=False, ipc_socket=args[0])
        point = args[1]
        start_or_stop = args[2]
        time_position = mpv.command(*args[3:])
        eval_in_emacs("hurricane//slide--material-video-timestamp", str(point), start_or_stop, str(time_position))

    def insert_pdf_toc(self, args):
        input_file = args[0]
        payload = args[1]
        self.doc = fitz.open(input_file)
        self.doc.set_toc(payload)
        self.doc.saveIncr()
        self.doc.close()


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        import cProfile
        profiler = cProfile.Profile()
        profiler.run("MindWave(sys.argv[1:])")
    else:
        MindWave(sys.argv[1:])
