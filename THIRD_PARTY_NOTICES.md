# Third-party notices

## Omarchy

`omarchy-plugin/SettingsDropdown.qml` adapts Omarchy's `shell/Ui/Dropdown.qml`.
Source: https://github.com/omacom/omarchy/tree/quattro/shell/Ui
The adaptations change popup dismissal and preserve the selected-value binding.
Omarchy components imported at runtime are supplied by the user's installation.

Copyright (c) David Heinemeier Hansson

Permission is hereby granted, free of charge, to any person obtaining
 a copy of this software and associated documentation files (the
 "Software"), to deal in the Software without restriction, including
 without limitation the rights to use, copy, modify, merge, publish,
 distribute, sublicense, and/or sell copies of the Software, and to
 permit persons to whom the Software is furnished to do so, subject to
 the following conditions:

The above copyright notice and this permission notice shall be
 included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
 NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
 BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
 ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 SOFTWARE.

License source: https://github.com/omacom/omarchy/blob/quattro/LICENSE

## Optional speech model

Model weights are not included in this repository. The explicitly requested
recommended download is Ivan Stupakov's ONNX conversion of NVIDIA's
Parakeet TDT 0.6B v3. The application does not modify the downloaded weights.

- ONNX model and attribution: https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx
- Original model: https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3
- Download revision: `8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce`
- Model license: Creative Commons Attribution 4.0 International,
  https://creativecommons.org/licenses/by/4.0/

The model has a separate license from the application. Model origin, revision
and license are also recorded in `SOURCE.json` alongside an application download.

## Python dependencies

Dependencies are installed separately using `requirements.lock`, not vendored.
Their license notices remain in the installed Python distributions:
onnx-asr (MIT), ONNX Runtime (MIT), NumPy (BSD-3-Clause with bundled components under additional licenses), FlatBuffers
(Apache-2.0), packaging (Apache-2.0 or BSD-2-Clause), protobuf (BSD-3-Clause).
Consult each installed distribution's license for its complete terms and notices.
