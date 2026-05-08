import sounddevice as sd
import soundfile as sf
import threading
import numpy as np

class AudioEngine:
    """
    Manages audio playback using sounddevice and soundfile.
    Supports multiple simultaneous sounds, pausing, volume adjustment, and custom output devices.
    """
    def __init__(self):
        self.output_device_id = None
        self.active_streams = {} # stream_id -> (stream, event, is_paused)
        self.stream_counter = 0
        self.lock = threading.Lock()

    def set_output_device(self, device_id):
        self.output_device_id = device_id

    def get_devices(self):
        return sd.query_devices()

    def play(self, file_path, loop=False, volume_offset=0):
        """
        Plays an audio file. Returns a unique stream_id.
        """
        try:
            data, fs = sf.read(file_path, always_2d=True)
            
            # Apply basic volume offset (simplistic: scale data)
            # if volume_offset > 0, increase volume, if < 0 decrease.
            # 0 is normal (1.0). Let's say each step is 10%.
            multiplier = 1.0 + (volume_offset * 0.1)
            if multiplier < 0:
                multiplier = 0.0
            data = data * multiplier

            with self.lock:
                self.stream_counter += 1
                stream_id = self.stream_counter

            event = threading.Event()
            current_frame = 0

            def callback(outdata, frames, time, status):
                nonlocal current_frame
                if status:
                    print(status)
                
                # Check if paused
                with self.lock:
                    if stream_id in self.active_streams and self.active_streams[stream_id][2]:
                        outdata.fill(0)
                        return

                chunksize = min(len(data) - current_frame, frames)
                outdata[:chunksize] = data[current_frame:current_frame + chunksize]
                
                if chunksize < frames:
                    if loop:
                        current_frame = 0 # loop back
                        # Fill the rest
                        rest = frames - chunksize
                        outdata[chunksize:] = data[:rest]
                        current_frame = rest
                    else:
                        outdata[chunksize:] = 0
                        raise sd.CallbackStop()
                else:
                    current_frame += chunksize

            device = self.output_device_id if self.output_device_id is not None else sd.default.device[1]
            
            stream = sd.OutputStream(
                samplerate=fs, device=device, channels=data.shape[1],
                callback=callback, finished_callback=event.set
            )

            with self.lock:
                self.active_streams[stream_id] = [stream, event, False]

            stream.start()
            
            # Auto-cleanup thread
            def cleanup():
                event.wait()
                with self.lock:
                    if stream_id in self.active_streams:
                        del self.active_streams[stream_id]

            threading.Thread(target=cleanup, daemon=True).start()
            
            return stream_id
        except Exception as e:
            print(f"Error playing sound: {e}")
            return None

    def pause(self, stream_id):
        with self.lock:
            if stream_id in self.active_streams:
                self.active_streams[stream_id][2] = True

    def resume(self, stream_id):
        with self.lock:
            if stream_id in self.active_streams:
                self.active_streams[stream_id][2] = False

    def stop(self, stream_id):
        with self.lock:
            if stream_id in self.active_streams:
                stream, event, _ = self.active_streams[stream_id]
                stream.stop()
                stream.close()
                del self.active_streams[stream_id]

    def stop_all(self):
        with self.lock:
            for stream_id, (stream, event, is_paused) in list(self.active_streams.items()):
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
            self.active_streams.clear()

# Global singleton instance
audio_engine = AudioEngine()
