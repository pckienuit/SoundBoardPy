import sounddevice as sd
import soundfile as sf
import threading
import numpy as np


class AudioEngine:
    """
    Manages audio playback using sounddevice and soundfile.
    Supports multiple simultaneous sounds, pausing, real-time volume envelope
    (fade-in / fade-out), crossfade, custom output devices, real-time RMS
    metering, and audio passthrough.
    """

    def __init__(self):
        self.output_device_id = None

        # stream_id -> [stream, event, is_paused, playback_state]
        # playback_state is a dict with keys:
        #   data            : numpy array (audio samples)
        #   fs              : sample rate (int)
        #   total_frames    : total frame count (int)
        #   current_frame   : current playback position (int, shared via lock)
        #   base_multiplier : static volume multiplier from volume_offset
        #   current_volume  : animated volume 0.0-1.0
        #   target_volume   : destination volume
        #   fade_in_samples  : total samples for fade-in (0 = no fade-in)
        #   fade_out_samples : total samples for fade-out (0 = no fade-out)
        #   fade_step       : volume change per frame during fade
        #   fade_frames_done: frames processed in current fade operation
        #   is_fading_out   : bool – fade-out has been triggered
        #   loop            : bool
        self.active_streams = {}
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

    def play(self, file_path, loop=False, volume_offset=0,
             fade_in_ms=0, fade_out_ms=0):
        """
        Play an audio file with optional fade-in.

        Args:
            file_path: Path to audio file.
            loop: Whether to loop playback.
            volume_offset: Volume offset in -10..+10 steps.
            fade_in_ms: Fade-in duration in milliseconds (0 = instant).
            fade_out_ms: Fade-out duration in milliseconds (0 = instant).

        Returns:
            A unique stream_id (int), or None on error.
        """
        try:
            data, fs = sf.read(file_path, always_2d=True)
            total_frames = len(data)

            base_multiplier = max(0.0, 1.0 + volume_offset * 0.1)

            # Calculate fade-in state
            fade_in_samples = int(fade_in_ms * fs / 1000)
            fade_out_samples = int(fade_out_ms * fs / 1000)

            # Start at 0 volume if fade-in is requested, otherwise full volume
            current_volume = 0.0 if fade_in_samples > 0 else 1.0
            target_volume = 1.0

            # Fade step: reach target_volume in fade_in_samples frames
            if fade_in_samples > 0:
                fade_step = 1.0 / fade_in_samples
            else:
                fade_step = 0.0

            with self.lock:
                self.stream_counter += 1
                stream_id = self.stream_counter

            event = threading.Event()
            current_frame = 0
            is_paused = False
            fade_frames_done = 0
            is_fading_out = False

            playback_state = {
                "data": data,
                "fs": fs,
                "total_frames": total_frames,
                "current_frame_ref": [0],      # list so callback can modify
                "base_multiplier": base_multiplier,
                "current_volume_ref": [current_volume],
                "target_volume_ref": [target_volume],
                "fade_in_samples": fade_in_samples,
                "fade_out_samples": fade_out_samples,
                "fade_step": fade_step,
                "fade_frames_done_ref": [0],
                "is_fading_out_ref": [False],
                "loop": loop,
            }

            def callback(outdata, frames, time, status):
                nonlocal current_frame, _master_rms

                if status:
                    print(status)

                # ── Pause path ──────────────────────────────────────────────────
                with ae_lock:
                    if stream_id in active_streams and active_streams[stream_id][2]:
                        outdata.fill(0)
                        return

                # ── Read mutable state from refs ───────────────────────────────
                state = active_streams[stream_id][3]
                cur_vol = state["current_volume_ref"][0]
                target_vol = state["target_volume_ref"][0]
                fade_step = state["fade_step"]
                fade_in_samples = state["fade_in_samples"]
                fade_out_samples = state["fade_out_samples"]
                fade_done = state["fade_frames_done_ref"][0]
                is_fading_out = state["is_fading_out_ref"][0]

                # ── Advance frame position ─────────────────────────────────────
                chunksize = min(len(data) - current_frame, frames)
                chunk = data[current_frame:current_frame + chunksize]

                # ── Apply volume envelope ──────────────────────────────────────
                effective_vol = cur_vol * base_multiplier
                outdata[:chunksize] = chunk * effective_vol

                # ── Fade envelope update ───────────────────────────────────────
                if chunksize > 0:
                    new_cur_vol = cur_vol

                    # Fade-in phase
                    if fade_in_samples > 0 and not is_fading_out:
                        frames_increment = chunksize
                        fade_done += frames_increment
                        fade_ratio = min(fade_done / fade_in_samples, 1.0)
                        new_cur_vol = fade_ratio
                        if fade_done >= fade_in_samples:
                            new_cur_vol = 1.0
                            # Lock out fade-in from now on
                            state["fade_in_samples"] = 0

                    # Fade-out phase
                    if is_fading_out and fade_out_samples > 0:
                        frames_increment = chunksize
                        fade_ratio = max(0.0, 1.0 - fade_done / fade_out_samples)
                        new_cur_vol = fade_ratio
                        fade_done += frames_increment
                        if fade_done >= fade_out_samples:
                            new_cur_vol = 0.0
                            state["fade_out_samples"] = 0

                    state["current_volume_ref"][0] = new_cur_vol
                    state["fade_frames_done_ref"][0] = fade_done

                # ── Advance / loop / end ───────────────────────────────────────
                if chunksize < frames:
                    if loop:
                        rest = frames - chunksize
                        rest = min(rest, len(data))
                        outdata[chunksize:chunksize + rest] = data[:rest] * effective_vol
                        outdata[chunksize + rest:] = 0
                        current_frame = rest
                    else:
                        outdata[chunksize:] = 0
                        # Signal done from inside callback
                        try:
                            raise sd.CallbackStop()
                        except Exception:
                            pass
                else:
                    current_frame += chunksize

                # Update current_frame in shared state for position queries
                state["current_frame_ref"][0] = current_frame

                # ── Master RMS update ──────────────────────────────────────────
                rms = float(np.sqrt(np.mean(outdata[:chunksize] ** 2)))
                with _rms_lock:
                    _master_rms = max(_master_rms * 0.85, rms)

            # Aliases for closures
            ae_lock = self.lock
            active_streams = self.active_streams
            _rms_lock = self._rms_lock
            _master_rms = self._master_rms

            device = self.output_device_id if self.output_device_id is not None \
                else sd.default.device[1]

            stream = sd.OutputStream(
                samplerate=fs, device=device, channels=data.shape[1],
                callback=callback, finished_callback=event.set
            )

            with self.lock:
                self.active_streams[stream_id] = [stream, event, False, playback_state]

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
            if stream_id not in self.active_streams:
                return
            _, event, _, state = self.active_streams[stream_id]
            fade_out_samples = state["fade_out_samples"]
            if fade_out_samples > 0:
                # Trigger fade-out instead of immediate stop
                state["is_fading_out_ref"][0] = True
                state["fade_frames_done_ref"][0] = 0
                state["target_volume_ref"][0] = 0.0
            else:
                # Hard stop
                try:
                    self.active_streams[stream_id][0].stop()
                    self.active_streams[stream_id][0].close()
                except Exception:
                    pass
                if stream_id in self.active_streams:
                    del self.active_streams[stream_id]

    def stop_all(self):
        with self.lock:
            for stream_id, (stream, event, _, state) in list(self.active_streams.items()):
                fade_out_samples = state["fade_out_samples"]
                if fade_out_samples > 0:
                    state["is_fading_out_ref"][0] = True
                    state["fade_frames_done_ref"][0] = 0
                    state["target_volume_ref"][0] = 0.0
                else:
                    try:
                        stream.stop()
                        stream.close()
                    except Exception:
                        pass
                    if stream_id in self.active_streams:
                        del self.active_streams[stream_id]

    # ------------------------------------------------------------------
    # Fade control
    # ------------------------------------------------------------------

    def fade_in(self, stream_id, duration_ms=500):
        """
        Trigger a fade-in on a playing (or paused) stream.
        Volume ramps from current level to 1.0 over duration_ms.
        """
        with self.lock:
            if stream_id not in self.active_streams:
                return
            _, _, _, state = self.active_streams[stream_id]
            fs = state["fs"]
            fade_samples = int(duration_ms * fs / 1000)
            if fade_samples <= 0:
                state["current_volume_ref"][0] = 1.0
                state["fade_in_samples"] = 0
                return
            # Reset fade-in from current volume to 1.0
            state["fade_in_samples"] = fade_samples
            state["fade_frames_done_ref"][0] = 0
            state["is_fading_out_ref"][0] = False
            state["target_volume_ref"][0] = 1.0
            state["fade_step"] = 1.0 / fade_samples

    def fade_out(self, stream_id, duration_ms=None):
        """
        Trigger a fade-out on a stream.
        If duration_ms is None, uses the stream's configured fade_out_samples.
        """
        with self.lock:
            if stream_id not in self.active_streams:
                return
            _, _, _, state = self.active_streams[stream_id]
            if duration_ms is None:
                duration_ms = int(state["fade_out_samples"] / state["fs"] * 1000)
            fs = state["fs"]
            fade_samples = int(duration_ms * fs / 1000)
            if fade_samples <= 0:
                state["current_volume_ref"][0] = 0.0
                state["is_fading_out_ref"][0] = True
                state["fade_out_samples"] = 0
                return
            state["is_fading_out_ref"][0] = True
            state["fade_frames_done_ref"][0] = 0
            state["fade_out_samples"] = fade_samples
            state["target_volume_ref"][0] = 0.0

    def crossfade(self, old_stream_id, new_stream_id, crossfade_ms=300):
        """
        Simultaneous crossfade: fade out old_stream_id while fade_in new_stream_id.
        """
        self.fade_out(old_stream_id, duration_ms=crossfade_ms)
        with self.lock:
            if new_stream_id in self.active_streams:
                _, _, _, state = self.active_streams[new_stream_id]
                fs = state["fs"]
                fade_samples = int(crossfade_ms * fs / 1000)
                state["current_volume_ref"][0] = 0.0
                state["fade_in_samples"] = fade_samples
                state["fade_frames_done_ref"][0] = 0
                state["is_fading_out_ref"][0] = False
                state["target_volume_ref"][0] = 1.0
                state["fade_step"] = 1.0 / fade_samples if fade_samples > 0 else 0.0

    def set_fade_params(self, stream_id, fade_in_ms, fade_out_ms):
        """Update fade-in and fade-out sample counts on a stream."""
        with self.lock:
            if stream_id not in self.active_streams:
                return
            _, _, _, state = self.active_streams[stream_id]
            fs = state["fs"]
            state["fade_in_samples"] = int(fade_in_ms * fs / 1000)
            state["fade_out_samples"] = int(fade_out_ms * fs / 1000)

    # ------------------------------------------------------------------
    # Position & stream info
    # ------------------------------------------------------------------

    def get_position(self, stream_id):
        """Return (current_frame, total_frames) for a stream."""
        with self.lock:
            if stream_id not in self.active_streams:
                return (0, 0)
            state = self.active_streams[stream_id][3]
            return (state["current_frame_ref"][0], state["total_frames"])

    def get_playing_streams(self):
        """
        Return lightweight list of active stream info for the timeline panel.
        Each dict has: stream_id, current_frame, total_frames, volume, is_paused.
        """
        with self.lock:
            result = []
            for stream_id, (stream, event, is_paused, state) in self.active_streams.items():
                result.append({
                    "stream_id": stream_id,
                    "current_frame": state["current_frame_ref"][0],
                    "total_frames": state["total_frames"],
                    "volume": state["current_volume_ref"][0],
                    "is_paused": is_paused,
                    "is_fading_out": state["is_fading_out_ref"][0],
                })
            return result

    def get_stream_rms(self, stream_id):
        """Return RMS level for a specific stream (0.0-1.0)."""
        with self.lock:
            if stream_id not in self.active_streams:
                return 0.0
            state = self.active_streams[stream_id][3]
            data = state["data"]
            frame = state["current_frame_ref"][0]
            # Use a small window of recent samples
            start = max(0, frame - 1024)
            chunk = data[start:frame]
            if len(chunk) == 0:
                return 0.0
            return float(np.sqrt(np.mean(chunk ** 2)))

    def is_stream_active(self, stream_id):
        """Return True if the stream is still in active_streams."""
        with self.lock:
            return stream_id in self.active_streams

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
