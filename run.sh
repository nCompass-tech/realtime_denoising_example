python -m venv venv-cleaner-transcription
source venv-cleaner-transcription/bin/activate

pip install asyncio websockets wave

python realtime_denoising.py --wav_file ./multiple_speakers.wav \
                             --denoised_sampling_freq 8000 \
                             --chunk_size_ms 65
