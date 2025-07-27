import os
import json
import re
import numpy as np
from vosk import Model, KaldiRecognizer
# asyncio is not strictly needed here if transcribe_once is removed

# No need to import client_settings here directly,
# as the VAD settings will be read by the capture_speech loop in PiMCPClient.

class VoskTranscriber:
    def __init__(self, model_path, sample_rate=16000): # No audio_manager needed here
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Vosk model not found at: {model_path}")

        self.sample_rate = sample_rate
        print(f"Loading Vosk model from {model_path}")
        self.model = Model(model_path)
        # Recognizer is created in reset()
        self.reset() # Initial reset
        print("Vosk transcriber initialized (for external VAD loop).")
        
    def reset(self): # Renamed from reset_transcription_state for simplicity
        """Reset the transcriber state for a new utterance."""
        self.complete_text = ""
        self.partial_text = ""
        # Create a new recognizer instance for a clean state
        self.recognizer = KaldiRecognizer(self.model, self.sample_rate)
        self.recognizer.SetWords(True) # Enable word timings if needed by your VAD logic's display
        
    def process_frame(self, frame_data_bytes):
        """
        Process a single audio frame and update transcription.
        This is called by the external VAD loop.

        Args:
            frame_data_bytes: Audio frame as bytes.
            
        Returns:
            Tuple of (is_final_chunk_result, is_speech_in_frame, current_full_text)
            is_final_chunk_result (bool): True if Vosk finalized a segment with this frame.
            is_speech_in_frame (bool): True if Vosk detected speech in this frame (based on partial).
            current_full_text (str): The current best guess of the full utterance so far.
        """
        if self.recognizer.AcceptWaveform(frame_data_bytes):
            result = json.loads(self.recognizer.Result())
            text_chunk = result.get("text", "").strip()
            
            if text_chunk:
                self.complete_text = (self.complete_text + " " + text_chunk).strip() if self.complete_text else text_chunk
                # Even if it's a final chunk, speech was present
                return True, bool(text_chunk), self.complete_text 
            # Vosk finalized a segment, but it was empty (e.g., short silence)
            return True, False, self.complete_text
        else:
            partial_result = json.loads(self.recognizer.PartialResult())
            self.partial_text = partial_result.get("partial", "").strip()
            
            is_speech_in_frame = bool(self.partial_text) # Speech is happening if partial text exists
            current_full_text = (self.complete_text + " " + self.partial_text).strip() if self.complete_text else self.partial_text
            return False, is_speech_in_frame, current_full_text

    def get_final_text(self): # Or rename to transcribe() if preferred
        """
        Get the final transcription after all frames are processed and VAD loop ends.
        This calls Vosk's FinalResult().
        """
        final_result_str = self.recognizer.FinalResult()
        final_vosk_text_chunk = json.loads(final_result_str).get("text", "").strip()

        if final_vosk_text_chunk:
             self.complete_text = (self.complete_text + " " + final_vosk_text_chunk).strip() if self.complete_text else final_vosk_text_chunk
        
        return self.complete_text.strip()

    def cleanup(self):
        """Clean up resources if any were held (not much for Vosk typically)."""
        self.reset() # Good practice to reset state
