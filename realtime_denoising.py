import time
import wave
import asyncio
import argparse
import websockets
from io import BytesIO
from typing import AsyncIterator, cast

def get_url(input_freq: int, output_freq: int, bytes_per_sample: int) -> str:
    '''
    The websocket API format is as follows:
    wss://<url>/denoise/<input_format>/<output_format>/<api_key>/<bytes_per_sample>/<input_sampling_frequency>/<output_sampling_frequency>
    Note here that the API is set to take in and return bytes in PCM format, i.e. the wav header
    should be parsed.
    '''
    return f"wss://demo.ncompass.tech:12347/denoise/pcm/pcm/2b6d62df-4b0a-4812-a199-9696be164608/{bytes_per_sample}/{input_freq}/{output_freq}"

def get_bytes_per_chunk(chunk_size_ms: int, frame_rate: int, bytes_per_frame: int) -> int:
    ''' 
    Given the size of a chunk in ms, number of bytes per frame in the pcm ecnoding and the
    frame rate (sampling frequency) this calculates the number of bytes in the chunk. 
    '''
    return int(bytes_per_frame * ((chunk_size_ms / 1000) * frame_rate))

async def chunk_audio(audio_frames: bytes
                      , chunk_size_ms: int
                      , in_frame_rate: int
                      , bytes_per_sample: int) -> AsyncIterator[bytes] : 
    ''' 
    This function takes the input audio file read in as bytes and chunks it into chunks based on
    the chunk size specified. The chunks are yielded followed by a async sleep to yield back
    control to the running thread from an infinite while loop. 
    '''
    bytes_per_chunk = get_bytes_per_chunk(chunk_size_ms, in_frame_rate, bytes_per_sample)
    chunk_start = 0
    while True:
        if chunk_start >= len(audio_frames): break
        end = chunk_start + bytes_per_chunk
        chunk_end = end if end < len(audio_frames) else len(audio_frames)
        chunk = audio_frames[chunk_start:chunk_end]
        chunk_start = chunk_end
        yield chunk
        await asyncio.sleep(0)

async def denoise_in_realtime(wav_file: str
                              , out_frame_rate: int
                              , chunk_size_ms: int) -> None:
    '''
    First open the file with the wave library to parse the wav header correctly and convert to a
    PCM format.
    '''
    with wave.open(wav_file, 'rb') as wh:
        bytes_per_sample = wh.getsampwidth()
        in_frame_rate = wh.getframerate()
        audio_frames = wh.readframes(wh.getnframes())
    
        # Connect to the API using websockets
        async with websockets.connect(get_url(in_frame_rate
                                              , out_frame_rate
                                              , bytes_per_sample)) as ws:
                denoised_audio = bytearray(b'')
                num_frames_received = 0
                count = 0
                # Get chunks of audio based on user provided chunk size
                async for chunk in chunk_audio(audio_frames
                                               , chunk_size_ms
                                               , in_frame_rate
                                               , bytes_per_sample):
                    start = time.perf_counter()
                    await ws.send(chunk)
                    res = cast(bytes, await ws.recv())
                    end = time.perf_counter()
                    count += 1
                    print(f'{count} : Processed chunk in {(end-start)*1000:.2f}ms')
                    
                    '''
                    As the return type is set to pcm in the websocket request, we can directly
                    accumulate the bytes into a bytearray.
                    '''
                    denoised_audio += res
        
        # Note: for now the API only supports single input and output channels
        with wave.open('output.wav', 'wb') as out_file: 
            out_file.setnchannels(1)             
            out_file.setsampwidth(bytes_per_sample)
            out_file.setframerate(out_frame_rate)
            if num_frames_received != 0: out_file.setnframes(num_frames_received)
            out_file.writeframes(denoised_audio)

if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser()

    arg_parser.add_argument("--wav_file"
                            , type=str
                            , required=True
                            , help = "File to denoise in .wav format")
    arg_parser.add_argument("--denoised_sampling_freq"
                            , type=int
                            , required=True
                            , help = "Sampling frequency of denoised output")
    arg_parser.add_argument("--chunk_size_ms"
                            , type=int
                            , default=65
                            , help = "Chunk size in ms to send audio")

    args = arg_parser.parse_args()
    asyncio.run(denoise_in_realtime(args.wav_file
                                    , args.denoised_sampling_freq
                                    , args.chunk_size_ms))
