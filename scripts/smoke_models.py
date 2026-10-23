"""Real inference on a generated fixture. Does not establish accuracy on music."""
import argparse
import json
from pathlib import Path
import sys
import time

import numpy as np
import pretty_midi
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import pipeline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    parser.add_argument('--output', type=Path, default=ROOT / '.local' / 'smoke')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    sr = 44100
    audio = np.zeros(sr * 6, dtype=np.float32)
    expected = [60, 64, 67, 72]
    for i, pitch in enumerate(expected):
        t = np.arange(int(sr * .8)) / sr
        frequency = 440 * 2 ** ((pitch - 69) / 12)
        envelope = np.minimum(t / .01, 1) * np.exp(-t * 2)
        tone = sum(np.sin(2 * np.pi * frequency * harmonic * t) / harmonic for harmonic in range(1, 5))
        begin = int((.5 + i * 1.2) * sr)
        audio[begin:begin + len(t)] += (tone * envelope * .2).astype(np.float32)
    sample = args.output / 'sample.wav'
    sf.write(sample, audio, sr, subtype='PCM_16')
    start = time.monotonic()
    pipeline.decode(sample, args.output, 0, 6)
    stems = pipeline.separate(args.output, 'six', args.device, 'balanced')
    assert set(stems) == {'drums','bass','other','vocals','guitar','piano'}, stems
    for name in stems:
        info = sf.info(args.output / stems[name])
        assert abs(info.duration - 6) < .05
    report = {'fixture':'6-second synthetic harmonic melody, not a piano recording',
              'device':args.device, 'expected_pitches':expected, 'stems':list(stems), 'transcription':{}}
    # Test both engines on the known clean input, and the complete stem->MIDI path.
    for name, source, engine in [('clean_basic', 'input.wav', 'basic-pitch'),
                                  ('clean_piano', 'input.wav', 'transkun'),
                                  ('piano', stems['piano'], 'transkun')]:
        if name != 'piano':
            pipeline.PITCHED[name] = 0
        result = pipeline.transcribe(args.output, name, source, engine, args.device, .5, 100)
        midi = pretty_midi.PrettyMIDI(str(args.output / result['file']))
        notes = [n for instrument in midi.instruments for n in instrument.notes]
        assert all(n.end > n.start >= 0 and 0 <= n.pitch <= 127 for n in notes)
        if name == 'clean_basic':
            assert len(notes) > 0, 'Basic Pitch produced no notes for the harmonic fixture'
        report['transcription'][name] = {'engine':engine, 'notes':len(notes), 'pitches':sorted({n.pitch for n in notes})}
    report['elapsed_seconds'] = round(time.monotonic() - start, 1)
    (args.output / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
