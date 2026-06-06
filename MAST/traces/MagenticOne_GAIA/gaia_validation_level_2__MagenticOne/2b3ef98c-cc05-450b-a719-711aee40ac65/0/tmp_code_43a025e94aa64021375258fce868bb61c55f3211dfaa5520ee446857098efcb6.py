import os
from pydub import AudioSegment
import speech_recognition as sr

# Ensure ffmpeg is installed and on the PATH

def transcribe_audio(file_path):
    try:
        # Convert MP3 to WAV
        audio = AudioSegment.from_mp3(file_path)
        wav_path = file_path.replace('.mp3', '.wav')
        audio.export(wav_path, format="wav")

        # Transcribe audio using SpeechRecognition
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
            text = recognizer.recognize_google(audio_data)
        return text
    
    except Exception as e:
        return f"An error occurred: {e}"

# Specify the path to the audio file
audio_file_path = '2b3ef98c-cc05-450b-a719-711aee40ac65.mp3'

# Check if the audio file exists
if os.path.exists(audio_file_path):
    transcription = transcribe_audio(audio_file_path)
    print(transcription)
else:
    print("Audio file not found.")
