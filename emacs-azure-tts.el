;;; emacs-azure-tts.el --- TTS -*- lexical-binding: t -*-
;;
;; Author: c <c@MacBook-Pro.local>
;; Copyright © 2023, c, all rights reserved.
;; Created: 10 March 2023
;;
;;; Commentary:
;;
;;
;;
;;; Code:

(require 'python-bridge)

(defcustom emacs-azure-tts-eww-sentence-abbrevs '("i.e." "etc." "U.S.")
  "Prevent to incorrectly determine sentence end."
  :type '(repeat string)
  :group 'emacs-azure-tts)

(defcustom emacs-azure-tts-eww-sentence-ends (rx (or
                                            (and "." (or " " eol))
                                            (and "?" (or " " eol))
                                            (and "!" (or " " eol))
                                            (and ";" (or " " eol))
                                            "\n\n"))
  "A regexp used to determine where is the end of a sentence in eww."
  :type 'string
  :group 'emacs-azure-tts)

(defcustom emacs-azure-tts-audio-dir ""
  "Directory to store azure tts audio file."
  :type 'string
  :group 'emacs-azure-tts)

(defvar emacs-azure-tts-SSML-file (expand-file-name "SSML.xml" (if load-file-name
                                                             (file-name-directory load-file-name)
                                                           default-directory)))
(defvar emacs-azure-tts-after-speak-functions
  '()
  "Define a list of functions used to process audio file and sentence.
These functions take two arguments: Audio file and Sentence.")

(defun emacs-azure-tts--string-ends-with-any (str patterns)
  (cl-dolist (p patterns)
    (when (string-suffix-p p str t)
      (cl-return t))))

(defun emacs-azure-tts--eww-sentence ()
  (let ((sentence-ends emacs-azure-tts-eww-sentence-ends)
        (point (point))
        (stop nil)
        start end)
    (save-excursion
      (while (not stop)
        (setq end (search-forward-regexp sentence-ends nil t))
        ;; (message "end: %s" end)
        (if (not end)
            (setq end (point-max)
                  stop t)
          (unless (emacs-azure-tts--string-ends-with-any (buffer-substring-no-properties point (- end 1)) emacs-azure-tts-eww-sentence-abbrevs)
            (setq stop t))))

      (setq stop nil)
      (goto-char point)
      (while (not stop)
        (setq start (search-backward-regexp sentence-ends nil t))
        ;; (message "start: %s" start)
        (if (not start)
            (setq start (point-min)
                  stop t)
          (unless (emacs-azure-tts--string-ends-with-any (buffer-substring-no-properties (point-at-bol) (1+ start)) emacs-azure-tts-eww-sentence-abbrevs)
            (setq stop t)
            (setq start (1+ start))))))
    (string-trim (buffer-substring-no-properties start end))))

(defun emacs-azure-tts--sentence ()
  (let (sentence)
    (cond
     ((derived-mode-p 'eww-mode)
      (setq sentence (emacs-azure-tts--eww-sentence)))
     (t
      (setq sentence (thing-at-point 'sentence t))))
    sentence))

(defun emacs-azure-tts-region-or-sentence ()
  "Return region or sentence around point.
If `mark-active' on, return region string.
Otherwise return sentence around point."
  (if mark-active
      (buffer-substring-no-properties (region-beginning)
                                      (region-end))
    (emacs-azure-tts--sentence)))

(defun emacs-azure-tts-after-speak (audio-file sentence translation)
  (run-hook-with-args-until-success
   'emacs-azure-tts-after-speak-functions audio-file sentence translation))

(defun emacs-azure-tts-start ()
  (when (python-bridge-epc-live-p python-bridge-epc-process)
    (python-bridge-call-async "tts" emacs-azure-tts-start-sentence)))

;;;###autoload
(defun emacs-azure-tts (&optional start-sentence arg)
  "Start emacs-azure-tts."

  (interactive (list (read-string (format "[emacs-azure-tts] To speak(%s): " (or (emacs-azure-tts-region-or-sentence) ""))
                                  (emacs-azure-tts-region-or-sentence)) "P"))

  (while (string-equal start-sentence "")
    (setq start-sentence (read-string "Please input the sentence to speak: "
                           nil nil "" nil)))

  (setq emacs-azure-tts-start-sentence (replace-regexp-in-string "[\t\n\r]+" " " start-sentence))

  (emacs-azure-tts-start)

  (unless python-bridge-is-starting
    (python-bridge-start-process)))

(provide 'emacs-azure-tts)

;;; emacs-azure-tts.el ends here
