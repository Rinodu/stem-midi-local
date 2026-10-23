# Model and dependency notices

No checkpoint is redistributed in this repository. Dependency/model authors retain their copyrights. The project's own source is MIT licensed; third-party licenses continue to apply separately.

## Demucs 4.0.1

- Source and license: https://github.com/facebookresearch/demucs and https://github.com/facebookresearch/demucs/blob/main/LICENSE (MIT).
- Official model registry: https://github.com/facebookresearch/demucs/tree/main/demucs/remote . Checkpoints are retrieved by upstream `demucs.pretrained`, not from arbitrary user URLs.
- The original repository is archived; pinning versions avoids silently changing the runtime contract. Upstream explicitly warns that the 6-source piano output has substantial bleeding/artifacts. 4-source fine-tuned mode does not yield separate piano/guitar.
- The MIT repository license and upstream checkpoint availability are recorded here; a separate, explicit checkpoint-only commercial license grant has not been established in this project's review. Do not read this notice as a guarantee about all training-data or commercial-use rights. This personal/local app does not rehost checkpoints.

## Transkun 2.0.1

- Source: https://github.com/Yujia-Yan/Transkun . License: https://github.com/Yujia-Yan/Transkun/blob/main/LICENSE (MIT).
- The package ships `transkun/pretrained/2.0.pt` and `2.0.conf` as declared in upstream setup.py. The application uses that matched pair without substituting weights from another architecture.
- Research: Yujia Yan, Frank Cwitkowitz, Zhiyao Duan, Skipping the Frame-Level: Event-Based Piano Transcription With Neural Semi-CRFs; see upstream README for the current model/paper references.

## Basic Pitch 0.4.0

- Source: https://github.com/spotify/basic-pitch . License: https://github.com/spotify/basic-pitch/blob/main/LICENSE (Apache-2.0).
- Uses the packaged ICASSP 2022 model. On Windows/Python 3.10, the upstream package selects ONNX Runtime instead of TensorFlow. No retraining, account or paid inference endpoint required.
- Research: Rachel M. Bittner et al., A Lightweight Instrument-Agnostic Model for Polyphonic Note Transcription and Multipitch Estimation, ICASSP 2022; see upstream repository.

## Runtime

PyTorch, Torchaudio, ONNX Runtime, FFmpeg (through imageio-ffmpeg), NumPy, SoundFile, FastAPI and remaining packages carry their own license notices within their distributions. Installing these downloads third-party software/binaries. For redistribution of a bundled runtime, collect those licenses and review FFmpeg build terms separately; this repo distributes source/installation instructions only.
