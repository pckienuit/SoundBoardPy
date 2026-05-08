import sounddevice as sd
import soundfile as sf
import threading
import numpy as np


class AudioEngine:
    """
    Manages audio playback using sounddevice and soundfile.
    Supports multiple simultaneous sounds, pausing, volume adjustment,
    custom output devices, real-time RMS metering, and audio passthrough.
    """
    def __init__(self):
        self.output_device_id = None
        self.active_streams = {}   # stream_id -> [stream, event, is_paused]
        self.stream_counter = 0
        self.lock = threading.Lock()

        # RMS metering — rolling buffer updated by all active callbacks
        self._master_rms = 0.0
        self._rms_lock = threading.Lock()

        # Passthrough state
        self._passthrough_stream = None

    # ------------------------------------------------------------------
    # Device helpers
    # ------------------------------------------------------------------

    def set_output_device(self, device_id):
        self.output_device_id = device_id

    def get_devices(self):
        return sd.query_devices()

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def play(self, file_path, loop=False, volume_offset=0):
        """Play an audio file. Returns a unique stream_id."""
        try:
            data, fs = sf.read(file_path, always_2d=True)

            multiplier = max(0.0, 1.0 + volume_offset * 0.1)
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

                with self.lock:
                    if stream_id in self.active_streams and self.active_streams[stream_id][2]:
                        outdata.fill(0)
                        return

                chunksize = min(len(data) - current_frame, frames)
                chunk = data[current_frame:current_frame + chunksize]
                outdata[:chunksize] = chunk

                if chunksize < frames:
                    if loop:
                        rest = frames - chunksize
                        outdata[chunksize:] = data[:rest]
                        current_frame = rest
                    else:
                        outdata[chunksize:] = 0
                        raise sd.CallbackStop()
                else:
                    current_frame += chunksize

                # Update master RMS
                rms = float(np.sqrt(np.mean(outdata[:chunksize] ** 2)))
                with self._rms_lock:
                    self._master_rms = max(self._master_rms * 0.85, rms)

            device = self.output_device_id if self.output_device_id is not None \
                else sd.default.device[1]

            stream = sd.OutputStream(
                samplerate=fs, device=device, channels=data.shape[1],
                callback=callback, finished_callback=event.set
            )

            with self.lock:
                self.active_streams[stream_id] = [stream, event, False]

            stream.start()

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
            for stream_id, (stream, event, _) in list(self.active_streams.items()):
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
            self.active_streams.clear()

    # ------------------------------------------------------------------
    # RMS Metering
    # ------------------------------------------------------------------

    def get_master_rms(self) -> float:
        """Return current master RMS level (0.0 – 1.0, approx)."""
        with self._rms_lock:
            rms = self._master_rms
            # Natural decay when no stream updates it
            self._master_rms *= 0.90
        return rms

    # ------------------------------------------------------------------
    # Audio Passthrough
    # ------------------------------------------------------------------

    def start_passthrough(self, input_device_id: int, output_device_id: int,
                          gain: float = 1.0) -> bool:
        """
        Start routing audio from input_device to output_device.
        Returns True on success.
        """
        self.stop_passthrough()
        try:
            in_info = sd.query_devices(input_device_id)
            out_info = sd.query_devices(output_device_id)
            channels = min(in_info["max_input_channels"],
                           out_info["max_output_channels"])
            channels = max(1, channels)

            # Try common sample rates
            sample_rate = None
            for sr in [48000, 44100, 22050, 16000]:
                try:
                    sd.check_input_settings(
                        device=input_device_id, channels=channels, samplerate=sr)
                    sd.check_output_settings(
                        device=output_device_id, channels=channels, samplerate=sr)
                    sample_rate = sr
                    break
                except Exception:
                    continue

            if sample_rate is None:
                print("Passthrough: no compatible sample rate found")
                return False

            _gain = gain

            def passthrough_callback(indata, outdata, frames, time, status):
                if status:
                    print(f"Passthrough status: {status}")
                outdata[:] = indata * _gain

            self._passthrough_stream = sd.Stream(
                samplerate=sample_rate,
                device=(input_device_id, output_device_id),
                channels=channels,
                callback=passthrough_callback,
            )
            self._passthrough_stream.start()
            return True

        except Exception as e:
            print(f"Passthrough error: {e}")
            self._passthrough_stream = None
            return False

    def stop_passthrough(self):
        """Stop any active passthrough stream."""
        if self._passthrough_stream is not None:
            try:
                self._passthrough_stream.stop()
                self._passthrough_stream.close()
            except Exception:
                pass
            self._passthrough_stream = None


# Global singleton instance
audio_engine = AudioEngine()
