import sys
import requests
import uuid
import os
from pydub import AudioSegment
from pydub.playback import play

def main():
    if len(sys.argv) < 2:
        print("Usage: quickTTS.py 'text' --voice='voice_model' --language='language_code'")
        return
    
    text = sys.argv[1]
    voice_model = next((arg.split('=')[1] for arg in sys.argv if arg.startswith('--voice=')), "female.wav")
    language = next((arg.split('=')[1] for arg in sys.argv if arg.startswith('--language=')), "en")
    all_merge = next((arg.split('=')[1] for arg in sys.argv if arg.startswith('--am=')), False)
    id = str(uuid.uuid4())[:8]

    all_voice_models = [
        "calm_female.wav",
        "female3.wav",
        "male.wav",
    ]

    if all_merge:

        os.makedirs(id, exist_ok=True)
        paths = convert_text_to_multiple_audio(id, text, all_voice_models, language)

        first_part = f"{id}/output.wav"
        merge_audio_files(paths, first_part)

        second_part = f"{id}/output2.wav"
        merge_audio_files_into_each_other(paths, second_part)

        merge_audio_files([first_part, second_part], f"{id}_final_am.wav")
    else:
        convert_text_to_audio(id, text, voice_model, language)

def convert_text_to_multiple_audio(id, text, voice_models, language="en"):
    # Convert text to audio for multiple voice models
    audio_paths = []
    for voice_model in voice_models:
        save_path = f"{id}/{voice_model}_output.wav"
        convert_text_to_audio(text, voice_model, language, save_path)
        audio_paths.append(save_path)
    return audio_paths

def merge_audio_files(audio_paths, output_path="merged_output.wav"):
    from pydub import AudioSegment
    merged_audio = AudioSegment.empty()
    for audio_path in audio_paths:
        audio = AudioSegment.from_wav(audio_path)
        merged_audio += audio
    merged_audio.export(output_path, format="wav")


def merge_audio_files_into_each_other(audio_paths, output_path="merged_output.wav"):
    first_audio = AudioSegment.from_wav(audio_paths[0])
    for audio_path in audio_paths[1:]:
        next_audio = AudioSegment.from_wav(audio_path)
        first_audio = first_audio.overlay(next_audio)

    first_audio.export(output_path, format="wav")


def convert_text_to_audio(text, voice_model, language = "en", save_path = "output.wav"):
    # Make a POST request to the TTS server to convert text to audio
    url = "http://127.0.0.1:8020/tts_to_audio/"
    payload = {
        "text": text,
        "speaker_wav": voice_model,
        "language": language
    }
    
    try:
        response = requests.post(url, json=payload)
        
        if response.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(response.content)
            print("Audio transcribed successfully")
        else:
            print("Failed to transcribe audio")
            print(f"Error: {response.content}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()