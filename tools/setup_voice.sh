#!/bin/sh
# VOICEVOX（青山龍星）を使えるようにする。動画を作る前に1回実行する。
set -e
V=/home/claude/voicevox
mkdir -p $V && cd $V
pip install -q --break-system-packages pyopenjtalk
[ -f voicevox_core-0.17.1-cp310-abi3-manylinux_2_34_x86_64.whl ] || curl -sL -o voicevox_core-0.17.1-cp310-abi3-manylinux_2_34_x86_64.whl \
  https://github.com/VOICEVOX/voicevox_core/releases/download/0.17.1/voicevox_core-0.17.1-cp310-abi3-manylinux_2_34_x86_64.whl
pip install -q --break-system-packages voicevox_core-0.17.1-cp310-abi3-manylinux_2_34_x86_64.whl
[ -d ort ] || { curl -sL https://github.com/VOICEVOX/onnxruntime-builder/releases/download/voicevox_onnxruntime-1.23.2/voicevox_onnxruntime-linux-x64-1.23.2.tgz | tar xz && mv voicevox_onnxruntime-linux-x64-1.23.2 ort; }
[ -f vvm/vvms/15.vvm ] || { git clone -q --depth 1 --filter=blob:none --sparse https://github.com/VOICEVOX/voicevox_vvm vvm && git -C vvm sparse-checkout set --no-cone /vvms/15.vvm; }
python3 -c "import pyopenjtalk; pyopenjtalk.g2p('テスト')"  # 辞書の取得
echo "voice ready"
