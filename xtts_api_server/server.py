from TTS.api import TTS
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse,StreamingResponse

from pydantic import BaseModel
import uvicorn

import os
import time
from pathlib import Path
import shutil
from loguru import logger
from argparse import ArgumentParser
from pathlib import Path

from xtts_api_server.tts_funcs import TTSWrapper,supported_languages
from xtts_api_server.RealtimeTTS import TextToAudioStream, CoquiEngine
from xtts_api_server.modeldownloader import check_stream2sentence_version,install_deepspeed_based_on_python_version

# Default Folders , you can change them via API
DEVICE = os.getenv('DEVICE',"cuda")
OUTPUT_FOLDER = os.getenv('OUTPUT', 'output')
SPEAKER_FOLDER = os.getenv('SPEAKER', 'speakers')
BASE_HOST = os.getenv('BASE_URL', '127.0.0.1:8020')
BASE_URL = os.getenv('BASE_URL', '127.0.0.1:8020')
MODEL_SOURCE = os.getenv("MODEL_SOURCE", "local")
MODEL_VERSION = os.getenv("MODEL_VERSION","v2.0.2")
LOWVRAM_MODE = os.getenv("LOWVRAM_MODE") == 'true'
DEEPSPEED = os.getenv("DEEPSPEED") == 'true'
USE_CACHE = os.getenv("USE_CACHE") == 'true'

# STREAMING VARS
STREAM_MODE = os.getenv("STREAM_MODE") == 'true'
STREAM_MODE_IMPROVE = os.getenv("STREAM_MODE_IMPROVE") == 'true'
STREAM_PLAY_SYNC = os.getenv("STREAM_PLAY_SYNC") == 'true'

if(DEEPSPEED):
  install_deepspeed_based_on_python_version()

# Create an instance of the TTSWrapper class and server
app = FastAPI()
XTTS = TTSWrapper(OUTPUT_FOLDER,SPEAKER_FOLDER,LOWVRAM_MODE,MODEL_SOURCE,MODEL_VERSION,DEVICE,DEEPSPEED,USE_CACHE)

# Check for old format model version
XTTS.model_version = XTTS.check_model_version_old_format(MODEL_VERSION)
MODEL_VERSION = XTTS.model_version

# Create version string
version_string = ""
if MODEL_SOURCE == "api" or MODEL_VERSION == "main":
    version_string = "lastest"
else:
    version_string = MODEL_VERSION

# Load model
if STREAM_MODE or STREAM_MODE_IMPROVE:
    # Load model for Streaming
    check_stream2sentence_version()

    logger.warning("'Streaming Mode' has certain limitations, you can read about them here https://github.com/daswer123/xtts-api-server#about-streaming-mode")

    if STREAM_MODE_IMPROVE:
        logger.info("You launched an improved version of streaming, this version features an improved tokenizer and more context when processing sentences, which can be good for complex languages like Chinese")
        
    this_dir = Path(__file__).parent.resolve()

    if XTTS.isModelOfficial(MODEL_VERSION): 
      model_path = this_dir / "models"
    else:
      model_path = "models"
    
    engine = CoquiEngine(specific_model=MODEL_VERSION,use_deepspeed=DEEPSPEED,local_models_path=str(model_path))
    stream = TextToAudioStream(engine)
else:
  logger.info(f"Model: '{version_string}' starts to load,wait until it loads")
  XTTS.load_model() 

if USE_CACHE:
    logger.info("You have enabled caching, this option enables caching of results, your results will be saved and if there is a repeat request, you will get a file instead of generation")

# Add CORS middleware 
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Help funcs
def play_stream(stream,language):
  if STREAM_MODE_IMPROVE:
    # Here we define common arguments in a dictionary for DRY principle
    play_args = {
        'minimum_sentence_length': 2,
        'minimum_first_fragment_length': 2,
        'tokenizer': "stanza",
        'language': language,
        'context_size': 2
    }
    if STREAM_PLAY_SYNC:
        # Play synchronously
        stream.play(**play_args)
    else:
        # Play asynchronously
        stream.play_async(**play_args)
  else:
    # If not improve mode just call the appropriate method based on sync_play flag.
    if STREAM_PLAY_SYNC:
      stream.play()
    else:
      stream.play_async()

class OutputFolderRequest(BaseModel):
    output_folder: str

class SpeakerFolderRequest(BaseModel):
    speaker_folder: str

class SynthesisRequest(BaseModel):
    text: str
    speaker_wav: str 
    language: str

class SynthesisFileRequest(BaseModel):
    text: str
    speaker_wav: str 
    language: str
    file_name_or_path: str  

@app.get("/speakers_list")
def get_speakers():
    speakers = XTTS.get_speakers()
    return speakers

@app.get("/speakers")
def get_speakers():
    speakers = XTTS.get_speakers_special()
    return speakers

@app.get("/languages")
def get_languages():
    languages = XTTS.list_languages()
    return {"languages": languages}

@app.get("/get_folders")
def get_folders():
    speaker_folder = XTTS.speaker_folder
    output_folder = XTTS.output_folder
    return {"speaker_folder": speaker_folder, "output_folder": output_folder}

@app.get("/sample/{file_name:path}")
def get_sample(file_name: str):
    file_path = os.path.join(XTTS.speaker_folder, file_name)
    if os.path.isfile(file_path):
        return FileResponse(file_path, media_type="audio/wav")
    else:
        logger.error("File not found")
        raise HTTPException(status_code=404, detail="File not found")

@app.post("/set_output")
def set_output(output_req: OutputFolderRequest):
    try:
        XTTS.set_out_folder(output_req.output_folder)
        return {"message": f"Output folder set to {output_req.output_folder}"}
    except ValueError as e:
        logger.error(e)
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/set_speaker_folder")
def set_speaker_folder(speaker_req: SpeakerFolderRequest):
    try:
        XTTS.set_speaker_folder(speaker_req.speaker_folder)
        return {"message": f"Speaker folder set to {speaker_req.speaker_folder}"}
    except ValueError as e:
        logger.error(e)
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/tts_to_audio/")
async def tts_to_audio(request: SynthesisRequest):
    if STREAM_MODE or STREAM_MODE_IMPROVE:
        try:
            global stream
            # Validate language code against supported languages.
            if request.language.lower() not in supported_languages:
                raise HTTPException(status_code=400,
                                    detail="Language code sent is either unsupported or misspelled.")

            speaker_wav = XTTS.get_speaker_wav(request.speaker_wav)
            language = request.language[0:2]

            if stream.is_playing() and not STREAM_PLAY_SYNC:
                stream.stop()
                stream = TextToAudioStream(engine)

            engine.set_voice(speaker_wav)
            engine.language = request.language.lower()
           
            # Start streaming, works only on your local computer.
            stream.feed(request.text)
            play_stream(stream,language)

            # It's a hack, just send 1 second of silence so that there is no sillyTavern error.
            this_dir = Path(__file__).parent.resolve()
            output = this_dir / "RealtimeTTS" / "silence.wav"

            return FileResponse(
                path=output,
                media_type='audio/wav',
                filename="silence.wav",
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    else:
        try:
            if XTTS.model_source == "local":
              logger.info(f"Processing TTS to audio with request: {request}")

            # Validate language code against supported languages.
            if request.language.lower() not in supported_languages:
                raise HTTPException(status_code=400,
                                    detail="Language code sent is either unsupported or misspelled.")

            # Generate an audio file using process_tts_to_file.
            output_file_path = XTTS.process_tts_to_file(
                text=request.text,
                speaker_name_or_path=request.speaker_wav,
                language=request.language.lower()
            )

            # Return the file in the response
            return FileResponse(
                path=output_file_path,
                media_type='audio/wav',
                filename="output.wav",
                )

        except Exception as e:
            logger.error(e)
            raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/tts_to_file")
async def tts_to_file(request: SynthesisFileRequest):
    try:
        if XTTS.model_source == "local":
          logger.info(f"Processing TTS to file with request: {request}")

        # Validate language code against supported languages.
        if request.language.lower() not in supported_languages:
             raise HTTPException(status_code=400,
                                 detail="Language code sent is either unsupported or misspelled.")

        # Now use process_tts_to_file for saving the file.
        output_file = XTTS.process_tts_to_file(
            text=request.text,
            speaker_name_or_path=request.speaker_wav,
            language=request.language.lower(),
            file_name_or_path=request.file_name_or_path  # The user-provided path to save the file is used here.
        )
        return {"message": "The audio was successfully made and stored.", "output_path": output_file}

    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app,host="0.0.0.0",port=8002)
