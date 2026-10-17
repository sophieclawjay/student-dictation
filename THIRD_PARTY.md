# Third-party software and models

Student Dictation's own source code uses the MIT license in `LICENSE`. Bundled
dependencies and downloaded models keep their own licenses. This file is a
navigation guide; the license texts shipped with each installed version control.

| Component | License / primary source |
| --- | --- |
| PySide6 and Qt | [LGPL 3.0 / GPL options](https://doc.qt.io/qtforpython-6/licenses.html) |
| faster-whisper | [MIT](https://github.com/SYSTRAN/faster-whisper/blob/master/LICENSE) |
| CTranslate2 | [MIT](https://github.com/OpenNMT/CTranslate2/blob/master/LICENSE) |
| OpenAI Whisper code and original weights | [MIT](https://github.com/openai/whisper/blob/main/LICENSE) |
| PortAudio, used by sounddevice | [MIT](https://www.portaudio.com/license.html) |
| sounddevice | [MIT](https://github.com/spatialaudio/python-sounddevice/blob/master/LICENSE) |
| NumPy | [BSD 3-Clause](https://github.com/numpy/numpy/blob/main/LICENSE.txt) |
| PyAV | [BSD 3-Clause](https://github.com/PyAV-Org/PyAV/blob/main/LICENSE.txt) |
| FFmpeg libraries distributed with PyAV wheels | See the exact wheel's license files and [PyAV build documentation](https://pyav.org/docs/stable/overview/installation.html) |
| Hugging Face Hub client | [Apache 2.0](https://github.com/huggingface/huggingface_hub/blob/main/LICENSE) |
| Tokenizers | [Apache 2.0](https://github.com/huggingface/tokenizers/blob/main/LICENSE) |
| ONNX Runtime | [MIT](https://github.com/microsoft/onnxruntime/blob/main/LICENSE) |
| pynput | [LGPL 3.0](https://github.com/moses-palmer/pynput/blob/master/COPYING.LGPL) |
| PyInstaller bootloader | [GPL with distribution exception](https://pyinstaller.org/en/stable/license.html) |

The application downloads CTranslate2 conversions from these model repositories:

- [mobiuslabsgmbh/faster-whisper-large-v3-turbo](https://huggingface.co/mobiuslabsgmbh/faster-whisper-large-v3-turbo)
- [Systran/faster-whisper-large-v3](https://huggingface.co/Systran/faster-whisper-large-v3)
- [Systran/faster-whisper-small](https://huggingface.co/Systran/faster-whisper-small)
- [Systran/faster-whisper-base](https://huggingface.co/Systran/faster-whisper-base)

These conversions derive from MIT-licensed Whisper models. Model files are
downloaded separately, after consent, and are excluded from application archives.
Review the model repository's current model card and license before redistribution.

`packaging/collect_licenses.py` copies installed dependency license texts into the
bundle's `licenses/third-party` folder. It also records installed package versions.
Keep that directory when redistributing a build. Qt and pynput are loaded as
separate, dynamically linked dependencies in the directory bundle. Preserve the
ability to replace or relink the applicable libraries and the LGPL notices. Source
distributions, corresponding dependency source, and LGPL relinking obligations
still need to be satisfied for the exact binary you distribute. PyAV wheels may
include FFmpeg builds with additional license obligations; retain their notices
and review those exact artifacts before a public binary release.

The unsigned CI archives are development artifacts. A distributor should review
the included dependency inventory, licenses, signing, and platform behavior before
offering an installer to students.
