from pydub import AudioSegment
import speech_recognition as sr

# Convert mp3 to wav
audio_file_path = '/workspace/1f975693-876d-457b-a649-393859e79bf3.mp3'
wav_file_path = '/workspace/converted_audio.wav'

# Load the mp3 file
audio = AudioSegment.from_file(audio_file_path, format='mp3')
# Export as wav
audio.export(wav_file_path, format='wav')

# Initialize recognizer
recognizer = sr.Recognizer()

# Use AudioFile as a source
with sr.AudioFile(wav_file_path) as source:
    # Adjust for ambient noise and record
    recognizer.adjust_for_ambient_noise(source)
    audio = recognizer.record(source)

# Recognize speech using Google Web API
try:
    text = recognizer.recognize_google(audio)
    print("Extracted text:", text)
except sr.RequestError:
    print("Could not request results from Google Speech Recognition service")
except sr.UnknownValueError:
    print("Google Web API could not understand the audio")
