#!/bin/bash
echo "Downloading Kokoro ONNX model and voices (v1.0)..."
wget -q --show-progress -O kokoro-v1.0.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
wget -q --show-progress -O voices-v1.0.bin https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
echo "Done!"
